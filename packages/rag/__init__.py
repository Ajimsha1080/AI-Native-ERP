"""
Enterprise RAG (Retrieval-Augmented Generation) Subsystem.
Provides Document OCR parsing, Chroma vector storage, BM25 sparse search, and 12-stage Advanced RAG Pipeline.
"""

from packages.rag.document_parser import document_parser, EnterpriseDocumentParser
from packages.rag.vector_store import vector_store, ChromaVectorStore
from packages.rag.bm25 import BM25Retriever
from packages.rag.pipeline import rag_engine, AdvancedRAGEngine, RAGResponse, Citation, RetrievedChunk

__all__ = [
    "document_parser",
    "EnterpriseDocumentParser",
    "vector_store",
    "ChromaVectorStore",
    "BM25Retriever",
    "rag_engine",
    "AdvancedRAGEngine",
    "RAGResponse",
    "Citation",
    "RetrievedChunk",
]
