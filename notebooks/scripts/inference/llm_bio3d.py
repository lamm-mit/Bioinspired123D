# notebooks/scripts/inference/llm_bio3d.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any, Dict

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

from .config import Bio3DConfig, RAGConfig
from .text_rag import RagIndex
from typing import Literal

_TORCH_DTYPE_MAP = {
    "float16": torch.float16,
    "fp16": torch.float16,
    "bfloat16": torch.bfloat16,
    "bf16": torch.bfloat16,
}

PromptMode = Literal["design", "direct"]

class Bio3D:
    def __init__(self, llm_cfg: Bio3DConfig, rag_cfg: Optional[RAGConfig] = None):
        self.llm_cfg = llm_cfg
        self.rag_cfg = rag_cfg or RAGConfig(enabled=False)

        # Build RAG index only if enabled
        self.rag = RagIndex(self.rag_cfg).build()

        self.tokenizer = None
        self.model = None

    # ----------------------------
    # Properties / toggles
    # ----------------------------
    @property
    def rag_enabled(self) -> bool:
        return bool(getattr(self.rag, "enabled", False))

    def set_rag(self, enabled: bool) -> None:

        if enabled:
            self.rag_cfg.enabled = True
            if not self.rag_enabled or getattr(self.rag, "index", None) is None:
                self.rag = RagIndex(self.rag_cfg).build()
            else:
                self.rag.enabled = True
        else:
            if self.rag is not None:
                self.rag.enabled = False

    # ----------------------------
    # Loading
    # ----------------------------
    def load(self) -> "Bio3D":

        dtype = _TORCH_DTYPE_MAP.get(self.llm_cfg.torch_dtype, torch.float16)

        self.tokenizer = AutoTokenizer.from_pretrained(self.llm_cfg.base_model)

        base = AutoModelForCausalLM.from_pretrained(
            self.llm_cfg.base_model,
            torch_dtype=dtype,  # keep for compatibility; can swap to dtype=... later
            device_map={"": self.llm_cfg.device},
        )

        self.model = PeftModel.from_pretrained(base, self.llm_cfg.lora_adapter)
        self.model.eval()

        print(f"✅ Loaded Bio3D LoRA on {self.llm_cfg.device} dtype={dtype}")
        return self

    # ----------------------------
    # Prompt formatting (matches your old code)
    # ----------------------------
    def format_input_llama32(
        self,
        user_prompt: str,
        system_prompt: str = "You are a helpful assistant",
    ) -> str:

        return (
            "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
            f"{system_prompt}<|eot_id|>"
            "<|start_header_id|>user<|end_header_id|>\n\n"
            f"{user_prompt}<|eot_id|>"
            "<|start_header_id|>assistant<|end_header_id|>\n\n"
        )

    def build_generation_prompt(
        self,
        text: str,
        *,
        mode: PromptMode = "design",
    ) -> str:
        """
        mode="design": `text` is a short design description (agent-friendly).
        mode="direct": `text` is a full user request (notebook-friendly).

        No auto-detection. Caller must choose.
        """
        if mode == "design":
            query = f"Write Blender Python code for a {text}"
            user_request_line = f"User request: {query}."
            rag_query = query
        elif mode == "direct":
            # Use the text exactly as provided.
            # Also use it as the retrieval query so RAG matches the real request.
            user_request_line = f"User request: {text}"
            rag_query = text
        else:
            raise ValueError(f"Invalid mode={mode}. Use 'design' or 'direct'.")

        context_block = ""
        if self.rag_enabled:
            context_block = self.rag.build_context(rag_query, k=self.rag_cfg.top_k)

        prompt = (
            "You are a Blender scripting assistant.\n\n"
            "Here are some useful base codes retrieved from the database:\n\n"
            f"{context_block}\n\n"
            f"{user_request_line}\n\n"
            "Generate ONLY valid Blender Python code.\n"
        )
        return prompt

    # ----------------------------
    # Generation
    # ----------------------------
    @torch.inference_mode()
    def generate(
        self,
        prompt: str,
        *,
        max_new_tokens: int = 2048,
        temperature: float = 0.1,
        top_p: float = 0.9,
        do_sample: bool = True,
        system_prompt: str = "You are a helpful assistant",
        **gen_kwargs: Any,
    ) -> str:
        """
        Generate from a fully-specified user prompt (string).
        This is a low-level method.
        """
        if self.model is None or self.tokenizer is None:
            raise RuntimeError("Bio3D not loaded. Call .load() first.")

        formatted = self.format_input_llama32(prompt, system_prompt=system_prompt)
        inputs = self.tokenizer(formatted, return_tensors="pt").to(self.model.device)

        out = self.model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=do_sample,
            temperature=temperature,
            top_p=top_p,
            **gen_kwargs,
        )

        return self.tokenizer.decode(out[0], skip_special_tokens=True)
    
    @torch.inference_mode()
    def generate_code(
        self,
        text: str,
        *,
        mode: PromptMode = "design",
        max_new_tokens: int = 2048,
        temperature: float = 0.1,
        top_p: float = 0.9,
        do_sample: bool = True,
        system_prompt: str = "You are a helpful assistant",
        **gen_kwargs: Any,
    ) -> str:
        user_prompt = self.build_generation_prompt(text, mode=mode)
        return self.generate(
            user_prompt,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
            do_sample=do_sample,
            system_prompt=system_prompt,
            **gen_kwargs,
        )