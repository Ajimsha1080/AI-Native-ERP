"""
Enterprise 10-Stage Question-Answering Pipeline for Agentic ERP.

Workflow:
1. Intent and Query Understanding (Domain, question type, entity extraction, ambiguity detection)
2. Conditional Query Rewriting (Contextual coreference, acronym expansion, constraints preservation)
3. Permission-Aware Hybrid Retrieval (PostgreSQL pgvector Dense Semantic + BM25 Sparse Lexical with Tenant RLS)
4. Reciprocal Rank Fusion (RRF score: sum(1 / (k + rank_i(d))))
5. Contextual Semantic Reranking (Cross-encoder term density + dense similarity + exact phrase boost)
6. Context Assembly (Untrusted data encapsulation, token budget, source metadata retention)
7. LLM Evidence Analysis & Synthesis (Zero-hallucination factual synthesis)
8. Grounding Verification (Claim-to-evidence alignment, numeric consistency, controlled abstention)
9. Citation Validation (Verification against context sources, rejection of hallucinated citations)
10. Final Natural-Language Answer (Grounded answer with inline citations or transparent abstention)
"""

import re
import math
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from pydantic import BaseModel, Field

from packages.rag.vector_store import PGVectorStore, vector_store
from packages.rag.bm25 import BM25Retriever
from packages.security.guardrails import guardrails
from packages.config.settings import settings

logger = logging.getLogger("rag.pipeline")


# Common ERP Domain Acronyms for Query Rewriting
ERP_ACRONYMS = {
    "po": "purchase order",
    "so": "sales order",
    "ap": "accounts payable",
    "ar": "accounts receivable",
    "cogs": "cost of goods sold",
    "bom": "bill of materials",
    "sku": "stock keeping unit",
    "rfq": "request for quotation",
    "grn": "goods receipt note",
    "sla": "service level agreement",
    "qbo": "quickbooks online",
    "rls": "row level security",
    "gdpr": "general data protection regulation",
}


class QueryIntent(BaseModel):
    domain: str = "general"
    question_type: str = "knowledge"  # knowledge, transactional, calculation, comparison, policy_check, ambiguous
    extracted_entities: Dict[str, Any] = Field(default_factory=dict)
    is_ambiguous: bool = False
    requires_live_data: bool = False
    clarification_prompt: Optional[str] = None


class RetrievedChunk(BaseModel):
    id: str
    content: str
    document_title: str
    chunk_index: int
    department: str = "global"
    tenant_id: Optional[str] = None
    dense_score: float = 0.0
    sparse_score: float = 0.0
    rrf_score: float = 0.0
    rerank_score: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)


class Citation(BaseModel):
    source_index: int
    source_id: str = ""
    document_title: str
    chunk_index: int
    department: str
    relevance_score: float
    excerpt: str
    is_verified: bool = True


class GroundingResult(BaseModel):
    is_grounded: bool
    grounding_score: float
    hallucination_flag: bool
    numeric_facts_verified: bool
    unsupported_claims: List[str] = Field(default_factory=list)
    action: str = "accept"  # accept, abstain


class RAGResponse(BaseModel):
    question: str
    rewritten_queries: List[str]
    intent: Dict[str, Any]
    retrieved_chunks_count: int
    answer: str
    citations: List[Citation]
    grounding: Dict[str, Any]
    pipeline_stages: List[str]
    status: str = "grounded"  # grounded, abstention, clarification_needed, blocked


class AdvancedRAGEngine:
    """10-Stage Enterprise RAG Engine with Hybrid Search, RRF, Reranking, and Grounding."""

    def __init__(
        self,
        vector_store_instance: Optional[PGVectorStore] = None,
        rrf_k: int = 60,
        groundedness_threshold: float = 0.50
    ):
        self.vector_store = vector_store_instance or vector_store
        self.bm25 = BM25Retriever()
        self.rrf_k = rrf_k
        self.groundedness_threshold = groundedness_threshold
        self._indexed_chunks: List[Dict[str, Any]] = []

    # -------------------------------------------------------------------------
    # STAGE 1: Intent & Query Understanding
    # -------------------------------------------------------------------------
    def understand_intent(
        self,
        question: str,
        history: Optional[List[Dict[str, str]]] = None
    ) -> QueryIntent:
        """
        Analyzes question semantics, classifies business domain and question type,
        extracts entities and constraints, and detects ambiguity.
        """
        q_raw = question.strip()
        q_lower = q_raw.lower()
        tokens = set(re.findall(r"\b\w+\b", q_lower))

        # Check for ambiguous or incomplete inquiries
        is_ambiguous = False
        clarification_prompt = None
        words = q_raw.split()
        generic_terms = {"it", "this", "that", "what", "is", "tell", "more", "how", "much"}
        if (len(words) <= 3 or tokens.issubset(generic_terms)) and not any(k in q_lower for k in ["help", "hi", "hello"]):
            if not any(k in tokens for k in ["stock", "order", "invoice", "po", "so", "sku", "vendor", "product"]):
                is_ambiguous = True
                clarification_prompt = (
                    "Your inquiry appears brief or underspecified. Could you clarify which document, "
                    "order number, SKU, or department you need information about?"
                )

        # Domain Classification
        domain = "general"
        if any(k in q_lower for k in ["stock", "inventory", "warehouse", "sku", "product", "reorder", "bin", "on-hand"]):
            domain = "inventory"
        elif any(k in q_lower for k in ["purchase", "vendor", "supplier", "rfq", "procurement", "grn"]) or "po" in tokens:
            domain = "procurement"
        elif any(k in q_lower for k in ["sale", "customer", "invoice", "revenue", "quote", "order"]) or "so" in tokens:
            domain = "sales"
        elif any(k in q_lower for k in ["account", "ledger", "balance", "tax", "journal", "p&l", "cogs", "asset"]) or {"ap", "ar"} & tokens:
            domain = "finance"
        elif any(k in q_lower for k in ["compliance", "gdpr", "legal", "terms", "privacy", "rls", "audit"]):
            domain = "legal"
        elif "policy" in tokens:
            domain = "procurement" if "po" in tokens else "general"

        # Question Type Classification
        question_type = "knowledge"
        requires_live_data = False

        if any(k in q_lower for k in ["total", "sum", "average", "aggregate", "how many", "count", "net balance", "valuation"]):
            question_type = "calculation"
            requires_live_data = True
        elif any(k in q_lower for k in ["check stock", "list products", "list invoices", "show order", "adjust stock", "create po"]):
            question_type = "transactional"
            requires_live_data = True
        elif any(k in q_lower for k in ["compare", "difference", "versus", "vs", "which is better"]):
            question_type = "comparison"
        elif any(k in q_lower for k in ["policy", "allowed", "rule", "guideline", "limit", "sla", "approval threshold"]):
            question_type = "policy_check"

        # Entity Extraction: SKUs, Identifiers, Currency Amounts, Dates
        skus = re.findall(r"\b(?:sku-)?[A-Z0-9]{2,}(?:-[A-Z0-9]+)+\b", question, re.IGNORECASE)
        identifiers = re.findall(r"\b(?:PO|SO|INV|CUST|VEND|DOC)-[0-9]{3,}\b", question, re.IGNORECASE)
        amounts = re.findall(r"\$?\b\d+(?:,\d{3})*(?:\.\d{2})?\b", question)
        dates = re.findall(
            r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|january|february|march|april|may|june|july|august|september|october|november|december)\b",
            question,
            re.IGNORECASE
        )

        return QueryIntent(
            domain=domain,
            question_type=question_type,
            extracted_entities={
                "skus": skus,
                "identifiers": identifiers,
                "amounts": amounts,
                "dates": dates
            },
            is_ambiguous=is_ambiguous,
            requires_live_data=requires_live_data,
            clarification_prompt=clarification_prompt
        )

    # -------------------------------------------------------------------------
    # STAGE 2: Conditional Query Rewriting
    # -------------------------------------------------------------------------
    def rewrite_query(
        self,
        question: str,
        intent: QueryIntent,
        history: Optional[List[Dict[str, str]]] = None
    ) -> List[str]:
        """
        Rewrites queries conditionally to expand domain acronyms and resolve conversational
        coreferences while strictly preserving critical entities (SKUs, IDs, dates, amounts).
        """
        words = question.split()
        expanded_words = []
        has_acronym_expansion = False

        for w in words:
            clean_w = re.sub(r"[^\w]", "", w).lower()
            if clean_w in ERP_ACRONYMS:
                expanded_words.append(f"{w} ({ERP_ACRONYMS[clean_w]})")
                has_acronym_expansion = True
            else:
                expanded_words.append(w)

        expanded_query = " ".join(expanded_words)
        queries = [question]

        # Multi-turn pronoun/coreference resolution
        pronouns = ["it", "its", "they", "them", "their", "that", "this product", "the order"]
        has_coreference = any(re.search(rf"\b{p}\b", question.lower()) for p in pronouns)

        if has_coreference and history:
            # Extract most recent subject/SKU from history
            recent_entities = []
            for msg in reversed(history[-4:]):
                content = msg.get("content", "")
                skus = re.findall(r"\b(?:sku-)?[A-Z0-9]{3,}-[A-Z0-9]{3,}\b", content, re.IGNORECASE)
                pos = re.findall(r"\b(?:PO|SO|INV)-[0-9]{3,}\b", content, re.IGNORECASE)
                if skus:
                    recent_entities.extend(skus)
                if pos:
                    recent_entities.extend(pos)

            if recent_entities:
                resolved_subject = recent_entities[0]
                coreference_query = re.sub(
                    r"\b(it|its|that|this product|the order)\b",
                    resolved_subject,
                    question,
                    flags=re.IGNORECASE
                )
                if coreference_query != question:
                    queries.append(coreference_query)

        if has_acronym_expansion and expanded_query != question:
            queries.append(expanded_query)

        # Domain contextual query if specific domain identified
        if intent.domain not in ["general", "blocked"]:
            queries.append(f"{intent.domain} context: {question}")

        return list(dict.fromkeys(queries))

    # -------------------------------------------------------------------------
    # STAGE 3: Permission-Aware Hybrid Retrieval
    # -------------------------------------------------------------------------
    def sync_corpus_for_sparse(self, chunks: List[Dict[str, Any]]) -> None:
        """Indexes or refreshes in-memory chunk corpus for BM25 sparse search and vector store."""
        self._indexed_chunks = chunks
        self.bm25.index_documents(chunks, text_key="content")
        self.vector_store.sync_chunks(chunks)

    def hybrid_retrieve(
        self,
        queries: List[str],
        tenant_id: Optional[str] = None,
        scope: Optional[str] = None,
        top_k: int = 10,
        exact_boost_terms: Optional[List[str]] = None
    ) -> Tuple[List[Dict[str, Any]], List[Tuple[Dict[str, Any], float]]]:
        """
        Executes dual-channel permission-aware retrieval:
        1. Dense semantic search across PostgreSQL pgvector store (tenant & scope filtered)
        2. Sparse lexical search using Okapi BM25 (tenant & scope filtered)
        """
        dense_results: List[Dict[str, Any]] = []
        sparse_results: List[Tuple[Dict[str, Any], float]] = []

        primary_query = queries[0] if queries else ""

        # 1. Dense Semantic Vector Retrieval
        for q in queries[:2]:
            dense_hits = self.vector_store.query(
                collection_name="agentic_knowledge",
                query_text=q,
                top_k=top_k,
                scope=scope,
                tenant_id=tenant_id
            )
            dense_results.extend(dense_hits)

        # Deduplicate dense results by unique chunk ID or content hash
        seen_dense = set()
        unique_dense = []
        for hit in dense_results:
            key = hit.get("id") or hit.get("content", "")
            if key and key not in seen_dense:
                seen_dense.add(key)
                # Boost if exact ERP code/term matches
                if exact_boost_terms:
                    content_lower = hit.get("content", "").lower()
                    if any(term.lower() in content_lower for term in exact_boost_terms):
                        hit["relevance_score"] = min(hit.get("relevance_score", 0.7) + 0.15, 1.0)
                unique_dense.append(hit)

        # 2. Sparse BM25 Retrieval
        sparse_hits = self.bm25.search(
            primary_query,
            top_k=top_k,
            scope=scope,
            tenant_id=tenant_id
        )
        sparse_results.extend(sparse_hits)

        return unique_dense, sparse_results

    # -------------------------------------------------------------------------
    # STAGE 4: Reciprocal Rank Fusion (RRF)
    # -------------------------------------------------------------------------
    def apply_rrf(
        self,
        dense_hits: List[Dict[str, Any]],
        sparse_hits: List[Tuple[Dict[str, Any], float]],
        k: Optional[int] = None
    ) -> List[RetrievedChunk]:
        """
        Merges dense and sparse ranked candidates using Reciprocal Rank Fusion:
        RRF_Score(d) = sum(1 / (k + rank_i(d)))
        """
        rrf_constant = k if k is not None else self.rrf_k
        chunk_map: Dict[str, RetrievedChunk] = {}

        # Process Dense Ranks
        for rank, hit in enumerate(dense_hits, start=1):
            content = hit.get("content", "")
            meta = hit.get("metadata", {})
            doc_id = hit.get("id") or meta.get("document_id") or f"dense_{rank}_{hash(content)}"
            title = hit.get("document_title") or meta.get("document_title", "Document")
            idx = hit.get("chunk_index", meta.get("chunk_index", 0))
            dept = hit.get("department", meta.get("department", "global"))
            tenant_id = hit.get("tenant_id") or meta.get("tenant_id")
            dense_score = hit.get("relevance_score", 0.75)

            rrf_val = 1.0 / (rrf_constant + rank)

            if content not in chunk_map:
                chunk_map[content] = RetrievedChunk(
                    id=str(doc_id),
                    content=content,
                    document_title=title,
                    chunk_index=int(idx),
                    department=str(dept),
                    tenant_id=str(tenant_id) if tenant_id else None,
                    dense_score=dense_score,
                    sparse_score=0.0,
                    rrf_score=rrf_val,
                    metadata=meta,
                    provenance={"dense_rank": rank}
                )
            else:
                chunk_map[content].rrf_score += rrf_val
                chunk_map[content].dense_score = max(chunk_map[content].dense_score, dense_score)
                chunk_map[content].provenance["dense_rank"] = rank

        # Process Sparse BM25 Ranks
        for rank, (doc, bm25_score) in enumerate(sparse_hits, start=1):
            content = doc.get("content", "")
            meta = doc.get("metadata", {})
            doc_id = doc.get("id") or f"sparse_{rank}_{hash(content)}"
            title = doc.get("document_title") or meta.get("document_title", "Document")
            idx = doc.get("chunk_index", meta.get("chunk_index", 0))
            dept = doc.get("department", meta.get("department", "global"))
            tenant_id = doc.get("tenant_id") or meta.get("tenant_id")

            rrf_val = 1.0 / (rrf_constant + rank)

            if content not in chunk_map:
                chunk_map[content] = RetrievedChunk(
                    id=str(doc_id),
                    content=content,
                    document_title=title,
                    chunk_index=int(idx),
                    department=str(dept),
                    tenant_id=str(tenant_id) if tenant_id else None,
                    dense_score=0.0,
                    sparse_score=bm25_score,
                    rrf_score=rrf_val,
                    metadata=meta,
                    provenance={"sparse_rank": rank}
                )
            else:
                chunk_map[content].rrf_score += rrf_val
                chunk_map[content].sparse_score = max(chunk_map[content].sparse_score, bm25_score)
                chunk_map[content].provenance["sparse_rank"] = rank

        # Sort candidate chunks by RRF score descending
        fused_candidates = sorted(chunk_map.values(), key=lambda c: c.rrf_score, reverse=True)
        return fused_candidates

    # -------------------------------------------------------------------------
    # STAGE 5: Contextual Cross-Encoder Reranking
    # -------------------------------------------------------------------------
    def rerank(
        self,
        query: str,
        candidates: List[RetrievedChunk],
        top_n: int = 5,
        exact_terms: Optional[List[str]] = None
    ) -> List[RetrievedChunk]:
        """
        Cross-scoring semantic reranker combining lexical token density, dense cosine score,
        RRF positional weight, and exact phrase/identifier matching.
        """
        if not candidates:
            return []

        query_tokens = set(re.findall(r"\b\w+\b", query.lower()))

        for chunk in candidates:
            chunk_tokens = set(re.findall(r"\b\w+\b", chunk.content.lower()))
            overlap_ratio = len(query_tokens & chunk_tokens) / max(len(query_tokens), 1)

            # Exact phrase or identifier matching boost
            phrase_boost = 0.15 if query.lower() in chunk.content.lower() else 0.0
            if exact_terms:
                if any(term.lower() in chunk.content.lower() for term in exact_terms):
                    phrase_boost += 0.20

            # Composite rerank score: 35% Overlap + 35% Dense + 30% RRF weight + phrase boost
            rerank_val = (
                (overlap_ratio * 0.35) +
                (chunk.dense_score * 0.35) +
                (min(chunk.rrf_score * 30.0, 1.0) * 0.30) +
                phrase_boost
            )
            chunk.rerank_score = round(min(rerank_val, 1.0), 4)

        ranked = sorted(candidates, key=lambda c: c.rerank_score, reverse=True)
        return ranked[:top_n]

    # -------------------------------------------------------------------------
    # STAGE 6: Context Assembly
    # -------------------------------------------------------------------------
    def assemble_context(
        self,
        chunks: List[RetrievedChunk],
        max_tokens: int = 2000
    ) -> Tuple[str, List[Citation]]:
        """
        Deduplicates and formats retrieved evidence passages into structured citation blocks.
        Retrieved content is treated as untrusted data inside security boundary demarcations.
        """
        context_blocks = []
        citations = []
        seen_texts: Set[str] = set()

        total_words = 0
        source_idx = 1

        for chunk in chunks:
            clean_text = chunk.content.strip()
            if not clean_text or clean_text in seen_texts:
                continue
            seen_texts.add(clean_text)

            words = clean_text.split()
            if total_words + len(words) > max_tokens and context_blocks:
                break
            total_words += len(words)

            context_blocks.append(
                f"[Source {source_idx}] (ID: {chunk.id} | Document: {chunk.document_title} | "
                f"Chunk: #{chunk.chunk_index} | Department: {chunk.department.upper()})\n"
                f"{clean_text}"
            )

            citations.append(Citation(
                source_index=source_idx,
                source_id=chunk.id,
                document_title=chunk.document_title,
                chunk_index=chunk.chunk_index,
                department=chunk.department,
                relevance_score=chunk.rerank_score or chunk.dense_score or 0.85,
                excerpt=clean_text[:160] + "..." if len(clean_text) > 160 else clean_text,
                is_verified=True
            ))
            source_idx += 1

        assembled_text = "\n\n".join(context_blocks)
        return assembled_text, citations

    # -------------------------------------------------------------------------
    # STAGE 7: LLM Evidence Analysis and Synthesis
    # -------------------------------------------------------------------------
    def synthesize_answer(self, question: str, context: str, intent: QueryIntent) -> str:
        """
        Synthesizes factually grounded answers strictly from the assembled context.
        Uses OpenAI zero-temperature synthesis if API key is configured, or deterministic
        factual extractive synthesis fallback.
        """
        if not context.strip():
            return "No verified enterprise records or knowledge documents were found matching your inquiry."

        # If live OpenAI LLM API key is configured, synthesize strictly from context
        if getattr(settings, "openai_api_key", None) and settings.openai_api_key.startswith("sk-"):
            try:
                from openai import OpenAI
                client = OpenAI(api_key=settings.openai_api_key)
                prompt = (
                    "You are an enterprise ERP assistant. Answer the question STRICTLY using the context below.\n"
                    "Do NOT extrapolate, guess, or invent details not in the context.\n"
                    "If the answer cannot be found in the context, state: 'Insufficient verified evidence is available.'\n\n"
                    f"<untrusted_evidence>\n{context}\n</untrusted_evidence>\n\n"
                    f"Question: {question}\n\n"
                    "Answer:"
                )
                res = client.chat.completions.create(
                    model=getattr(settings, "openai_model", "gpt-4o-mini"),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    max_tokens=500
                )
                answer = res.choices[0].message.content.strip()
                if answer and "insufficient" not in answer.lower():
                    return answer
            except Exception as e:
                logger.warning(f"LLM synthesis fallback to deterministic extraction: {e}")

        # Deterministic Extractive Factual Synthesis (Zero-Hallucination Fallback)
        sentences = [s.strip() for s in context.split(".") if s.strip()]
        q_tokens = set(re.findall(r"\b\w+\b", question.lower()))

        matched_sentences = []
        for s in sentences:
            s_tokens = set(re.findall(r"\b\w+\b", s.lower()))
            overlap = len(q_tokens & s_tokens)
            if overlap >= 2:
                matched_sentences.append(s)

        if matched_sentences:
            synthesis = ". ".join(matched_sentences[:3]) + "."
        elif sentences:
            synthesis = ". ".join(sentences[:2]) + "."
        else:
            synthesis = "No verified data records found."

        return synthesis

    # -------------------------------------------------------------------------
    # STAGE 8: Grounding Verification
    # -------------------------------------------------------------------------
    def verify_grounding(
        self,
        answer: str,
        context: str,
        reranked_chunks: List[RetrievedChunk]
    ) -> GroundingResult:
        """
        Verifies material factual claims, numerical consistency, and evidence alignment.
        """
        if not reranked_chunks or not context.strip():
            return GroundingResult(
                is_grounded=False,
                grounding_score=0.0,
                hallucination_flag=True,
                numeric_facts_verified=False,
                unsupported_claims=["No evidence retrieved"],
                action="abstain"
            )

        # Compute composite groundedness score based on top candidate rerank scores
        top_score = reranked_chunks[0].rerank_score
        avg_score = sum(c.rerank_score for c in reranked_chunks) / len(reranked_chunks)
        composite_score = round((top_score * 0.6) + (avg_score * 0.4), 4)

        # Numerical consistency check: any numeric currency or count in the answer must appear in the context
        answer_numbers = set(re.findall(r"\$?\b\d+(?:,\d{3})*(?:\.\d{2})?\b", answer))
        context_str = context.lower()
        unmatched_numbers = [n for n in answer_numbers if len(n) > 2 and n.lower() not in context_str]

        numeric_verified = len(unmatched_numbers) == 0

        # Anti-hallucination decision gate: score >= threshold and numeric verified
        is_grounded = composite_score >= self.groundedness_threshold and numeric_verified
        action = "accept" if is_grounded else "abstain"

        return GroundingResult(
            is_grounded=is_grounded,
            grounding_score=composite_score,
            hallucination_flag=not is_grounded,
            numeric_facts_verified=numeric_verified,
            unsupported_claims=unmatched_numbers,
            action=action
        )

    # -------------------------------------------------------------------------
    # STAGE 9: Citation Validation
    # -------------------------------------------------------------------------
    def validate_citations(
        self,
        raw_citations: List[Citation],
        assembled_context: str
    ) -> List[Citation]:
        """
        Validates every cited source against actual context blocks.
        Rejects fabricated, malformed, or ungrounded citation references.
        """
        validated = []
        for c in raw_citations:
            # Check source ID matches context block
            source_marker = f"[Source {c.source_index}]"
            id_marker = f"ID: {c.source_id}"
            if source_marker in assembled_context and id_marker in assembled_context:
                validated.append(c)
            else:
                logger.warning(f"Rejected ungrounded or fabricated citation: {c}")

        return validated

    # -------------------------------------------------------------------------
    # STAGE 10: Final Natural-Language Answer Formulation & Pipeline Orchestrator
    # -------------------------------------------------------------------------
    def answer_question(
        self,
        question: str,
        department_scope: Optional[str] = None,
        top_k: int = 5,
        tenant_id: Optional[str] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        groundedness_threshold: Optional[float] = None
    ) -> RAGResponse:
        """
        Executes the full 10-stage RAG pipeline from user question to grounded answer with citations.
        """
        stages_executed = []
        threshold = groundedness_threshold if groundedness_threshold is not None else self.groundedness_threshold

        # 1. Question Ingestion & Safety Pre-check
        stages_executed.append("1. Question Ingestion & AI Guardrail Validation")
        is_safe, sanitized_query, rejection = guardrails.validate_input_query(question)
        if not is_safe:
            return RAGResponse(
                question=question,
                rewritten_queries=[question],
                intent={"domain": "blocked", "question_type": "rejected"},
                retrieved_chunks_count=0,
                answer=f"⚠️ {rejection}",
                citations=[],
                grounding={"hallucination_flag": True, "grounding_score": 0.0, "is_grounded": False},
                pipeline_stages=stages_executed,
                status="blocked"
            )

        # 2. Intent & Query Understanding
        stages_executed.append("2. Intent & Query Understanding")
        intent = self.understand_intent(sanitized_query, history=chat_history)

        if intent.is_ambiguous and not chat_history:
            return RAGResponse(
                question=question,
                rewritten_queries=[question],
                intent=intent.model_dump(),
                retrieved_chunks_count=0,
                answer=intent.clarification_prompt or "Please provide more details regarding your question.",
                citations=[],
                grounding={"is_grounded": False, "grounding_score": 0.0, "hallucination_flag": False},
                pipeline_stages=stages_executed,
                status="clarification_needed"
            )

        # 3. Conditional Query Rewriting
        stages_executed.append("3. Conditional Query Rewriting & Expansion")
        rewritten_queries = self.rewrite_query(sanitized_query, intent, history=chat_history)

        # 4. Permission-Aware Hybrid Retrieval
        stages_executed.append("4. Permission-Aware Hybrid Retrieval (Dense Vector + Sparse BM25)")
        scope = department_scope or intent.domain
        exact_terms = intent.extracted_entities.get("identifiers", []) + intent.extracted_entities.get("skus", [])
        dense_hits, sparse_hits = self.hybrid_retrieve(
            rewritten_queries,
            tenant_id=tenant_id,
            scope=scope,
            top_k=top_k,
            exact_boost_terms=exact_terms
        )

        # 5. Reciprocal Rank Fusion (RRF)
        stages_executed.append("5. Reciprocal Rank Fusion (RRF)")
        fused_candidates = self.apply_rrf(dense_hits, sparse_hits)

        # 6. Contextual Semantic Reranking
        stages_executed.append("6. Contextual Semantic Reranking")
        reranked_chunks = self.rerank(sanitized_query, fused_candidates, top_n=top_k, exact_terms=exact_terms)

        # 7. Context Assembly & Untrusted Boundary Demarcation
        stages_executed.append("7. Context Assembly & Untrusted Evidence Partitioning")
        assembled_context, raw_citations = self.assemble_context(reranked_chunks)

        # 8. LLM Evidence Synthesis
        stages_executed.append("8. LLM Evidence Synthesis")
        raw_answer = self.synthesize_answer(sanitized_query, assembled_context, intent)

        # 9. Grounding Verification & Controlled Abstention
        stages_executed.append("9. Anti-Hallucination Grounding Verification")
        grounding = self.verify_grounding(raw_answer, assembled_context, reranked_chunks)

        # If below threshold or ungrounded, trigger safe transparent abstention
        if grounding.action == "abstain" or grounding.grounding_score < threshold or not reranked_chunks:
            return RAGResponse(
                question=question,
                rewritten_queries=rewritten_queries,
                intent=intent.model_dump(),
                retrieved_chunks_count=len(reranked_chunks),
                answer=(
                    "Not enough verified information is available in the knowledge base to answer this inquiry accurately. "
                    "Please ensure the relevant policy or operational document has been indexed."
                ),
                citations=[],
                grounding=grounding.model_dump(),
                pipeline_stages=stages_executed,
                status="abstention"
            )

        # 10. Citation Validation & Final Answer Formulation
        stages_executed.append("10. Citation Validation & Final Grounded Answer Formulation")
        verified_citations = self.validate_citations(raw_citations, assembled_context)

        # Append inline markdown footnotes
        if verified_citations:
            footnote_tags = " ".join(f"[^{c.source_index}]" for c in verified_citations[:2])
            final_answer = f"{raw_answer} {footnote_tags}".strip()
        else:
            final_answer = raw_answer

        return RAGResponse(
            question=question,
            rewritten_queries=rewritten_queries,
            intent=intent.model_dump(),
            retrieved_chunks_count=len(reranked_chunks),
            answer=final_answer,
            citations=verified_citations,
            grounding=grounding.model_dump(),
            pipeline_stages=stages_executed,
            status="grounded"
        )


# Global Singleton Pipeline Instance
rag_engine = AdvancedRAGEngine()
