"""
Unified Hybrid RAG Engine & Anti-Hallucination Guardrail Integration.

Wraps the 10-stage Enterprise RAG Pipeline (packages.rag.pipeline)
to provide backward-compatible interfaces for agent runtime and chat services.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from packages.rag.pipeline import rag_engine, AdvancedRAGEngine, RAGResponse, RetrievedChunk
from packages.rag.bm25 import BM25Retriever
from packages.rag.embedding_service import embedding_service
from packages.rag.reranking_service import reranking_service
from packages.rag.query_rewrite import query_rewriter
from packages.rag.llm_service import llm_gateway
from packages.rag.vector_store import vector_store


class RAGDocumentChunk(BaseModel):
    id: str
    content: str
    document_title: str
    chunk_index: int
    department: str = "global"
    dense_score: float = 0.0
    sparse_score: float = 0.0
    rrf_score: float = 0.0
    rerank_score: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GroundedRAGResult(BaseModel):
    status: str  # "grounded", "safe_refusal", "blocked"
    question: str
    reformulated_query: str
    answer: str
    groundedness_score: float
    threshold: float
    is_grounded: bool
    citations: List[Dict[str, Any]]
    retrieved_chunks_count: int
    pipeline_layers: List[str]


class HybridRAGEngine:
    """Enterprise Hybrid RAG Engine integrating the 10-stage architecture."""

    def __init__(self, groundedness_threshold: float = 0.50):
        self.groundedness_threshold = groundedness_threshold
        self.pipeline: AdvancedRAGEngine = rag_engine
        self.bm25 = self.pipeline.bm25
        self.embedding = embedding_service
        self.reranker = reranking_service
        self.rewriter = query_rewriter
        self.llm = llm_gateway
        self.vector_store = self.pipeline.vector_store

    def sync_sparse_corpus(self, chunks: List[Dict[str, Any]]) -> None:
        """Indexes corpus in BM25 and vector store for search."""
        self.pipeline.sync_corpus_for_sparse(chunks)

    def retrieve_hybrid(
        self,
        search_queries: List[str],
        scope: Optional[str] = None,
        top_k: int = 10,
        rrf_k: int = 60,
        tenant_id: Optional[str] = None
    ) -> List[RAGDocumentChunk]:
        """
        Executes Dense + Sparse BM25 search merged via Reciprocal Rank Fusion.
        """
        dense_hits, sparse_hits = self.pipeline.hybrid_retrieve(
            queries=search_queries,
            tenant_id=tenant_id,
            scope=scope,
            top_k=top_k
        )
        fused = self.pipeline.apply_rrf(dense_hits, sparse_hits, k=rrf_k)
        reranked = self.pipeline.rerank(search_queries[0] if search_queries else "", fused, top_n=top_k)
        return [
            RAGDocumentChunk(
                id=c.id,
                content=c.content,
                document_title=c.document_title,
                chunk_index=c.chunk_index,
                department=c.department,
                dense_score=c.dense_score,
                sparse_score=c.sparse_score,
                rrf_score=c.rrf_score,
                rerank_score=c.rerank_score,
                metadata=c.metadata
            )
            for c in reranked
        ]

    def compute_groundedness(self, query: str, top_chunks: List[Any]) -> float:
        """
        Computes composite groundedness score.
        """
        if not top_chunks:
            return 0.0
        scores = [getattr(c, "rerank_score", 0.0) for c in top_chunks]
        top_score = scores[0]
        avg_score = sum(scores) / len(scores)
        return round((top_score * 0.6) + (avg_score * 0.4), 4)

    def execute_rag(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        scope: Optional[str] = None,
        top_k: int = 5,
        organization_id: Optional[Any] = None
    ) -> GroundedRAGResult:
        """
        Full Execution through the unified 10-stage RAG Pipeline.
        """
        tenant_str = str(organization_id) if organization_id else None
        res: RAGResponse = self.pipeline.answer_question(
            question=query,
            department_scope=scope,
            top_k=top_k,
            tenant_id=tenant_str,
            chat_history=chat_history,
            groundedness_threshold=self.groundedness_threshold
        )

        # Map response status
        if res.status == "blocked":
            status = "blocked"
        elif res.status in ["abstention", "clarification_needed"]:
            status = "safe_refusal"
        else:
            status = "grounded"

        grounding_info = res.grounding or {}
        groundedness_val = float(grounding_info.get("grounding_score", 0.0))
        is_grounded = bool(grounding_info.get("is_grounded", False))

        primary_reformulated = res.rewritten_queries[1] if len(res.rewritten_queries) > 1 else (res.rewritten_queries[0] if res.rewritten_queries else query)

        return GroundedRAGResult(
            status=status,
            question=query,
            reformulated_query=primary_reformulated,
            answer=res.answer,
            groundedness_score=groundedness_val,
            threshold=self.groundedness_threshold,
            is_grounded=is_grounded,
            citations=[c.model_dump() for c in res.citations],
            retrieved_chunks_count=res.retrieved_chunks_count,
            pipeline_layers=res.pipeline_stages
        )


# Global Hybrid RAG Engine Instance
hybrid_rag_engine = HybridRAGEngine(groundedness_threshold=0.50)
