from llama_index.llms.llama_cpp import LlamaCPP
from typing import Optional


class BioinspiredLLM:
    """
    One-shot bioinspired concept generator.
    Produces a compact structural design phrase.
    """

    def __init__(
        self,
        model_url: str,
        *,
        temperature: float = 0.1,
        max_new_tokens: int = 512,
        context_window: int = 16000,
        n_gpu_layers: int = -1,
        main_gpu: int = 1,
        tensor_split=(0.0, 1.0),
        verbose: bool = False,
    ):
        self.model_url = model_url
        self.temperature = temperature
        self.max_new_tokens = max_new_tokens
        self.context_window = context_window
        self.n_gpu_layers = n_gpu_layers
        self.main_gpu = main_gpu
        self.tensor_split = tensor_split
        self.verbose = verbose
        self.llm: Optional[LlamaCPP] = None

    # ---- LLaMA 3.1 formatting ----
    @staticmethod
    def completion_to_prompt(completion: str) -> str:
        return (
            "<|start_header_id|>system<|end_header_id|>\n<eot_id>\n"
            "<|start_header_id|>user<|end_header_id|>\n"
            f"{completion}<eot_id>\n"
            "<|start_header_id|>assistant<|end_header_id|>\n"
        )

    @staticmethod
    def messages_to_prompt(messages) -> str:
        prompt = "<|start_header_id|>system<|end_header_id|>\n<eot_id>\n"
        for message in messages:
            if message.role == "user":
                prompt += (
                    "<|start_header_id|>user<|end_header_id|>\n"
                    f"{message.content}<eot_id>\n"
                )
            elif message.role == "assistant":
                prompt += (
                    "<|start_header_id|>assistant<|end_header_id|>\n"
                    f"{message.content}<eot_id>\n"
                )
        prompt += "<|start_header_id|>assistant<|end_header_id|>\n"
        return prompt

    def load(self):
        self.llm = LlamaCPP(
            model_url=self.model_url,
            temperature=self.temperature,
            max_new_tokens=self.max_new_tokens,
            context_window=self.context_window,
            model_kwargs={
                "n_gpu_layers": self.n_gpu_layers,
                "main_gpu": self.main_gpu,
                "tensor_split": list(self.tensor_split),
            },
            messages_to_prompt=self.messages_to_prompt,
            completion_to_prompt=self.completion_to_prompt,
            verbose=self.verbose,
        )
        print("✅ Loaded BioinspiredLLM (GGUF)")
        return self

    def generate_design_concept(self, material: str) -> str:
        if self.llm is None:
            raise RuntimeError("BioinspiredLLM not loaded. Call .load() first.")

        prompt = f"""
You are a bioinspired materials design assistant.

Analyze the natural microstructure of {material}.
Based on its geometry, generate a concise, simple descriptive phrase that could serve as a structural design concept.

The phrase should be compact but expressive (no more than 8 words) — capturing geometric structure.

Examples:
- helical layered material made of cylindrical fibers
- cellular structure with smooth edges and sandwich layers
- tubular structure with noisy placement
"""

        resp = self.llm.complete(prompt)
        return resp.text.strip().lower()
