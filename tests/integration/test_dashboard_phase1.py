"""
Phase 1 Integration Tests:
- All dashboard endpoints require authentication (no unauthenticated demo fallback).
- Empty tenant returns real zeros/empty lists.
- No response contains hardcoded mock names ('Apex', 'Quantum', 'Vanguard') or invented metrics.
- Populated tenant metrics accurately reflect canonical database records.
"""

import pytest
from uuid import uuid4
from decimal import Decimal
from datetime import datetime, timezone, date
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from apps.api.main import app
from tests.conftest import ASYNC_TEST_DB_URL
from packages.auth.tokens import create_access_token
from packages.database.models import Organization, User
from packages.database.models.erp.sales import Invoice, Customer, SalesOrder, InvoiceStatus, OrderStatus
from packages.database.models.erp.purchasing import Vendor, PurchaseOrder, PurchaseOrderLine, POStatus
from packages.database.models.erp.inventory import Product, Warehouse, StockLevel
from packages.database.tenant_context import set_tenant_context

APP_DB_URL = ASYNC_TEST_DB_URL.replace("postgres:postgres@", "app_user:app_pass@") if "postgres:postgres@" in ASYNC_TEST_DB_URL else ASYNC_TEST_DB_URL


@pytest.mark.asyncio
async def test_dashboard_unauthenticated_rejected():
    """All dashboard endpoints must return 401 Unauthorized without a valid JWT."""
    endpoints = [
        "/api/v1/dashboard/home",
        "/api/v1/dashboard/finance",
        "/api/v1/dashboard/inventory",
        "/api/v1/dashboard/procurement",
        "/api/v1/dashboard/sales",
        "/api/v1/dashboard/knowledge",
        "/api/v1/dashboard/audit",
        "/api/v1/dashboard/security",
        "/api/v1/dashboard/operations",
        "/api/v1/dashboard/activity",
    ]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for ep in endpoints:
            res = await client.get(ep)
            assert res.status_code == 401, f"Endpoint {ep} allowed unauthenticated access with status {res.status_code}"

        # POST /command must also reject unauthenticated requests
        post_res = await client.post("/api/v1/dashboard/command", json={"query": "test query"})
        assert post_res.status_code == 401, f"POST /command allowed unauthenticated access with status {post_res.status_code}"


@pytest.mark.asyncio
async def test_empty_tenant_returns_zeros_and_no_fake_names():
    """An empty tenant returns zeros/empty states and zero hardcoded fake strings."""
    engine = create_async_engine(ASYNC_TEST_DB_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid4()
    user_id = uuid4()

    async with session_factory() as session:
        await set_tenant_context(session, org_id)
        org = Organization(id=org_id, name="Empty Tenant Ltd", slug=f"empty-{org_id.hex[:6]}", plan="enterprise")
        user = User(
            id=user_id,
            email=f"ceo.{org_id.hex[:6]}@emptysaastest.io",
            organization_id=org_id,
            tenant_id=org_id,
            password_hash="argon2id$mock$passwordhashfortest1234567890",
            first_name="Test",
            last_name="CEO",
            is_active=True
        )
        session.add_all([org, user])
        await session.commit()

    token = create_access_token(user_id=user_id, org_id=org_id, role="owner", email=user.email)
    headers = {"Authorization": f"Bearer {token}"}

    endpoints = [
        "/api/v1/dashboard/home",
        "/api/v1/dashboard/finance",
        "/api/v1/dashboard/inventory",
        "/api/v1/dashboard/procurement",
        "/api/v1/dashboard/sales",
        "/api/v1/dashboard/knowledge",
        "/api/v1/dashboard/operations",
    ]

    fake_strings = ["Apex", "Quantum", "Vanguard", "T-Slot Extrusion", "425,000", "1,425,000", "118,500", "306,500", "89,200", "demo-po-1"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for ep in endpoints:
            res = await client.get(ep, headers=headers)
            assert res.status_code == 200, f"Failed on {ep}: {res.text}"
            raw_text = res.text

            # Check that none of the fake strings exist in any response
            for fake in fake_strings:
                assert fake not in raw_text, f"Found fake string '{fake}' in response of {ep}: {raw_text}"

        # Check Home specific zero values
        home_res = await client.get("/api/v1/dashboard/home", headers=headers)
        home_data = home_res.json()
        assert home_data["total_revenue"] == "$0.00"
        assert home_data["active_orders"] == 0
        assert home_data["inventory_skus"] == 0
        assert home_data["approvals"] == []

        # Check Finance zero values
        fin_res = await client.get("/api/v1/dashboard/finance", headers=headers)
        fin_data = fin_res.json()
        assert fin_data["invoices"] == []
        kpis = {k["label"]: k["value"] for k in fin_data["kpis"]}
        assert kpis["Total Revenue"] == "$0.00"
        assert kpis["Net Profit"] == "$0.00"
        assert kpis["Accounts Receivable"] == "$0.00"
        assert kpis["Accounts Payable"] == "$0.00"

        # Check Inventory zero values
        inv_res = await client.get("/api/v1/dashboard/inventory", headers=headers)
        inv_data = inv_res.json()
        assert inv_data["products"] == []
        inv_kpis = {k["label"]: k["value"] for k in inv_data["kpis"]}
        assert inv_kpis["Active SKUs"] == "0"
        assert inv_kpis["Total Inventory Value"] == "$0.00"
        assert inv_kpis["Low Stock Alerts"] == "0"

        # Check Sales zero values
        sales_res = await client.get("/api/v1/dashboard/sales", headers=headers)
        sales_data = sales_res.json()
        assert sales_data["opportunities"] == []
        sales_kpis = {k["label"]: k["value"] for k in sales_data["kpis"]}
        assert sales_kpis["Pipeline Value"] == "$0.00"
        assert sales_kpis["Active Opportunities"] == "0"


@pytest.mark.asyncio
async def test_dashboard_with_real_tenant_data():
    """Populated tenant records are accurately computed and reflected in dashboard KPIs."""
    engine = create_async_engine(ASYNC_TEST_DB_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid4()
    user_id = uuid4()

    async with session_factory() as session:
        await set_tenant_context(session, org_id)
        org = Organization(id=org_id, name="Real Data Corp", slug=f"real-{org_id.hex[:6]}", plan="enterprise")
        user = User(
            id=user_id,
            email=f"cfo.{org_id.hex[:6]}@realsaas.io",
            organization_id=org_id,
            tenant_id=org_id,
            password_hash="argon2id$mock$passwordhashfortest1234567890",
            first_name="Real",
            last_name="CFO",
            is_active=True
        )
        session.add_all([org, user])
        await session.commit()

    async with session_factory() as session:
        await set_tenant_context(session, org_id)

        # Create Customer & Paid Invoice
        cust = Customer(
            id=uuid4(),
            organization_id=org_id,
            name="Acme Enterprise Client",
            email="billing@acmeclient.com"
        )
        session.add(cust)
        await session.flush()

        inv = Invoice(
            id=uuid4(),
            organization_id=org_id,
            invoice_number=f"INV-{org_id.hex[:4]}-001",
            issue_date=date.today(),
            due_date=date.today(),
            total_amount=Decimal("12500.00"),
            status=InvoiceStatus.PAID
        )
        session.add(inv)

        # Create Product & StockLevel
        prod = Product(
            id=uuid4(),
            organization_id=org_id,
            sku="REAL-SKU-9900",
            name="Precision CNC Milling Bit",
            unit_price=Decimal("150.00"),
            cost_price=Decimal("75.00"),
            is_active=1
        )
        wh = Warehouse(
            id=uuid4(),
            organization_id=org_id,
            name="Main Facility",
            code="WH-MAIN"
        )
        session.add_all([prod, wh])
        await session.flush()

        sl = StockLevel(
            organization_id=org_id,
            product_id=prod.id,
            warehouse_id=wh.id,
            quantity_on_hand=Decimal("40"),
            reorder_point=Decimal("50")  # Should trigger low stock alert
        )
        session.add(sl)

        # Create Vendor & Open PO
        vendor = Vendor(
            id=uuid4(),
            organization_id=org_id,
            name="Global Carbide Suppliers",
            email="sales@globalcarbide.com"
        )
        session.add(vendor)
        await session.flush()

        po = PurchaseOrder(
            id=uuid4(),
            organization_id=org_id,
            vendor_id=vendor.id,
            po_number=f"PO-{org_id.hex[:4]}-001",
            order_date=date.today(),
            status=POStatus.SENT
        )
        session.add(po)
        await session.flush()

        po_line = PurchaseOrderLine(
            id=uuid4(),
            organization_id=org_id,
            order_id=po.id,
            product_id=prod.id,
            quantity=Decimal("20"),
            unit_cost=Decimal("150.00"),
            line_total=Decimal("3000.00")
        )
        session.add(po_line)
        await session.commit()

    token = create_access_token(user_id=user_id, org_id=org_id, role="owner", email=user.email)
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check Home
        home_res = await client.get("/api/v1/dashboard/home", headers=headers)
        assert home_res.status_code == 200
        home_data = home_res.json()
        assert home_data["total_revenue"] == "$12,500.00"
        assert home_data["inventory_skus"] == 1

        # Check Finance
        fin_res = await client.get("/api/v1/dashboard/finance", headers=headers)
        assert fin_res.status_code == 200
        fin_kpis = {k["label"]: k["value"] for k in fin_res.json()["kpis"]}
        assert fin_kpis["Total Revenue"] == "$12,500.00"

        # Check Inventory
        inv_res = await client.get("/api/v1/dashboard/inventory", headers=headers)
        assert inv_res.status_code == 200
        inv_data = inv_res.json()
        assert len(inv_data["products"]) == 1
        assert inv_data["products"][0]["sku"] == "REAL-SKU-9900"
        assert inv_data["products"][0]["stock"] == 40
        assert "Low Stock" in inv_data["products"][0]["status"]
        inv_kpis = {k["label"]: k["value"] for k in inv_data["kpis"]}
        assert inv_kpis["Low Stock Alerts"] == "1"
        assert inv_kpis["Total Inventory Value"] == "$3,000.00"  # 40 * 75.00

        # Check Procurement
        proc_res = await client.get("/api/v1/dashboard/procurement", headers=headers)
        assert proc_res.status_code == 200
        proc_kpis = {k["label"]: k["value"] for k in proc_res.json()["kpis"]}
        assert proc_kpis["Active POs"] == "1"
        assert proc_kpis["Active Suppliers"] == "1"
