from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import os, json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

@dataclass
class VLMRagConfig:
    jsonl_path: str
    embed_model_name: str = "BAAI/bge-small-en-v1.5"
    top_k: int = 2

class VLMTextRag:
    def __init__(self, cfg: VLMRagConfig):
        self.cfg = cfg
        self.embed_model = SentenceTransformer(cfg.embed_model_name)
        self.entries: List[Dict[str, Any]] = []
        self.index = None

    def load(self) -> "VLMTextRag":
        path = os.path.abspath(self.cfg.jsonl_path)
        if not os.path.exists(path):
            raise FileNotFoundError(f"RAG file not found: {path}")

        entries = []
        with open(path, "r", encoding="utf-8-sig") as f:
            for line in f:
                if not line.strip():
                    continue
                item = json.loads(line)
                rel_path = item["path"].lstrip("/")
                item["abs_path"] = os.path.abspath(os.path.join(os.getcwd(), rel_path))
                entries.append(item)
        self.entries = entries

        embs = [self.embed_model.encode(e["caption"], normalize_embeddings=True) for e in self.entries]
        embs = np.vstack(embs).astype("float32")

        idx = faiss.IndexFlatIP(embs.shape[1])
        idx.add(embs)
        self.index = idx
        return self

    def retrieve(self, query: str, k: Optional[int] = None) -> List[Dict[str, Any]]:
        if self.index is None:
            raise RuntimeError("VLMTextRag not loaded. Call .load() first.")
        k = k or self.cfg.top_k
        q_emb = self.embed_model.encode([query], normalize_embeddings=True).astype("float32")
        D, I = self.index.search(q_emb, k)
        out = []
        for rank, idx in enumerate(I[0]):
            out.append({
                "score": float(D[0][rank]),
                "caption": self.entries[int(idx)]["caption"],
                "path": self.entries[int(idx)]["abs_path"],
            })
        return out
