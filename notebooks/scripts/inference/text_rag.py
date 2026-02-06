from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

from .utils import load_all_jsonls
from .config import RAGConfig

@dataclass
class RagResult:
    rank: int
    score: float
    source: str
    category: str
    instruction: str
    code: str

class RagIndex:
    """
    Simple in-memory FAISS IP index over (instruction + code).
    """
    def __init__(self, cfg: RAGConfig):
        self.cfg = cfg
        self.enabled = bool(cfg.enabled)
        self.embed_model: Optional[SentenceTransformer] = None
        self.index: Optional[faiss.Index] = None
        self.items: List[Dict[str, Any]] = []
        self._dim: Optional[int] = None

    def build(self) -> "RagIndex":
        if not self.enabled:
            return self

        self.items = load_all_jsonls(self.cfg.jsonl_paths or [])
        if len(self.items) == 0:
            print("⚠️ RAG enabled, but no items were loaded. Disabling RAG.")
            self.enabled = False
            return self

        print("🔍 Loading embed model:", self.cfg.embed_model_name)
        self.embed_model = SentenceTransformer(self.cfg.embed_model_name)

        print("🔍 Encoding entries...")
        embs = []
        for it in self.items:
            txt = f"{it.get('instruction','')}\n{it.get('code','')}"
            e = self.embed_model.encode(txt, normalize_embeddings=True)
            embs.append(e)

        embeddings = np.vstack(embs).astype("float32")
        self._dim = embeddings.shape[1]

        self.index = faiss.IndexFlatIP(self._dim)
        self.index.add(embeddings)

        print(f"✅ Built FAISS index with {len(self.items)} items. dim={self._dim}")
        return self

    def retrieve(self, query: str, k: Optional[int] = None) -> List[RagResult]:
        if not self.enabled or self.index is None or self.embed_model is None:
            return []

        k = k or self.cfg.top_k
        q_emb = self.embed_model.encode([query], normalize_embeddings=True).astype("float32")
        D, I = self.index.search(q_emb, k)

        out: List[RagResult] = []
        for rank, idx in enumerate(I[0]):
            item = self.items[int(idx)]
            out.append(RagResult(
                rank=rank,
                score=float(D[0][rank]),
                source=item.get("source", ""),
                category=item.get("category", "unknown"),
                instruction=item.get("instruction", ""),
                code=item.get("code", ""),
            ))
        return out

    def build_context(self, query: str, k: Optional[int] = None) -> str:
        results = self.retrieve(query, k=k)
        if not results:
            return ""

        chunks = []
        for r in results:
            chunks.append(
                "Source: {source}\n"
                "Instruction: {instruction}\n"
                "Category: {category}\n"
                "Code:\n{code}\n".format(
                    source=r.source,
                    instruction=r.instruction,
                    category=r.category,
                    code=r.code,
                )
            )
        return "\n---\n".join(chunks)
