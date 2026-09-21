"""
Enterprise RAG (Retrieval-Augmented Generation) Subsystem.
Provides Document OCR parsing, Chroma vector storage, BM25 sparse search,
Contextual Query Reformulation, Cross-Encoder Reranking, Anti-Hallucination Gate, and LLM Gateway.
"""

from packages.rag.document_parser import document_parser, EnterpriseDocumentParser
from packages.rag.vector_store import vector_store, ChromaVectorStore
from packages.rag.bm25 import BM25Retriever
from packages.rag.query_rewrite import query_rewriter, ContextualQueryRewriter
from packages.rag.embedding_service import embedding_service, EmbeddingService
from packages.rag.reranking_service import reranking_service, CrossEncoderReranker
from packages.rag.llm_service import llm_gateway, LLMGateway
from packages.rag.rag_engine import hybrid_rag_engine, HybridRAGEngine, GroundedRAGResult
from packages.rag.pipeline import rag_engine, AdvancedRAGEngine, RAGResponse, Citation, RetrievedChunk

__all__ = [
    "document_parser",
    "EnterpriseDocumentParser",
    "vector_store",
    "ChromaVectorStore",
    "BM25Retriever",
    "query_rewriter",
    "ContextualQueryRewriter",
    "embedding_service",
    "EmbeddingService",
    "reranking_service",
    "CrossEncoderReranker",
    "llm_gateway",
    "LLMGateway",
    "hybrid_rag_engine",
    "HybridRAGEngine",
    "GroundedRAGResult",
    "rag_engine",
    "AdvancedRAGEngine",
    "RAGResponse",
    "Citation",
    "RetrievedChunk",
]
