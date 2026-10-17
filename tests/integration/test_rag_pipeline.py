"""
Enterprise Integration Tests for the 10-Stage Question-Answering Pipeline & ERP Routing.

Covers:
1. Intent & Query Understanding (domain, question_type, entity extraction, ambiguity)
2. Conditional Query Rewriting (acronyms, coreference resolution, entity preservation)
3. Permission-Aware Hybrid Retrieval & Multi-Tenant Isolation
4. Reciprocal Rank Fusion (RRF formula, provenance, deduplication)
5. Contextual Semantic Reranking
6. Context Assembly & Untrusted Boundary Demarcation
7. Anti-Hallucination Grounding Verification & Numerical Check
8. Controlled Abstention on Insufficient Evidence
9. Citation Validation & Hallucinated Citation Rejection
10. Final Natural-Language Answer Formulation with Citations
11. ERP 5-Way Intent Routing (Calculation, Transactional, Greeting, Escalation, RAG)
"""

import pytest
import uuid
from typing import Dict, Any, List

from packages.rag.pipeline import AdvancedRAGEngine, rag_engine, Citation, RetrievedChunk, RAGResponse, QueryIntent
from packages.rag.rag_engine import hybrid_rag_engine, GroundedRAGResult
from packages.rag.vector_store import PGVectorStore
from packages.rag.bm25 import BM25Retriever
from packages.agents.agent_runtime import agent_runtime, AgentRuntimeResponse


# ─────────────────────────────────────────────────────────────────────────────
# 1. STAGE 1 & 2: INTENT UNDERSTANDING & CONDITIONAL REWRITING
# ─────────────────────────────────────────────────────────────────────────────

def test_intent_understanding_domains_and_entities():
    engine = AdvancedRAGEngine()
    
    # Inventory inquiry with SKU
    q1 = "What is the reorder policy for SKU-9840-X1 in the warehouse?"
    intent1 = engine.understand_intent(q1)
    assert intent1.domain == "inventory"
    assert intent1.question_type == "policy_check"
    assert "SKU-9840-X1" in intent1.extracted_entities["skus"]
    assert not intent1.is_ambiguous

    # Procurement inquiry with PO and Amount
    q2 = "Approve PO-88301 for $14,500.00 dated 2026-08-15"
    intent2 = engine.understand_intent(q2)
    assert intent2.domain == "procurement"
    assert "PO-88301" in intent2.extracted_entities["identifiers"]
    assert any("14,500.00" in a for a in intent2.extracted_entities["amounts"])
    assert "2026-08-15" in intent2.extracted_entities["dates"]

    # Calculation inquiry
    q3 = "Calculate total inventory valuation and average price"
    intent3 = engine.understand_intent(q3)
    assert intent3.question_type == "calculation"
    assert intent3.requires_live_data is True

    # Ambiguous inquiry
    q4 = "what is it?"
    intent4 = engine.understand_intent(q4)
    assert intent4.is_ambiguous is True
    assert intent4.clarification_prompt is not None


def test_conditional_query_rewriting():
    engine = AdvancedRAGEngine()

    # Acronym expansion without changing numbers
    intent = engine.understand_intent("What is the PO limit for vendor ABC?")
    rewritten = engine.rewrite_query("What is the PO limit for vendor ABC?", intent)
    assert len(rewritten) >= 1
    # Original query must always be preserved
    assert rewritten[0] == "What is the PO limit for vendor ABC?"
    # Expanded query should contain purchase order
    assert any("purchase order" in q for q in rewritten)

    # Coreference resolution using conversational history
    history = [
        {"role": "user", "content": "I am reviewing product SKU-4420-PRIME."},
        {"role": "assistant", "content": "Product SKU-4420-PRIME is currently in stock."}
    ]
    intent_it = engine.understand_intent("Can we ship it today?")
    rewritten_coref = engine.rewrite_query("Can we ship it today?", intent_it, history=history)
    assert any("SKU-4420-PRIME" in q for q in rewritten_coref)


# ─────────────────────────────────────────────────────────────────────────────
# 2. STAGE 3, 4 & 5: PERMISSION-AWARE RETRIEVAL, RRF & RERANKING
# ─────────────────────────────────────────────────────────────────────────────

def test_permission_aware_multi_tenant_isolation():
    vstore = PGVectorStore()
    engine = AdvancedRAGEngine(vector_store_instance=vstore)

    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())

    chunks = [
        {
            "id": "chunk_tenant_a_1",
            "content": "Secret executive compensation policy for Tenant A is strictly confidential.",
            "document_title": "Executive Compensation Policy",
            "chunk_index": 0,
            "department": "hr",
            "metadata": {"tenant_id": tenant_a}
        },
        {
            "id": "chunk_tenant_b_1",
            "content": "Tenant B public procurement threshold is $50,000 for standard POs.",
            "document_title": "Procurement Guidelines",
            "chunk_index": 0,
            "department": "procurement",
            "metadata": {"tenant_id": tenant_b}
        }
    ]

    engine.sync_corpus_for_sparse(chunks)

    # Tenant B queries compensation - MUST return 0 results (no leakage from Tenant A)
    dense_hits_b, sparse_hits_b = engine.hybrid_retrieve(
        queries=["executive compensation policy"],
        tenant_id=tenant_b,
        scope="hr",
        top_k=5
    )
    assert len(dense_hits_b) == 0
    assert len(sparse_hits_b) == 0

    # Tenant A queries compensation - MUST return Tenant A chunk
    dense_hits_a, sparse_hits_a = engine.hybrid_retrieve(
        queries=["executive compensation policy"],
        tenant_id=tenant_a,
        scope="hr",
        top_k=5
    )
    assert len(dense_hits_a) == 1
    assert dense_hits_a[0]["id"] == "chunk_tenant_a_1"


def test_reciprocal_rank_fusion_formula_and_deduplication():
    engine = AdvancedRAGEngine(rrf_k=60)

    # Chunk 1 appears in Dense rank 1 and Sparse rank 2
    dense_hits = [
        {"id": "doc_1", "content": "Passage 1 content", "document_title": "Doc 1", "chunk_index": 0, "relevance_score": 0.90},
        {"id": "doc_2", "content": "Passage 2 content", "document_title": "Doc 2", "chunk_index": 0, "relevance_score": 0.80}
    ]
    sparse_hits = [
        ({"id": "doc_3", "content": "Passage 3 content", "document_title": "Doc 3", "chunk_index": 0}, 8.5),
        ({"id": "doc_1", "content": "Passage 1 content", "document_title": "Doc 1", "chunk_index": 0}, 6.2)
    ]

    fused = engine.apply_rrf(dense_hits, sparse_hits, k=60)

    # doc_1 fused score = 1/(60+1) + 1/(60+2)
    expected_doc1_rrf = (1.0 / 61.0) + (1.0 / 62.0)
    doc_1_chunk = next(c for c in fused if c.id == "doc_1")
    assert abs(doc_1_chunk.rrf_score - expected_doc1_rrf) < 1e-6
    assert doc_1_chunk.provenance["dense_rank"] == 1
    assert doc_1_chunk.provenance["sparse_rank"] == 2

    # Verify deduplication (doc_1 appears exactly once in fused results)
    doc_1_occurrences = [c for c in fused if c.id == "doc_1"]
    assert len(doc_1_occurrences) == 1

    # Reranking with exact term match
    reranked = engine.rerank("Passage 1", fused, top_n=2)
    assert len(reranked) == 2
    assert reranked[0].id == "doc_1"


# ─────────────────────────────────────────────────────────────────────────────
# 3. STAGE 6, 7 & 8: CONTEXT ASSEMBLY, GROUNDING & ABSTENTION
# ─────────────────────────────────────────────────────────────────────────────

def test_context_assembly_and_token_budget():
    engine = AdvancedRAGEngine()

    chunks = [
        RetrievedChunk(id="c1", content="Paragraph 1 text.", document_title="Doc A", chunk_index=1, rerank_score=0.9),
        RetrievedChunk(id="c2", content="Paragraph 2 text.", document_title="Doc B", chunk_index=1, rerank_score=0.8),
        RetrievedChunk(id="c3", content="Paragraph 1 text.", document_title="Doc A", chunk_index=1, rerank_score=0.7)  # Duplicate text
    ]

    context, citations = engine.assemble_context(chunks, max_tokens=100)
    assert "[Source 1]" in context
    assert "[Source 2]" in context
    assert "Paragraph 1 text." in context
    assert "Paragraph 2 text." in context
    # Duplicate Paragraph 1 should be deduplicated
    assert len(citations) == 2


def test_anti_hallucination_grounding_and_numerical_verification():
    engine = AdvancedRAGEngine(groundedness_threshold=0.50)

    chunk = RetrievedChunk(
        id="c1",
        content="The authorized petty cash expenditure limit is $250.00 per department head.",
        document_title="Petty Cash Policy",
        chunk_index=0,
        rerank_score=0.85
    )
    context, citations = engine.assemble_context([chunk])

    # Factual grounded answer containing the exact number
    grounded_ans = "According to the Petty Cash Policy, the authorized limit is $250.00."
    res_grounded = engine.verify_grounding(grounded_ans, context, [chunk])
    assert res_grounded.is_grounded is True
    assert res_grounded.numeric_facts_verified is True
    assert res_grounded.action == "accept"

    # Hallucinated answer claiming a different numerical limit ($9,500.00)
    hallucinated_ans = "You can spend up to $9,500.00 in petty cash without manager approval."
    res_hallucinated = engine.verify_grounding(hallucinated_ans, context, [chunk])
    assert res_hallucinated.numeric_facts_verified is False
    assert "$9,500.00" in res_hallucinated.unsupported_claims
    assert res_hallucinated.action == "abstain"


def test_controlled_abstention_on_insufficient_evidence():
    engine = AdvancedRAGEngine(groundedness_threshold=0.60)
    engine._indexed_chunks = []
    engine.vector_store._local_chunks = []

    # Query with no matching documents in index
    response: RAGResponse = engine.answer_question(
        question="What is the nuclear reactor cooling SLA in warehouse 4?",
        department_scope="engineering"
    )

    assert response.status == "abstention"
    assert "Not enough verified information is available" in response.answer
    assert len(response.citations) == 0
    assert response.grounding.get("hallucination_flag") is True


# ─────────────────────────────────────────────────────────────────────────────
# 4. STAGE 9 & 10: CITATION VALIDATION & FINAL ANSWER FORMULATION
# ─────────────────────────────────────────────────────────────────────────────

def test_citation_validation_and_rejection_of_fabricated_citations():
    engine = AdvancedRAGEngine()

    assembled_context = (
        "[Source 1] (ID: legit_doc_101 | Document: Shipping Policy | Chunk: #0 | Department: LOGISTICS)\n"
        "Standard delivery turnaround time is 48 business hours."
    )

    legit_citation = Citation(
        source_index=1,
        source_id="legit_doc_101",
        document_title="Shipping Policy",
        chunk_index=0,
        department="logistics",
        relevance_score=0.92,
        excerpt="Standard delivery turnaround time is 48 business hours."
    )

    fabricated_citation = Citation(
        source_index=2,
        source_id="fake_doc_999",
        document_title="Fabricated Document",
        chunk_index=0,
        department="finance",
        relevance_score=0.99,
        excerpt="Fabricated content that was never retrieved."
    )

    validated = engine.validate_citations([legit_citation, fabricated_citation], assembled_context)
    assert len(validated) == 1
    assert validated[0].source_id == "legit_doc_101"


def test_full_end_to_end_rag_with_verified_citations():
    tenant_id = str(uuid.uuid4())
    engine = AdvancedRAGEngine(groundedness_threshold=0.40)

    corpus = [
        {
            "id": "po_policy_doc",
            "content": "All purchase orders exceeding $5,000 require dual signature authorization from Finance.",
            "document_title": "Procurement Threshold SOP",
            "chunk_index": 0,
            "department": "procurement",
            "metadata": {"tenant_id": tenant_id}
        }
    ]
    engine.sync_corpus_for_sparse(corpus)

    res: RAGResponse = engine.answer_question(
        question="What is the signature requirement for POs over $5,000?",
        department_scope="procurement",
        tenant_id=tenant_id
    )

    assert res.status == "grounded"
    assert "require dual signature authorization" in res.answer
    assert "[^1]" in res.answer
    assert len(res.citations) >= 1
    assert res.citations[0].document_title == "Procurement Threshold SOP"
    assert res.grounding["is_grounded"] is True


# ─────────────────────────────────────────────────────────────────────────────
# 5. ERP 5-WAY INTENT ROUTING INTEGRATION
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_erp_intent_routing_calculation_and_transactional():
    org_id = uuid.uuid4()

    # 1. Calculation branch (total inventory)
    res_calc: AgentRuntimeResponse = await agent_runtime.dispatch(
        query="Calculate total inventory valuation and stock quantity",
        organization_id=org_id
    )
    assert res_calc.branch == "calculation_action"
    assert "Calculated" in res_calc.response_text
    assert res_calc.data is not None

    # 2. Transactional branch (list products)
    res_trans: AgentRuntimeResponse = await agent_runtime.dispatch(
        query="list products in enterprise catalog",
        organization_id=org_id
    )
    assert res_trans.branch == "transactional_action"
    assert "tool" in res_trans.data

    # 3. Persona responder (greeting)
    res_greeting: AgentRuntimeResponse = await agent_runtime.dispatch(
        query="hello there",
        organization_id=org_id
    )
    assert res_greeting.branch == "persona_responder"
    assert res_greeting.latency_ms < 5.0

    # 4. Human escalation (complaint / human agent)
    res_esc: AgentRuntimeResponse = await agent_runtime.dispatch(
        query="I demand to speak to a human representative immediately",
        organization_id=org_id
    )
    assert res_esc.branch == "human_escalation"
    assert "ESC-" in res_esc.data["ticket_id"]

    # 5. Knowledge RAG branch
    res_rag: AgentRuntimeResponse = await agent_runtime.dispatch(
        query="What are the regulatory compliance guidelines for GDPR audit trails?",
        organization_id=org_id
    )
    assert res_rag.branch == "knowledge_rag"
