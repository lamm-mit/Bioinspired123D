from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List
import os, re, json, base64, textwrap

from .openai_client import OpenAIClient
from .vlm_text_rag import VLMTextRag

def _encode_png(path: str) -> str:
    with open(path, "rb") as f:
        b = f.read()
    return "data:image/png;base64," + base64.b64encode(b).decode("utf-8")

@dataclass
class VLMCriticConfig:
    top_k_refs: int = 2

class VLMCritic:
    def __init__(self, client: OpenAIClient, rag: VLMTextRag, cfg: VLMCriticConfig = VLMCriticConfig()):
        self.client = client
        self.rag = rag
        self.cfg = cfg

    def critique(self, design_prompt: str, render_path: str) -> Dict[str, Any]:
        results = self.rag.retrieve(design_prompt, k=self.cfg.top_k_refs)
        ref_images = [r for r in results if os.path.exists(r["path"])]

        blocks: List[Dict[str, Any]] = []

        for i, ref in enumerate(ref_images[: self.cfg.top_k_refs], start=1):
            blocks.append({"type": "text", "text": f"Reference image {i}: {ref['caption']}"})
            blocks.append({"type": "image_url", "image_url": {"url": _encode_png(ref["path"])}})

        blocks.append({"type": "text", "text": "Candidate render to evaluate:"})
        blocks.append({"type": "image_url", "image_url": {"url": _encode_png(render_path)}})

        vlm_prompt = textwrap.dedent(f"""
        You are a critic of 3D model renders.

        Intended Design Concept:
        "{design_prompt}"

        Evaluate the candidate render independently:
        1. Match quality: "good" | "partial" | "poor"
        2. Physical stability: "stable" | "unstable"

        approve=true only when both "good" and "stable".

        Return STRICT JSON:
        {{
          "match_quality": "good" | "partial" | "poor",
          "physical_stability": "stable" | "unstable",
          "comment": "one sentence",
          "approve": true | false
        }}
        """).strip()

        blocks.append({"type": "text", "text": vlm_prompt})

        output_text = self.client.chat_multimodal(blocks)

        m = re.search(r"\{.*\}", output_text, flags=re.DOTALL)
        if not m:
            raise ValueError("No JSON object found in VLM output.")
        return json.loads(m.group(0))
