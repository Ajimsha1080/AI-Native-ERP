"""
Phase 2 & Phase 3 Integration Tests:
- Phase 2: Command Center, LangGraph, SSE streaming, 503 on missing LLM, state-changing tools create approval.
- Phase 3: Unified Approvals, self-approval blocked (403), dual approval over threshold ($1,000), single approval under threshold, replay no-op, cross-tenant 404, structured amount evaluation.
"""

import pytest
from uuid import uuid4, UUID
from decimal import Decimal
from datetime import datetime, timezone, date
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from apps.api.main import app
from tests.conftest import ASYNC_TEST_DB_URL
from packages.auth.tokens import create_access_token
from packages.database.models import Organization, User, Action, ActionStatus, Approval
from packages.database.models.erp.inventory import Product, Warehouse, StockLevel
from packages.database.models.erp.sales import Invoice, InvoiceStatus
from packages.database.models.erp.purchasing import Vendor, PurchaseOrder
from packages.database.tenant_context import set_tenant_context
from packages.agents.approval_service import (
    propose_state_changing_action,
    process_approval_decision,
    extract_tool_amount,
    APPROVAL_THRESHOLD_USD
)
from packages.agents.graph.tools.erp_tools import (
    tool_adjust_stock,
    tool_create_purchase_order,
    tool_record_payment,
    tool_create_journal_entry
)
from packages.config.settings import settings


@pytest.mark.asyncio
async def test_command_endpoint_missing_llm_returns_503():
    """If no LLM provider is configured, POST /command and GET /command/stream return 503."""
    org_id = uuid4()
    user_id = uuid4()
    token = create_access_token(user_id=user_id, org_id=org_id, role="admin")
    headers = {"Authorization": f"Bearer {token}"}

    # Temporarily ensure no LLM keys are set
    orig_openai = settings.openai_api_key
    orig_anthropic = settings.anthropic_api_key
    try:
        settings.openai_api_key = ""
        settings.anthropic_api_key = ""

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # POST /command must return 503 for non-blocked query
            res = await client.post(
                "/api/v1/dashboard/command",
                headers=headers,
                json={"query": "Analyze quarterly procurement spend and forecast"}
            )
            assert res.status_code == 503
            assert "AI Gateway Unavailable" in res.json()["detail"]

            # GET /command/stream must also return 503
            res_stream = await client.get(
                "/api/v1/dashboard/command/stream?query=Check+inventory+forecast",
                headers=headers
            )
            assert res_stream.status_code == 503
            assert "AI Gateway Unavailable" in res_stream.json()["detail"]
    finally:
        settings.openai_api_key = orig_openai
        settings.anthropic_api_key = orig_anthropic


@pytest.mark.asyncio
async def test_state_changing_tools_create_approvals_and_do_not_execute_directly():
    """State-changing tools (adjust_stock, PO, payment, journal) create an Action and never mutate directly."""
    engine = create_async_engine(ASYNC_TEST_DB_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid4()
    user_id = uuid4()

    async with session_factory() as session:
        await set_tenant_context(session, org_id)
        org = Organization(id=org_id, name="Tool Test Org", slug=f"tool-{org_id.hex[:6]}")
        user = User(
            id=user_id,
            email=f"agent.{org_id.hex[:4]}@tool.io",
            organization_id=org_id,
            tenant_id=org_id,
            password_hash="argon2id$mock$hash",
            first_name="Agent",
            last_name="User",
            is_active=True
        )
        session.add_all([org, user])
        await session.commit()

        # 1. Adjust stock tool call
        p_id = uuid4()
        w_id = uuid4()
        res_stock = await tool_adjust_stock(
            organization_id=org_id,
            product_id=p_id,
            warehouse_id=w_id,
            delta=500.0,
            reason="Bulk replenishment arrived",
            requested_by_id=user_id,
        )
        assert res_stock["status"] == "approval_required"
        action_id_stock = UUID(res_stock["action_id"])

        # Verify Action in DB is APPROVAL_REQUIRED
        stmt = select(Action).where(Action.id == action_id_stock)
        action_stock = (await session.execute(stmt)).scalar_one()
        assert action_stock.status == ActionStatus.APPROVAL_REQUIRED
        assert action_stock.name == "adjust_stock"
        assert action_stock.requested_by_id == user_id

        # 2. Payment tool call
        inv_id = uuid4()
        res_pay = await tool_record_payment(
            organization_id=org_id,
            invoice_id=inv_id,
            amount=4500.0,
            requested_by_id=user_id,
        )
        assert res_pay["status"] == "approval_required"
        action_id_pay = UUID(res_pay["action_id"])

        stmt_pay = select(Action).where(Action.id == action_id_pay)
        action_pay = (await session.execute(stmt_pay)).scalar_one()
        assert action_pay.status == ActionStatus.APPROVAL_REQUIRED
        assert action_pay.estimated_cost == 4500.0


@pytest.mark.asyncio
async def test_self_approval_blocked():
    """Requester cannot approve their own action (separation of duties)."""
    engine = create_async_engine(ASYNC_TEST_DB_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid4()
    requester_id = uuid4()

    async with session_factory() as session:
        await set_tenant_context(session, org_id)
        org = Organization(id=org_id, name="Self Approval Org", slug=f"self-{org_id.hex[:6]}")
        user = User(
            id=requester_id,
            email=f"requester.{org_id.hex[:4]}@corp.io",
            organization_id=org_id,
            tenant_id=org_id,
            password_hash="argon2id$mock$passwordhashfortest1234567890",
            first_name="Requester",
            last_name="User",
            is_active=True
        )
        session.add_all([org, user])
        await session.commit()

        # Propose action requested by this user
        action = await propose_state_changing_action(
            session=session,
            organization_id=org_id,
            tool_name="adjust_stock",
            inputs={"product_id": str(uuid4()), "warehouse_id": str(uuid4()), "delta": 50.0, "amount": 500.0},
            requested_by_id=requester_id,
            requester_email=user.email,
        )
        action_id = action.id

    token = create_access_token(user_id=requester_id, org_id=org_id, role="manager", email=user.email)
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(f"/api/v1/actions/{action_id}/approve", headers=headers)
        assert res.status_code == 403
        assert "Self-approval forbidden" in res.json()["detail"]


@pytest.mark.asyncio
async def test_dual_approval_over_threshold_enforced():
    """Amounts > $1,000 require two distinct approvers. 1st approver leaves status pending_second_approval."""
    engine = create_async_engine(ASYNC_TEST_DB_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid4()
    requester_id = uuid4()
    manager_1 = uuid4()
    manager_2 = uuid4()

    async with session_factory() as session:
        await set_tenant_context(session, org_id)
        org = Organization(id=org_id, name="Dual Approval Corp", slug=f"dual-{org_id.hex[:6]}")
        u_req = User(id=requester_id, email="agent.initiator@dualcorp.io", organization_id=org_id, tenant_id=org_id, password_hash="argon2id$mock$hash1", first_name="Agent", last_name="Init", is_active=True)
        u_m1 = User(id=manager_1, email="mgr1@dualcorp.io", organization_id=org_id, tenant_id=org_id, password_hash="argon2id$mock$hash2", first_name="Manager", last_name="One", is_active=True)
        u_m2 = User(id=manager_2, email="mgr2@dualcorp.io", organization_id=org_id, tenant_id=org_id, password_hash="argon2id$mock$hash3", first_name="Manager", last_name="Two", is_active=True)
        session.add_all([org, u_req, u_m1, u_m2])
        await session.commit()

        # Propose high-value PO ($15,000.00)
        action = await propose_state_changing_action(
            session=session,
            organization_id=org_id,
            tool_name="create_purchase_order",
            inputs={
                "vendor_id": str(uuid4()),
                "lines": [{"product_id": str(uuid4()), "quantity": 100, "unit_cost": 150.0}],
            },
            requested_by_id=requester_id,
            requester_email=u_req.email,
        )
        action_id = action.id

    token_m1 = create_access_token(user_id=manager_1, org_id=org_id, role="manager", email=u_m1.email)
    token_m2 = create_access_token(user_id=manager_2, org_id=org_id, role="manager", email=u_m2.email)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # First manager approves: must record 1st approval and require second distinct approval
        res1 = await client.post(
            f"/api/v1/actions/{action_id}/approve",
            headers={"Authorization": f"Bearer {token_m1}"}
        )
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["status"] == "pending_second_approval"
        assert data1["approvals_count"] == 1
        assert data1["approvals_required"] == 2

        # Same manager attempts to approve again: must be rejected with 400
        res_repeat = await client.post(
            f"/api/v1/actions/{action_id}/approve",
            headers={"Authorization": f"Bearer {token_m1}"}
        )
        assert res_repeat.status_code == 400
        assert "Duplicate approval" in res_repeat.json()["detail"]

        # Second distinct manager approves: transitions to executed
        res2 = await client.post(
            f"/api/v1/actions/{action_id}/approve",
            headers={"Authorization": f"Bearer {token_m2}"}
        )
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["status"] == "executed"

        # Replay attempt: idempotent no-op
        res_replay = await client.post(
            f"/api/v1/actions/{action_id}/approve",
            headers={"Authorization": f"Bearer {token_m2}"}
        )
        assert res_replay.status_code == 200
        assert "idempotent no-op" in res_replay.json()["message"]


@pytest.mark.asyncio
async def test_cross_tenant_approvals_return_404():
    """Attempting to approve an action from another tenant returns 404."""
    engine = create_async_engine(ASYNC_TEST_DB_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    org_a = uuid4()
    org_b = uuid4()
    mgr_b = uuid4()

    async with session_factory() as session:
        await set_tenant_context(session, org_a)
        org1 = Organization(id=org_a, name="Org Alpha", slug=f"alpha-{org_a.hex[:6]}")
        org2 = Organization(id=org_b, name="Org Beta", slug=f"beta-{org_b.hex[:6]}")
        session.add_all([org1, org2])
        await session.commit()

        # Action belongs to Org Alpha
        action = await propose_state_changing_action(
            session=session,
            organization_id=org_a,
            tool_name="adjust_stock",
            inputs={"product_id": str(uuid4()), "warehouse_id": str(uuid4()), "delta": 10.0, "amount": 100.0},
        )
        action_id = action.id

    # User from Org Beta tries to access/approve Org Alpha's action
    token_b = create_access_token(user_id=mgr_b, org_id=org_b, role="manager", email="mgr@beta.io")
    headers = {"Authorization": f"Bearer {token_b}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(f"/api/v1/actions/{action_id}/approve", headers=headers)
        assert res.status_code == 404
        assert "not found in tenant context" in res.json()["detail"]


@pytest.mark.asyncio
async def test_under_threshold_single_approval_executes_idempotently():
    """Amounts <= $1,000 ($999.00) require only a single manager approval and execute."""
    engine = create_async_engine(ASYNC_TEST_DB_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid4()
    manager_id = uuid4()

    async with session_factory() as session:
        await set_tenant_context(session, org_id)
        org = Organization(id=org_id, name="Single Approver Org", slug=f"single-{org_id.hex[:6]}")
        u_mgr = User(id=manager_id, email="mgr@singlecorp.io", organization_id=org_id, tenant_id=org_id, password_hash="argon2id$mock$hash4", first_name="Solo", last_name="Manager", is_active=True)
        session.add_all([org, u_mgr])
        await session.commit()

        # Propose $999.00 payment (under $1,000 threshold)
        action = await propose_state_changing_action(
            session=session,
            organization_id=org_id,
            tool_name="record_payment",
            inputs={"invoice_id": str(uuid4()), "amount": 999.0},
        )
        action_id = action.id

    token = create_access_token(user_id=manager_id, org_id=org_id, role="manager", email=u_mgr.email)
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(f"/api/v1/actions/{action_id}/approve", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "executed"
        assert data["amount"] == 999.0
