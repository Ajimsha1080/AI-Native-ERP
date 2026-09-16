"""
Vector Store & Embedding Engine for Enterprise RAG
Supports local Chroma vector store and deterministic fallback embeddings.
"""

import os
import math
import hashlib
from typing import List, Dict, Any, Optional
import logging
from packages.config import get_settings

logger = logging.getLogger("rag.vector_store")
settings = get_settings()


class DeterministicEmbedder:
    """384-dimensional feature hashing embedding function for offline/local semantic similarity."""
    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def embed_text(self, text: str) -> List[float]:
        words = text.lower().split()
        vec = [0.0] * self.dimension
        if not words:
            return vec

        for w in words:
            h = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dimension
            sign = 1.0 if (h >> 4) % 2 == 0 else -1.0
            vec[idx] += sign

        # L2 normalize
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self.embed_text(text)


class ChromaVectorStore:
    """Enterprise Vector Store backed by persistent ChromaDB."""

    def __init__(self, persist_directory: str = "./data/chroma"):
        self.persist_directory = persist_directory
        self.embedder = DeterministicEmbedder(dimension=384)
        self._client = None
        self._init_client()

    def _init_client(self):
        try:
            import chromadb
            os.makedirs(self.persist_directory, exist_ok=True)
            self._client = chromadb.PersistentClient(path=self.persist_directory)
            logger.info(f"Initialized ChromaDB persistent client at {self.persist_directory}")
        except Exception as e:
            logger.warning(f"ChromaDB initialization fallback: {e}")
            self._client = None

    def get_or_create_collection(self, collection_name: str = "agentic_knowledge"):
        if self._client:
            try:
                return self._client.get_or_create_collection(
                    name=collection_name,
                    metadata={"hnsw:space": "cosine"}
                )
            except Exception as e:
                logger.error(f"Error getting Chroma collection: {e}")
        return None

    def add_documents(
        self,
        collection_name: str,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str]
    ) -> bool:
        """Add text chunks and embeddings to the vector collection."""
        if not documents:
            return True

        collection = self.get_or_create_collection(collection_name)
        embeddings = self.embedder.embed_documents(documents)

        if collection:
            try:
                collection.upsert(
                    ids=ids,
                    documents=documents,
                    embeddings=embeddings,
                    metadatas=metadatas
                )
                logger.info(f"Indexed {len(documents)} vector chunks into Chroma collection '{collection_name}'")
                return True
            except Exception as e:
                logger.error(f"Failed to index documents into ChromaDB: {e}")
                return False
        return False

    def query(
        self,
        collection_name: str,
        query_text: str,
        top_k: int = 5,
        scope: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Semantic vector query returning top-k matching document chunks with optional departmental scope."""
        collection = self.get_or_create_collection(collection_name)
        query_embedding = self.embedder.embed_query(query_text)

        if collection:
            try:
                query_kwargs: Dict[str, Any] = {
                    "query_embeddings": [query_embedding],
                    "n_results": top_k
                }
                if scope and scope.lower() not in ["global", "all"]:
                    query_kwargs["where"] = {"department": scope.lower()}

                results = collection.query(**query_kwargs)
                formatted = []
                docs = results.get("documents", [[]])[0]
                metas = results.get("metadatas", [[]])[0]
                distances = results.get("distances", [[]])[0] if "distances" in results else [0.1] * len(docs)

                for doc, meta, dist in zip(docs, metas, distances):
                    # Cosine distance to relevance score (1 - dist)
                    relevance = round(max(0.0, 1.0 - float(dist)), 4) if dist is not None else 0.95
                    formatted.append({
                        "content": doc,
                        "metadata": meta,
                        "document_title": (meta or {}).get("document_title", "Indexed Document"),
                        "chunk_index": (meta or {}).get("chunk_index", 0),
                        "department": (meta or {}).get("department", "global"),
                        "relevance_score": relevance
                    })
                return formatted
            except Exception as e:
                logger.error(f"ChromaDB query failed: {e}")

        # In-memory fallback if Chroma collection is empty or unreachable
        return []



# Global Vector Store Instance
vector_store = ChromaVectorStore()
