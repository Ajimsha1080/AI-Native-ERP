"""
Integration tests for LangGraph multi-agent orchestration, supervisor routing, and risk approvals.
"""

import pytest
from uuid import uuid4
from decimal import Decimal

from packages.database.core import async_session_scope, create_db_and_tables
from packages.database.tenant_context import set_tenant_context
from packages.agents.graph.graph import run_erp_agent
from packages.agents.approval_manager import ApprovalManager


@pytest.mark.asyncio
async def test_langgraph_agent_supervisor_routing():
    await create_db_and_tables()
    org_id = uuid4()
    user_id = uuid4()

    # 1. Inventory routing
    res_inv = await run_erp_agent(
        organization_id=org_id,
        user_id=user_id,
        user_role="manager",
        prompt="Show me all current inventory products and stock status",
    )
    assert res_inv["routed_to"] == "inventory_agent"
    assert "Retrieved" in res_inv["response"] or "Stock" in res_inv["response"]

    # 2. Sales routing
    res_sales = await run_erp_agent(
        organization_id=org_id,
        user_id=user_id,
        user_role="manager",
        prompt="List recent customer invoices",
    )
    assert res_sales["routed_to"] == "sales_agent"
    assert "Found" in res_sales["response"]

    # 3. Finance routing
    res_finance = await run_erp_agent(
        organization_id=org_id,
        user_id=user_id,
        user_role="manager",
        prompt="Check chart of accounts and finance ledger",
    )
    assert res_finance["routed_to"] == "finance_agent"
    assert "Chart of Accounts" in res_finance["response"]


def test_agent_risk_tier_approval_rules():
    # Read tools are low risk -> auto execute
    assert ApprovalManager.is_high_risk_tool("list_products", {}) is False
    assert ApprovalManager.is_high_risk_tool("check_stock", {}) is False

    # Financial / sensitive write tools -> require human approval
    assert ApprovalManager.is_high_risk_tool("record_payment", {"amount": 500}) is True
    assert ApprovalManager.is_high_risk_tool("post_journal_entry", {"entry_id": "123"}) is True

    # Stock adjustments over 100 units -> require approval
    assert ApprovalManager.is_high_risk_tool("adjust_stock", {"delta": 50}) is False
    assert ApprovalManager.is_high_risk_tool("adjust_stock", {"delta": 500}) is True
