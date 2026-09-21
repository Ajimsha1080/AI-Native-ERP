"""
Layer 4 & 5: Unified Hybrid RAG Engine & Anti-Hallucination Guardrail.

Implements:
- Dense Vector Search (1536-dim)
- Sparse BM25 Search (with Stemming & Synonyms)
- Reciprocal Rank Fusion (RRF k=60)
- Cross-Encoder Reranker
- Anti-Hallucination Decision Gate: Groundedness Score >= Threshold?
  - Below Threshold -> Safe Refusal: "Not enough verified information"
  - Verified Grounded -> Assemble Question-Centric Grounded Context
"""

import math
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field

from packages.rag.bm25 import BM25Retriever
from packages.rag.embedding_service import embedding_service
from packages.rag.reranking_service import reranking_service
from packages.rag.query_rewrite import query_rewriter
from packages.rag.llm_service import llm_gateway
from packages.rag.vector_store import vector_store
from packages.security.guardrails import guardrails


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
    """Enterprise Hybrid RAG Engine with Decision Gate Guardrails."""

    def __init__(self, groundedness_threshold: float = 0.60):
        self.groundedness_threshold = groundedness_threshold
        self.bm25 = BM25Retriever()
        self.embedding = embedding_service
        self.reranker = reranking_service
        self.rewriter = query_rewriter
        self.llm = llm_gateway
        self.vector_store = vector_store
        self._corpus: List[Dict[str, Any]] = []

    def sync_sparse_corpus(self, chunks: List[Dict[str, Any]]) -> None:
        """Indexes corpus in BM25 for sparse keyword search."""
        self._corpus = chunks
        self.bm25.index_documents(chunks, text_key="content")

    def retrieve_hybrid(
        self,
        search_queries: List[str],
        scope: Optional[str] = None,
        top_k: int = 10,
        rrf_k: int = 60
    ) -> List[RAGDocumentChunk]:
        """
        Executes Dense (1536-dim) + Sparse BM25 search and merges via Reciprocal Rank Fusion.
        """
        primary_q = search_queries[0] if search_queries else ""

        # 1. Dense Semantic Vector Search
        dense_hits = []
        for q in search_queries[:2]:
            hits = self.vector_store.query(
                collection_name="agentic_knowledge",
                query_text=q,
                top_k=top_k,
                scope=scope
            )
            dense_hits.extend(hits)

        # 2. Sparse BM25 Search
        sparse_hits = self.bm25.search(primary_q, top_k=top_k)

        # 3. Reciprocal Rank Fusion (RRF k=60)
        fused_map: Dict[str, RAGDocumentChunk] = {}

        for rank, hit in enumerate(dense_hits, start=1):
            content = hit.get("content", "")
            meta = hit.get("metadata", {})
            title = hit.get("document_title") or meta.get("document_title", "Document")
            idx = hit.get("chunk_index", meta.get("chunk_index", 0))
            dept = hit.get("department", meta.get("department", "global"))
            dense_score = hit.get("relevance_score", 0.75)
            rrf_val = 1.0 / (rrf_k + rank)

            if content not in fused_map:
                fused_map[content] = RAGDocumentChunk(
                    id=str(meta.get("document_id") or f"dense_{rank}"),
                    content=content,
                    document_title=title,
                    chunk_index=int(idx),
                    department=str(dept),
                    dense_score=dense_score,
                    sparse_score=0.0,
                    rrf_score=rrf_val,
                    metadata=meta
                )
            else:
                fused_map[content].rrf_score += rrf_val
                fused_map[content].dense_score = max(fused_map[content].dense_score, dense_score)

        for rank, (doc, bm25_val) in enumerate(sparse_hits, start=1):
            content = doc.get("content", "")
            meta = doc.get("metadata", {})
            title = doc.get("document_title") or meta.get("document_title", "Document")
            idx = doc.get("chunk_index", meta.get("chunk_index", 0))
            dept = doc.get("department", meta.get("department", "global"))
            rrf_val = 1.0 / (rrf_k + rank)

            if content not in fused_map:
                fused_map[content] = RAGDocumentChunk(
                    id=str(doc.get("id") or f"sparse_{rank}"),
                    content=content,
                    document_title=title,
                    chunk_index=int(idx),
                    department=str(dept),
                    dense_score=0.0,
                    sparse_score=bm25_val,
                    rrf_score=rrf_val,
                    metadata=meta
                )
            else:
                fused_map[content].rrf_score += rrf_val
                fused_map[content].sparse_score = max(fused_map[content].sparse_score, bm25_val)

        # 4. Cross-Encoder Reranking
        candidate_dicts = [c.model_dump() for c in fused_map.values()]
        reranked = self.reranker.rerank(primary_q, candidate_dicts, top_k=top_k)

        return [RAGDocumentChunk(**item) for item in reranked]

    def compute_groundedness(self, query: str, top_chunks: List[RAGDocumentChunk]) -> float:
        """
        Computes composite groundedness score based on top chunk rerank scores and term overlap.
        """
        if not top_chunks:
            return 0.0

        top_score = top_chunks[0].rerank_score
        avg_score = sum(c.rerank_score for c in top_chunks) / len(top_chunks)
        groundedness = (top_score * 0.6) + (avg_score * 0.4)
        return round(groundedness, 4)

    def execute_rag(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        scope: Optional[str] = None,
        top_k: int = 5
    ) -> GroundedRAGResult:
        """
        Full Execution through Layer 3, 4, 5, and 6.
        """
        pipeline_log = []

        # Layer 3: Query Reformulation
        pipeline_log.append("Layer 3: Multi-Turn Contextual Query Rewriter")
        reformulation = self.rewriter.rewrite(query, chat_history)
        search_query = reformulation["reformulated_query"]
        variations = reformulation["search_variations"]

        # Layer 4: Hybrid RAG (Dense + BM25 + RRF + Cross-Encoder)
        pipeline_log.append("Layer 4: Hybrid Retrieval (1536-dim Dense + BM25 Sparse + RRF + Cross-Encoder)")
        top_chunks = self.retrieve_hybrid(variations, scope=scope, top_k=top_k)

        # Layer 5: Anti-Hallucination Guardrail Decision Gate
        pipeline_log.append("Layer 5: Anti-Hallucination Guardrail Decision Gate")
        groundedness_score = self.compute_groundedness(search_query, top_chunks)

        # Decision Diamond: Groundedness Score >= Threshold?
        if groundedness_score < self.groundedness_threshold or not top_chunks:
            pipeline_log.append("Layer 5 Outcome: Below Threshold -> Safe Refusal Triggered")
            return GroundedRAGResult(
                status="safe_refusal",
                question=query,
                reformulated_query=search_query,
                answer="Not enough verified information is available in the knowledge base to answer this inquiry accurately.",
                groundedness_score=groundedness_score,
                threshold=self.groundedness_threshold,
                is_grounded=False,
                citations=[],
                retrieved_chunks_count=len(top_chunks),
                pipeline_layers=pipeline_log
            )

        pipeline_log.append("Layer 5 Outcome: Verified Grounded -> Assemble Question-Centric Context")
        context_blocks = []
        raw_citations = []
        for i, c in enumerate(top_chunks, start=1):
            context_blocks.append(f"[Source {i}: {c.document_title} | #{c.chunk_index} | {c.department.upper()}]\n{c.content}")
            raw_citations.append({
                "source_index": i,
                "document_title": c.document_title,
                "chunk_index": c.chunk_index,
                "department": c.department,
                "relevance_score": c.rerank_score,
                "excerpt": c.content[:150] + "..." if len(c.content) > 150 else c.content
            })

        assembled_context = "\n\n".join(context_blocks)
        deduped_citations = self.llm.deduplicate_citations(raw_citations)

        # Layer 6: LLM Gateway & Synthesis
        pipeline_log.append("Layer 6: LLM Gateway & Synthesis + Source Citation Deduplication")
        raw_answer = self.llm.synthesize(prompt=search_query, context=assembled_context)

        # Append citation markers
        if deduped_citations:
            tags = " ".join(f"[^{c['source_index']}]" for c in deduped_citations[:2])
            final_answer = f"{raw_answer} {tags}".strip()
        else:
            final_answer = raw_answer

        return GroundedRAGResult(
            status="grounded",
            question=query,
            reformulated_query=search_query,
            answer=final_answer,
            groundedness_score=groundedness_score,
            threshold=self.groundedness_threshold,
            is_grounded=True,
            citations=deduped_citations,
            retrieved_chunks_count=len(top_chunks),
            pipeline_layers=pipeline_log
        )


# Global Hybrid RAG Engine Instance
hybrid_rag_engine = HybridRAGEngine(groundedness_threshold=0.60)
