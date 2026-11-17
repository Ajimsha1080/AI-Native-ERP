"""
Enterprise Integration Tests for GraphRAG (Knowledge Graph Augmented Retrieval).

Validates:
1. High-precision ERP entity and relational triple extraction from text.
2. Knowledge Graph node and edge indexing, deduplication, and chunk provenance.
3. Multi-hop relational graph traversal (1-hop, 2-hop, 3-hop) and path discovery.
4. Strict Multi-Tenant Isolation (zero cross-tenant data leakage).
5. Subgraph extraction and markdown triple formatting for prompt augmentation.
6. Integration with 10-Stage AdvancedRAGEngine & HybridRAGEngine.
"""

import pytest
import uuid
from packages.rag.graph_rag import (
    GraphRAGEngine,
    TenantKnowledgeGraph,
    GraphExtractor,
    EntityNode,
    RelationEdge,
    EntityType,
    RelationType,
    normalize_entity_id,
    graph_rag_engine
)
from packages.rag.pipeline import AdvancedRAGEngine
from packages.rag.rag_engine import HybridRAGEngine


# ─────────────────────────────────────────────────────────────────────────────
# 1. ENTITY & TRIPLE EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def test_graph_extractor_erp_entities():
    extractor = GraphExtractor()
    sample_text = (
        "Purchase Order PO-88301 was issued to Vendor Acme Corp for 500 units of SKU-9840-X1. "
        "This order is governed under Master Service Agreement MSA-2025-ACME, specifically "
        "Clause 4.2 requiring Net 30 payment terms and SLA 99.5% uptime."
    )
    entities = extractor.extract_entities_from_text(sample_text)
    entity_names = [e[0] for e in entities]
    entity_types = [e[1] for e in entities]

    assert any("PO-88301" in name for name in entity_names)
    assert any("Acme Corp" in name for name in entity_names)
    assert any("SKU-9840-X1" in name for name in entity_names)
    assert any("MSA-2025-ACME" in name for name in entity_names)
    assert any("Clause 4.2" in name or "Net 30" in name for name in entity_names)

    assert EntityType.PURCHASE_ORDER.value in entity_types
    assert EntityType.VENDOR.value in entity_types
    assert EntityType.SKU.value in entity_types
    assert EntityType.CONTRACT.value in entity_types
    assert EntityType.CLAUSE.value in entity_types


def test_graph_extractor_triples():
    extractor = GraphExtractor()
    text = (
        "Invoice INV-9041 references PO-88301 issued to Vendor Acme Corp for SKU-9840-X1. "
        "Governed by Contract MSA-2025-ACME with Clause 7.1."
    )
    triples = extractor.extract_triples_from_text(text, chunk_id="chunk_001")
    assert len(triples) >= 3

    # Check relation types generated
    relation_types = [t[1] for t in triples]
    assert RelationType.REFERENCES.value in relation_types  # Invoice -> PO
    assert RelationType.ISSUED_TO.value in relation_types   # PO -> Vendor
    assert RelationType.PURCHASES.value in relation_types or RelationType.SUPPLIES.value in relation_types


# ─────────────────────────────────────────────────────────────────────────────
# 2. GRAPH INDEXING & PROVENANCE
# ─────────────────────────────────────────────────────────────────────────────

def test_graph_indexing_and_provenance():
    kg = TenantKnowledgeGraph()
    engine = GraphRAGEngine(knowledge_graph=kg)
    tenant_id = str(uuid.uuid4())

    chunk_content = "Vendor Apex Logistics supplies SKU-5520-B. Governed by Contract MSA-992."
    nodes, edges = engine.index_chunk(
        chunk_id="chunk_test_1",
        content=chunk_content,
        tenant_id=tenant_id,
        metadata={"document_type": "contract", "department": "procurement"}
    )

    assert len(nodes) >= 2
    assert len(edges) >= 1

    # Check that chunk provenance was recorded
    apex_node = kg.find_node_by_name("Apex Logistics", tenant_id)
    assert apex_node is not None
    assert "chunk_test_1" in apex_node.chunk_ids

    # Idempotent re-indexing does not duplicate nodes
    engine.index_chunk(
        chunk_id="chunk_test_2",
        content=chunk_content,
        tenant_id=tenant_id
    )
    apex_node_reindexed = kg.find_node_by_name("Apex Logistics", tenant_id)
    assert "chunk_test_1" in apex_node_reindexed.chunk_ids
    assert "chunk_test_2" in apex_node_reindexed.chunk_ids


# ─────────────────────────────────────────────────────────────────────────────
# 3. MULTI-HOP RELATIONAL TRAVERSAL & PATH FINDING
# ─────────────────────────────────────────────────────────────────────────────

def test_multi_hop_traversal_and_paths():
    kg = TenantKnowledgeGraph()
    engine = GraphRAGEngine(knowledge_graph=kg)
    tenant_id = f"tenant_{uuid.uuid4()}"

    # Document 1: Invoice references PO
    engine.index_chunk(
        chunk_id="c1",
        content="Invoice INV-7712 references PO-3301.",
        tenant_id=tenant_id
    )

    # Document 2: PO issued to Vendor
    engine.index_chunk(
        chunk_id="c2",
        content="Purchase Order PO-3301 issued to Vendor Global Metals.",
        tenant_id=tenant_id
    )

    # Document 3: Vendor bound by Contract with Clause
    engine.index_chunk(
        chunk_id="c3",
        content="Vendor Global Metals is governed by Contract MSA-GM-2026 containing Clause 5.3 for Net 45 payment.",
        tenant_id=tenant_id
    )

    # Multi-hop path explanation: INV-7712 -> Clause 5.3 (3 hops)
    explanation = engine.explain_relation("INV-7712", "Clause 5.3", tenant_id, max_hops=4)
    assert explanation["connected"] is True
    assert explanation["paths_count"] >= 1
    first_path = explanation["paths"][0]
    # Path sequence should traverse through intermediate entities
    assert len(first_path) >= 2


def test_subgraph_retrieval_and_context_formatting():
    kg = TenantKnowledgeGraph()
    engine = GraphRAGEngine(knowledge_graph=kg)
    tenant_id = f"tenant_{uuid.uuid4()}"

    engine.index_chunk(
        chunk_id="c10",
        content="Purchase Order PO-9900 issued to Vendor Zenith Electronics for SKU-Z-100.",
        tenant_id=tenant_id
    )

    result = engine.retrieve_graph_context("What vendor supplies SKU-Z-100 on PO-9900?", tenant_id=tenant_id)
    assert result.nodes_count >= 2
    assert result.edges_count >= 1
    assert "Zenith Electronics" in result.context_text
    assert "PO-9900" in result.context_text
    assert "c10" in result.connected_chunk_ids


# ─────────────────────────────────────────────────────────────────────────────
# 4. STRICT MULTI-TENANT ISOLATION
# ─────────────────────────────────────────────────────────────────────────────

def test_strict_multi_tenant_isolation():
    kg = TenantKnowledgeGraph()
    engine = GraphRAGEngine(knowledge_graph=kg)

    tenant_a = f"tenant_alpha_{uuid.uuid4()}"
    tenant_b = f"tenant_beta_{uuid.uuid4()}"

    # Ingest secret contract for Tenant A
    engine.index_chunk(
        chunk_id="c_alpha_1",
        content="Vendor SecretVendor Alpha supplies confidential SKU-CONF-99 under Contract MSA-SECRET-A.",
        tenant_id=tenant_a
    )

    # Ingest public contract for Tenant B
    engine.index_chunk(
        chunk_id="c_beta_1",
        content="Vendor PublicVendor Beta supplies standard SKU-PUB-01 under Contract MSA-PUB-B.",
        tenant_id=tenant_b
    )

    # Tenant B attempts to retrieve Tenant A's confidential node
    leak_attempt_node = kg.find_node_by_name("SecretVendor Alpha", tenant_id=tenant_b)
    assert leak_attempt_node is None

    # Tenant B queries for Tenant A's SKU
    res_b = engine.retrieve_graph_context("SKU-CONF-99 SecretVendor Alpha", tenant_id=tenant_b)
    assert res_b.nodes_count == 0
    assert res_b.edges_count == 0
    assert res_b.context_text == ""
    assert "SecretVendor" not in res_b.context_text

    # Tenant A queries for Tenant A's SKU -> Success
    res_a = engine.retrieve_graph_context("SKU-CONF-99 SecretVendor Alpha", tenant_id=tenant_a)
    assert res_a.nodes_count >= 1
    assert "SecretVendor Alpha" in res_a.context_text

    # Tenant B explanation between Tenant A entities must fail
    path_res = engine.explain_relation("SecretVendor Alpha", "SKU-CONF-99", tenant_id=tenant_b)
    assert path_res["connected"] is False


# ─────────────────────────────────────────────────────────────────────────────
# 5. INTEGRATION WITH 10-STAGE ADVANCED RAG & HYBRID RAG ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def test_advanced_rag_engine_graph_augmentation():
    engine = AdvancedRAGEngine()
    tenant_id = f"org_{uuid.uuid4()}"

    corpus = [
        {
            "id": "doc_po_1",
            "document_title": "PO-10499 Execution",
            "chunk_index": 1,
            "department": "procurement",
            "tenant_id": tenant_id,
            "content": "Purchase Order PO-10499 was issued to Vendor Nordic Logistics for SKU-NOR-88. Governed by Contract MSA-NORDIC-2026."
        },
        {
            "id": "doc_contract_1",
            "document_title": "MSA-NORDIC Master Agreement",
            "chunk_index": 2,
            "department": "legal",
            "tenant_id": tenant_id,
            "content": "Contract MSA-NORDIC-2026 contains Clause 3.4 specifying penalty of 5% per week for delayed delivery."
        }
    ]

    engine.sync_corpus_for_sparse(corpus)

    # Query connecting PO-10499 to penalties
    response = engine.answer_question(
        question="What are the contract terms and penalties for PO-10499?",
        tenant_id=tenant_id,
        groundedness_threshold=0.30
    )

    # Pipeline stages must record GraphRAG traversal
    assert any("GraphRAG" in stage for stage in response.pipeline_stages)
    assert response.status in ["grounded", "safe_refusal", "abstention"]


def test_hybrid_rag_engine_graph_helpers():
    hybrid = HybridRAGEngine()
    tenant_id = f"org_{uuid.uuid4()}"

    hybrid.sync_sparse_corpus([
        {
            "id": "chunk_h1",
            "document_title": "Vendor Profile",
            "chunk_index": 1,
            "department": "procurement",
            "tenant_id": tenant_id,
            "content": "Vendor Delta Dynamics supplies SKU-DD-500 under Contract MSA-DELTA."
        }
    ])

    graph_res = hybrid.query_graph("What does Delta Dynamics supply?", tenant_id=tenant_id)
    assert graph_res.nodes_count >= 1
    assert "Delta Dynamics" in graph_res.context_text

    explanation = hybrid.explain_relation("Delta Dynamics", "SKU-DD-500", tenant_id=tenant_id)
    assert explanation["connected"] is True
