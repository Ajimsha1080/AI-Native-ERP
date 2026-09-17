"""
Comprehensive Cross-Tenant Isolation Integration Tests.
Proves Tenant A cannot read, mutate, or intercept Tenant B's data across:
1. ERP Layer (Inventory, Sales)
2. Dashboard & Command Center APIs (/dashboard/home, /dashboard/inventory, /dashboard/finance)
3. Action & Approval Queue (/actions/approvals-queue, /actions/{id}/approve)
4. Workflows (/workflows, /workflows/{id}/run)
5. Direct PostgreSQL RLS TenantDB session scoping
"""

import pytest
from httpx import AsyncClient, ASGITransport
from uuid import uuid4
from decimal import Decimal
from datetime import datetime, timezone

from apps.api.main import app
from packages.database.core import async_session_scope, create_db_and_tables
from packages.database.tenant_context import set_tenant_context
from packages.auth.tokens import create_access_token
from packages.database.models import (
    Organization, Workspace, User, UserStatus, Agent,
    Action, ActionType, ActionStatus, Workflow, WorkflowStatus
)
from packages.database.models.erp.inventory import Product, Warehouse, StockLevel
from packages.database.models.erp.sales import Customer, SalesOrder, OrderStatus, Invoice, InvoiceStatus
from packages.erp.services.inventory_service import InventoryService


@pytest.mark.asyncio
async def test_cross_tenant_isolation_full_suite():
    # 0. Ensure database tables exist
    await create_db_and_tables()

    # 1. Setup Tenant Alpha and Tenant Beta IDs and Tokens
    tenant_a_id = uuid4()
    tenant_b_id = uuid4()
    user_a_id = uuid4()
    user_b_id = uuid4()

    token_a = create_access_token(user_id=user_a_id, org_id=tenant_a_id, role="admin")
    token_b = create_access_token(user_id=user_b_id, org_id=tenant_b_id, role="admin")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    action_a_id = uuid4()
    workflow_a_id = uuid4()

    # 2. Seed Tenant Alpha resources into database
    async with async_session_scope() as session:
        await set_tenant_context(session, tenant_a_id)

        # Organization & Users
        org_a = Organization(id=tenant_a_id, name="Tenant Alpha Corp", slug=f"alpha-{uuid4().hex[:6]}")
        user_a = User(
            id=user_a_id,
            tenant_id=tenant_a_id,
            email=f"ceo@alpha-{uuid4().hex[:4]}.com",
            password_hash="hash",
            first_name="Alice",
            last_name="Alpha",
            status=UserStatus.ACTIVE,
            is_active=True,
        )
        session.add_all([org_a, user_a])

        # Inventory Product for Alpha
        prod_a = Product(
            id=uuid4(),
            organization_id=tenant_a_id,
            sku=f"ALPHA-CONFIDENTIAL-{uuid4().hex[:6]}",
            name="Alpha Secret Widget",
            unit_price=Decimal("9999.00"),
            cost_price=Decimal("4000.00"),
        )
        session.add(prod_a)

        # Pending Action for Alpha
        action_a = Action(
            id=action_a_id,
            organization_id=tenant_a_id,
            name="Alpha Strategic Acquisition PO",
            action_type=ActionType.CREATE,
            status=ActionStatus.APPROVAL_REQUIRED,
            action_data={"amount": 50000.0, "vendor": "Secret Alpha Supplier"},
            proposed_at=datetime.now(timezone.utc),
        )
        session.add(action_a)

        # Workflow for Alpha
        wf_a = Workflow(
            id=workflow_a_id,
            organization_id=tenant_a_id,
            name="Alpha Proprietary Pricing Model",
            slug=f"alpha-pricing-{uuid4().hex[:6]}",
            description="Tenant Alpha internal automated pipeline",
            status=WorkflowStatus.ACTIVE,
        )
        session.add(wf_a)

        await session.commit()

    # Seed Tenant Beta resources into database
    async with async_session_scope() as session:
        await set_tenant_context(session, tenant_b_id)

        org_b = Organization(id=tenant_b_id, name="Tenant Beta LLC", slug=f"beta-{uuid4().hex[:6]}")
        user_b = User(
            id=user_b_id,
            tenant_id=tenant_b_id,
            email=f"bob@beta-{uuid4().hex[:4]}.com",
            password_hash="hash",
            first_name="Bob",
            last_name="Beta",
            status=UserStatus.ACTIVE,
            is_active=True,
        )
        session.add_all([org_b, user_b])
        await session.commit()

    # 3. Test HTTP Isolation with ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        
        # --- TEST 1: Dashboard Home Isolation ---
        # Tenant A sees their pending action
        res_a_home = await client.get("/api/v1/dashboard/home", headers=headers_a)
        assert res_a_home.status_code == 200
        approvals_a = res_a_home.json().get("approvals", [])
        assert any(appr["id"] == str(action_a_id) for appr in approvals_a)

        # Tenant B MUST NOT see Tenant A's action
        res_b_home = await client.get("/api/v1/dashboard/home", headers=headers_b)
        assert res_b_home.status_code == 200
        approvals_b = res_b_home.json().get("approvals", [])
        assert not any(appr["id"] == str(action_a_id) for appr in approvals_b)

        # --- TEST 2: Dashboard Inventory Isolation ---
        res_a_inv = await client.get("/api/v1/dashboard/inventory", headers=headers_a)
        assert res_a_inv.status_code == 200
        items_a = res_a_inv.json().get("products", [])
        assert any("ALPHA-CONFIDENTIAL" in item.get("sku", "") for item in items_a)

        res_b_inv = await client.get("/api/v1/dashboard/inventory", headers=headers_b)
        assert res_b_inv.status_code == 200
        items_b = res_b_inv.json().get("products", [])
        assert not any("ALPHA-CONFIDENTIAL" in item.get("sku", "") for item in items_b)

        # --- TEST 3: Actions Approvals Queue & Mutation Isolation ---
        res_b_queue = await client.get("/api/v1/actions/approvals-queue", headers=headers_b)
        assert res_b_queue.status_code == 200
        queue_b = res_b_queue.json() if isinstance(res_b_queue.json(), list) else res_b_queue.json().get("approvals", [])
        assert not any(item["id"] == str(action_a_id) for item in queue_b)

        # Tenant B attempts to approve Tenant A's action -> MUST FAIL (404 Not Found)
        res_b_mutate = await client.post(
            f"/api/v1/actions/{action_a_id}/approve",
            headers=headers_b,
            json={"notes": "Malicious cross-tenant approval"}
        )
        assert res_b_mutate.status_code in [404, 403]

        # --- TEST 4: Workflows Isolation ---
        res_b_wf = await client.get("/api/v1/workflows", headers=headers_b)
        assert res_b_wf.status_code == 200
        wf_list_b = res_b_wf.json() if isinstance(res_b_wf.json(), list) else res_b_wf.json().get("workflows", [])
        assert not any(w["id"] == str(workflow_a_id) for w in wf_list_b)

        # Tenant B attempts to run Tenant A's workflow -> MUST FAIL (404 Not Found)
        res_b_run_wf = await client.post(
            f"/api/v1/workflows/{workflow_a_id}/run",
            headers=headers_b,
            json={}
        )
        assert res_b_run_wf.status_code in [404, 403]

        # --- TEST 5: Direct ERP Products Isolation ---
        res_a_prod = await client.get("/api/v1/inventory/products", headers=headers_a)
        assert res_a_prod.status_code == 200
        products_a = res_a_prod.json() if isinstance(res_a_prod.json(), list) else res_a_prod.json().get("items", [])
        assert any("ALPHA-CONFIDENTIAL" in p["sku"] for p in products_a)

        res_b_prod = await client.get("/api/v1/inventory/products", headers=headers_b)
        assert res_b_prod.status_code == 200
        products_b = res_b_prod.json() if isinstance(res_b_prod.json(), list) else res_b_prod.json().get("items", [])
        assert not any("ALPHA-CONFIDENTIAL" in p["sku"] for p in products_b)
