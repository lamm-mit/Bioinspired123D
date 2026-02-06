from dataclasses import dataclass
from typing import List, Optional

@dataclass
class RAGConfig:
    enabled: bool = True
    jsonl_paths: List[str] = None
    embed_model_name: str = "BAAI/bge-small-en-v1.5"
    top_k: int = 2

@dataclass
class Bio3DConfig:
    device: str = "cuda:0"
    base_model: str = "meta-llama/Llama-3.2-3B-Instruct"
    lora_adapter: str = "rachelkluu/bioinspired3D"
    torch_dtype: str = "float16"   # "float16" or "bfloat16"
