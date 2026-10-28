"""
Layer 4: Dense Vector Embedding Service.
Provides semantic embeddings for cosine similarity search with real provider validation,
exponential backoff retry, and loud failure modes.
"""

import time
import logging
from typing import List, Optional
from packages.config.settings import settings

logger = logging.getLogger("rag.embedding_service")


class EmbeddingServiceError(Exception):
    """Raised when the embedding provider fails or configuration is missing."""
    pass


class EmbeddingService:
    """Dense Semantic Embedding Service with verified provider integration and backoff."""

    def __init__(self, model: Optional[str] = None, dimension: Optional[int] = None):
        self.model = model or getattr(settings, "embedding_model", "text-embedding-3-small")
        self.dimension = dimension or getattr(settings, "embedding_dimension", 1536)

    def _call_provider_with_retry(self, texts: List[str], max_retries: int = 3) -> List[List[float]]:
        """
        Calls external embedding provider with exponential backoff retry.
        Fails loudly if provider fails or API keys are missing.
        """
        api_key = getattr(settings, "openai_api_key", None)
        if not api_key or not api_key.startswith("sk-"):
            raise EmbeddingServiceError(
                f"No valid OpenAI/Embedding API key configured for model '{self.model}'. "
                "Deterministic and hash-based embedding fallbacks have been removed for production security."
            )

        last_exception = None
        backoff = 0.5
        for attempt in range(1, max_retries + 1):
            try:
                from openai import OpenAI
                client = OpenAI(api_key=api_key)
                res = client.embeddings.create(
                    input=texts,
                    model=self.model
                )
                embeddings = [item.embedding for item in res.data]
                for emb in embeddings:
                    if len(emb) != self.dimension:
                        raise EmbeddingServiceError(
                            f"Provider returned vector of dimension {len(emb)}, "
                            f"expected {self.dimension} for model '{self.model}'."
                        )
                return embeddings
            except EmbeddingServiceError:
                raise
            except Exception as exc:
                last_exception = exc
                logger.warning(
                    f"Embedding provider attempt {attempt}/{max_retries} failed for model '{self.model}': {exc}"
                )
                if attempt < max_retries:
                    time.sleep(backoff)
                    backoff *= 2

        raise EmbeddingServiceError(
            f"Embedding provider failed after {max_retries} retries for model '{self.model}': {last_exception}"
        ) from last_exception

    def embed_text(self, text: str) -> List[float]:
        """Embeds single text into normalized vector. Fails loudly on error."""
        if not text:
            return [0.0] * self.dimension
        results = self._call_provider_with_retry([text])
        return results[0]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Batch embedding of documents. Fails loudly on error."""
        if not texts:
            return []
        return self._call_provider_with_retry(texts)

    def embed_query(self, query: str) -> List[float]:
        """Embed query string. Fails loudly on error."""
        return self.embed_text(query)


# Global Embedding Service singleton
embedding_service = EmbeddingService()
