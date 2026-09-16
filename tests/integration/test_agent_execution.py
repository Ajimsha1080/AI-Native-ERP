"""
Integration Test Suite for Agentic ERP Backend
Verifies Agent ReAct Tool Loop, RBAC Policy Checks, Workflow Lifecycles, Tool Validation, and Chroma RAG.
"""

import pytest
import asyncio
from datetime import datetime

from packages.agents.base import BaseAgent
from packages.tools.erp_tools import AgentToolLayer, check_inventory, check_revenue, check_pending_invoices
from packages.rag.vector_store import ChromaVectorStore, vector_store
from apps.api.v1.chat import chat_with_agent, ChatRequest, ChatMessage


@pytest.mark.asyncio
async def test_agent_react_execution_round_trip():
    """Test BaseAgent executes ReAct loop and invokes ERP tools deterministically or via LLM."""
    agent = BaseAgent(
        name="Inventory Controller Agent",
        role="Autonomous Warehouse & Supply Chain Manager"
    )

    # 1. Inventory inquiry
    result_inv = await agent.execute_task("Check current inventory stock levels for SKU-9921 in Warehouse A.")
    assert result_inv["status"] == "completed"
    assert len(result_inv["tool_calls"]) >= 1
    assert result_inv["tool_calls"][0]["tool"] == "get_inventory"
    assert "SKU-9921" in str(result_inv["tool_calls"][0]["arguments"])
    assert "units" in result_inv["tool_calls"][0]["result"]

    # 2. High-value Purchase Order triggering human-in-the-loop policy boundary (> $1,000)
    result_po = await agent.execute_task("Create a purchase order for $5,000.00 from Dell Enterprise.")
    assert result_po["status"] == "completed"
    assert len(result_po["tool_calls"]) >= 1
    po_call = result_po["tool_calls"][0]
    assert po_call["tool"] == "create_purchase_order"
    assert po_call["result"]["requires_approval"] is True
    assert "approvals" in result_po["output"].lower() or "approval" in result_po["output"].lower()


@pytest.mark.asyncio
async def test_agent_tool_layer_rbac_enforcement():
    """Test AgentToolLayer enforces fail-closed RBAC on unauthorized write actions."""
    # Tool layer with read-only permission for inventory
    tool_layer_read_only = AgentToolLayer(allowed_tools=["read_inventory", "inventory"])

    # Read action allowed
    read_allowed = await tool_layer_read_only._policy_check(
        action="read",
        entity="inventory"
    )
    assert read_allowed is True

    # Write action rejected by ACL
    write_allowed = await tool_layer_read_only._policy_check(
        action="create",
        entity="purchase_orders"
    )
    assert write_allowed is False

    # Attempting create_purchase_order with read-only layer raises PermissionError
    with pytest.raises(PermissionError):
        await tool_layer_read_only.create_purchase_order(
            supplier_id="SUPP-001",
            amount=500.00,
            items=[{"item": "Office Supplies", "qty": 10}]
        )


@pytest.mark.asyncio
async def test_tool_direct_execution_and_reporting():
    """Test direct ERP tool functions return authentic enterprise data structures."""
    inv = check_inventory("SKU-8840")
    assert "SKU-8840" in inv
    assert "units" in inv

    rev = check_revenue()
    assert "$" in rev
    assert "425,000" in rev or "Revenue" in rev

    invoices = check_pending_invoices()
    assert "invoice" in invoices.lower() or "pending" in invoices.lower()


def test_chroma_rag_vector_store_indexing_and_retrieval(tmp_path):
    """Test ChromaVectorStore indexing document chunks and performing semantic similarity search."""
    store = ChromaVectorStore(persist_directory=str(tmp_path / "chroma_test"))

    docs = [
        "Procurement Policy: All purchase orders exceeding $1,000 USD require Department Head approval.",
        "Warehouse Protocol: Stock counts for SKU-8840 and SKU-9921 must be audited on the 1st of every month.",
        "Accounts Payable: Vendor invoices must be matched against purchase orders prior to net-30 disbursement."
    ]
    metas = [
        {"document_title": "Procurement Manual", "category": "Policy"},
        {"document_title": "Inventory SOP", "category": "Warehouse"},
        {"document_title": "Finance Guidelines", "category": "Finance"}
    ]
    ids = ["doc-procure-01", "doc-inventory-01", "doc-finance-01"]

    success = store.add_documents(
        collection_name="test_erp_kb",
        documents=docs,
        metadatas=metas,
        ids=ids
    )
    assert success is True

    # Semantic search
    results = store.query(
        collection_name="test_erp_kb",
        query_text="Procurement Policy approval threshold for purchase orders",
        top_k=2
    )
    assert len(results) >= 1
    contents = [r["content"] for r in results]
    assert any("Procurement" in c for c in contents)
    assert results[0]["relevance_score"] >= 0.0


@pytest.mark.asyncio
async def test_chat_endpoint_agent_orchestration():
    """Test /api/v1/chat endpoint invokes BaseAgent ReAct loop."""
    req = ChatRequest(messages=[
        ChatMessage(role="user", content="Please inspect stock for SKU-8840 and summarize.")
    ])
    
    response = await chat_with_agent(req)
    assert "response" in response
    assert response["status"] == "completed"
    assert response["agent"] == "Enterprise ERP Copilot"
    assert len(response["tool_calls"]) > 0
    assert response["tool_calls"][0]["tool"] == "get_inventory"
