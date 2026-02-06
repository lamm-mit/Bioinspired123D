from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import os
import textwrap

from .state import DesignState
from .utils import extract_blender_code, clean_blender_code
from .blender_exec import BlenderValidator
from .openai_client import OpenAIClient
from .llm_bio3d import Bio3D


@dataclass
class NodeConfig:
    debug_dir: str = "/home/rachel/bio3d_debug_fixes"
    max_code_fix_attempts: int = 3
    max_design_fix_attempts: int = 1


class Bio3DNode:
    def __init__(self, bio3d: Bio3D, blender: BlenderValidator):
        self.bio3d = bio3d
        self.blender = blender

    def __call__(self, state: DesignState) -> DesignState:
        state["last_node"] = "bio3d"
        print("\n🧱 Bio3D generating Blender code...")

        raw = self.bio3d.generate_code(state.get("design_prompt") or "", mode="design")
        code = clean_blender_code(extract_blender_code(raw))
        state["blender_code"] = code
        print(code)

        result = self.blender.run(code, label="initial", render_subdir_wsl=state.get("render_subdir_wsl"))
        state["render_path"] = result.get("render_path")
        state["blender_status"] = result.get("status", "unknown")
        state["error_snippet"] = result.get("error_snippet")
        state["approved"] = False
        return state


class CodeFixerNode:
    """
    Fixes Blender runtime/syntax errors using OpenAI.
    Optionally injects Bio3D text-RAG context via the Bio3D instance (even though the fixer model is OpenAI).
    """

    def __init__(
        self,
        client: OpenAIClient,
        blender: BlenderValidator,
        *,
        cfg: NodeConfig = NodeConfig(),
        bio3d_for_rag: Optional[Bio3D] = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.1,
    ):
        self.client = client
        self.blender = blender
        self.cfg = cfg
        self.bio3d_for_rag = bio3d_for_rag
        self.model = model
        self.temperature = temperature

        os.makedirs(self.cfg.debug_dir, exist_ok=True)

    def _build_rag_context(self, query: str, k: int = 2) -> str:
        if self.bio3d_for_rag is None or not self.bio3d_for_rag.rag_enabled:
            return ""
        return self.bio3d_for_rag.rag.build_context(query, k=k)

    def _build_prompt(self, design_prompt: str, code_to_fix: str, blender_feedback: str) -> str:
        context_block = self._build_rag_context(design_prompt, k=2)
        return textwrap.dedent(f"""\
        You are a Blender Python code repair assistant.
        Your task is to FIX and RETURN a working Blender script only.

        Here are potentially useful base code examples retrieved from the database:
        {context_block}

        Blender error message:
        {blender_feedback}

        Output ONLY valid Python code.

        CODE TO FIX:
        {code_to_fix}
        """).strip()

    def __call__(self, state: DesignState) -> DesignState:
        state["last_node"] = "codefixer"
        print("\n🧰 CodeFixer repairing Blender errors...")

        if state.get("blender_status") == "success":
            print("✅ No Blender errors detected — skipping CodeFixer.")
            state["fix_success"] = True
            return state

        attempts = 0
        fixed_code = state.get("blender_code") or ""
        blender_error = state.get("error_snippet") or ""
        design_prompt = state.get("design_prompt") or ""

        while attempts < self.cfg.max_code_fix_attempts:
            attempts += 1
            print(f"\n🔧 Attempt {attempts} (CodeFixer)\n{'='*60}")

            prompt = self._build_prompt(design_prompt, fixed_code, blender_error)

            raw = self.client.chat_text(prompt, model=self.model, temperature=self.temperature, max_tokens=1200)
            code_block = extract_blender_code(raw)
            if not code_block.strip():
                print("⚠️ No valid Python code detected. Retrying...")
                continue

            fixed_code = clean_blender_code(code_block)

            dbg_path = os.path.join(self.cfg.debug_dir, f"fix_attempt_{attempts}_runfix.py")
            with open(dbg_path, "w", encoding="utf-8") as f:
                f.write(fixed_code)

            result = self.blender.run(
                fixed_code,
                label=f"fix_run_{attempts}",
                render_subdir_wsl=state.get("render_subdir_wsl"),
            )

            state.update({
                "render_path": result.get("render_path"),
                "blender_status": result.get("status", "unknown"),
                "error_snippet": result.get("error_snippet"),
                "fix_attempts_used": attempts,
            })

            if result.get("status") == "success":
                print("✅ Blender validation succeeded after fix.")
                state["blender_code_fixed"] = fixed_code
                state["fix_success"] = True
                return state

            blender_error = state.get("error_snippet") or ""

        print("🛑 CodeFixer failed all attempts.")
        state["fix_success"] = False
        return state


class CodeDesignerNode:
    """
    Adjusts geometry based on VLM feedback (script already runs), using OpenAI.
    If the design change breaks execution, it returns "codefixer" (LangGraph routing).
    """

    def __init__(
        self,
        client: OpenAIClient,
        blender: BlenderValidator,
        *,
        cfg: NodeConfig = NodeConfig(),
        bio3d_for_rag: Optional[Bio3D] = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.1,
    ):
        self.client = client
        self.blender = blender
        self.cfg = cfg
        self.bio3d_for_rag = bio3d_for_rag
        self.model = model
        self.temperature = temperature

        os.makedirs(self.cfg.debug_dir, exist_ok=True)

    def _build_rag_context(self, query: str, k: int = 2) -> str:
        if self.bio3d_for_rag is None or not self.bio3d_for_rag.rag_enabled:
            return ""
        return self.bio3d_for_rag.rag.build_context(query, k=k)

    def _build_prompt(self, design_prompt: str, code_to_improve: str, vlm_feedback_json: str) -> str:
        context_block = self._build_rag_context(design_prompt, k=2)
        code_clean = clean_blender_code(code_to_improve)
        return textwrap.dedent(f"""\
        You are a Blender Python code design assistant.
        The script already runs. Now carefully ADJUST the geometry to satisfy the critique.

        Here are potentially useful base code examples retrieved from the database:
        {context_block}

        Design Concept:
        {design_prompt}

        Critique:
        {vlm_feedback_json}

        Output ONLY valid Python code.

        CODE TO IMPROVE:
        {code_clean}
        """).strip()

    def __call__(self, state: DesignState):
        state["last_node"] = "codedesigner"
        state["iteration_count"] = int(state.get("iteration_count") or 0) + 1

        print(f"\n🎨 CodeDesigner improving geometry... (iter={state['iteration_count']})")

        if state.get("approved"):
            print("✅ Already approved — skipping CodeDesigner.")
            return state

        design_prompt = state.get("design_prompt") or ""
        vlm_feedback = state.get("vlm_feedback") or ""
        code_base = state.get("blender_code_fixed") or state.get("blender_code") or ""

        prompt = self._build_prompt(design_prompt, code_base, vlm_feedback)
        raw = self.client.chat_text(prompt, model=self.model, temperature=self.temperature, max_tokens=1400)

        code_block = extract_blender_code(raw)
        if not code_block.strip():
            print("⚠️ No valid Python code detected.")
            return state

        improved_code = clean_blender_code(code_block)

        dbg_path = os.path.join(self.cfg.debug_dir, f"design_iter_{state['iteration_count']}.py")
        with open(dbg_path, "w", encoding="utf-8") as f:
            f.write(improved_code)

        result = self.blender.run(
            improved_code,
            label=f"design_iter_{state['iteration_count']}",
            render_subdir_wsl=state.get("render_subdir_wsl"),
        )

        state.update({
            "render_path": result.get("render_path"),
            "blender_status": result.get("status", "unknown"),
            "error_snippet": result.get("error_snippet"),
            "blender_code_fixed": improved_code,
        })

        if result.get("status") != "success":
            print("❌ Design change broke code — routing to CodeFixer next.")
            state["approved"] = False
            state["prev_to_vlm"] = "codedesigner"
            return "codefixer"

        state["prev_to_vlm"] = "codedesigner"
        return state


class VLMNode:
    def __init__(self, critic: VLMCritic):
        self.critic = critic

    def __call__(self, state: DesignState) -> DesignState:
        state["last_node"] = "vlm"
        print("\n👁️ VLM analyzing render...")

        design_prompt = state.get("design_prompt") or ""
        render_path = state.get("render_path") or ""
        try:
            data = self.critic.critique(design_prompt, render_path)
            state["vlm_analysis"] = data
            state["vlm_feedback"] = str(data)
            state["approved"] = bool(data.get("approve", False))
            if state["approved"]:
                state["final_result"] = render_path
            print(f"🧩 Approval: {state['approved']}")
        except Exception as e:
            state["vlm_feedback"] = f"Error: {e}"
            state["approved"] = False
        return state
