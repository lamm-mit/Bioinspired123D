from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import os
from openai import OpenAI

@dataclass
class OpenAIConfig:
    api_key_env: str = "OPENAI_API_KEY"
    model_text: str = "gpt-4o-mini"
    model_vlm: str = "gpt-4o-mini"
    temperature: float = 0.1

class OpenAIClient:
    def __init__(self, cfg: OpenAIConfig):
        api_key = os.getenv(cfg.api_key_env)
        if not api_key:
            raise RuntimeError(f"Missing env var {cfg.api_key_env}. Set it before running.")
        self.cfg = cfg
        self.client = OpenAI(api_key=api_key)

    def chat_text(self, prompt: str, model: Optional[str] = None, temperature: Optional[float] = None, max_tokens: int = 800) -> str:
        model = model or self.cfg.model_text
        temperature = self.cfg.temperature if temperature is None else temperature
        resp = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content.strip()

    def chat_multimodal(self, content_blocks: List[Dict[str, Any]], model: Optional[str] = None, temperature: Optional[float] = None, max_tokens: int = 500) -> str:
        model = model or self.cfg.model_vlm
        temperature = self.cfg.temperature if temperature is None else temperature
        resp = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content_blocks}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content.strip()
