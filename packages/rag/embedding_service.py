"""
Layer 4: Dense Vector Embedding Service.
Provides 1536-dimensional semantic embeddings for cosine similarity search.
"""

import math
import hashlib
from typing import List, Optional
from packages.config.settings import settings


class EmbeddingService:
    """Dense Semantic Embedding Service with 1536-dimensional vectors."""

    def __init__(self, dimension: int = 1536):
        self.dimension = dimension

    def _hash_embed(self, text: str) -> List[float]:
        """Deterministic 1536-dimensional feature hashing for local offline similarity."""
        words = text.lower().split()
        vec = [0.0] * self.dimension
        if not words:
            return vec

        for w in words:
            h = int(hashlib.sha256(w.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dimension
            sign = 1.0 if (h >> 5) % 2 == 0 else -1.0
            vec[idx] += sign

        # L2 Normalization
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def embed_text(self, text: str) -> List[float]:
        """Embeds single text into 1536-dim normalized vector."""
        if not text:
            return [0.0] * self.dimension

        # If live OpenAI/External API is available, use text-embedding-3-small (1536 dims)
        if getattr(settings, "openai_api_key", None) and settings.openai_api_key.startswith("sk-"):
            try:
                from openai import OpenAI
                client = OpenAI(api_key=settings.openai_api_key)
                res = client.embeddings.create(
                    input=text,
                    model="text-embedding-3-small"
                )
                return res.data[0].embedding
            except Exception:
                pass

        return self._hash_embed(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Batch embedding of documents."""
        return [self.embed_text(t) for t in texts]

    def embed_query(self, query: str) -> List[float]:
        """Embed query string."""
        return self.embed_text(query)


# Global Embedding Service
embedding_service = EmbeddingService(dimension=1536)
