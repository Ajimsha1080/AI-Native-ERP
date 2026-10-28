"""
Phase 4 Integration Tests:
- Connecting as app_user (NOSUPERUSER, NOBYPASSRLS).
- Committing mid-request: after_begin hook re-applies app.tenant_id, keeping tenant isolated.
- Cross-tenant read and write blocked by Row-Level Security.
"""

import pytest
from uuid import uuid4
from decimal import Decimal
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text, select

from tests.conftest import ASYNC_TEST_DB_URL
from packages.database.models import Organization, User
from packages.database.models.erp.inventory import Product, Warehouse, StockLevel
from packages.database.models.erp.sales import Customer
from packages.database.tenant_context import set_tenant_context

APP_USER_DB_URL = ASYNC_TEST_DB_URL.replace("postgres:postgres@", "app_user:app_pass@") if "postgres:postgres@" in ASYNC_TEST_DB_URL else ASYNC_TEST_DB_URL


@pytest.mark.asyncio
async def test_app_user_is_non_superuser_and_nobypassrls():
    """Verify app_user is a login role without superuser or bypassrls privileges."""
    engine = create_async_engine(APP_USER_DB_URL, echo=False)
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"))
        row = res.fetchone()
        assert row is not None
        assert row[0] == "app_user"
        assert row[1] is False, "app_user must NOT be a superuser"
        assert row[2] is False, "app_user must NOT have bypassrls"


@pytest.mark.asyncio
async def test_tenant_isolation_survives_commit_mid_request_as_app_user():
    """
    Connect as app_user, set tenant context, commit mid-request, query again.
    Verifies that the SQLAlchemy after_begin hook re-applies app.tenant_id and preserves RLS isolation.
    """
    # 1. Setup two distinct tenants as admin/migration owner
    admin_engine = create_async_engine(ASYNC_TEST_DB_URL, echo=False)
    admin_session_factory = async_sessionmaker(admin_engine, class_=AsyncSession, expire_on_commit=False)

    org_a = uuid4()
    org_b = uuid4()

    async with admin_session_factory() as session:
        await set_tenant_context(session, org_a)
        org1 = Organization(id=org_a, name="Tenant A Corp", slug=f"tenant-a-{org_a.hex[:6]}")
        org2 = Organization(id=org_b, name="Tenant B Corp", slug=f"tenant-b-{org_b.hex[:6]}")
        session.add_all([org1, org2])
        await session.commit()

        # Seed data for Tenant A
        cust_a = Customer(id=uuid4(), organization_id=org_a, name="Customer Alpha of Tenant A", email="cust.a@alpha.io")
        # Seed data for Tenant B
        cust_b = Customer(id=uuid4(), organization_id=org_b, name="Customer Beta of Tenant B", email="cust.b@beta.io")
        session.add_all([cust_a, cust_b])
        await session.commit()

    # 2. Connect strictly as app_user (enforcing RLS)
    app_engine = create_async_engine(APP_USER_DB_URL, echo=False)
    app_session_factory = async_sessionmaker(app_engine, class_=AsyncSession, expire_on_commit=False)

    async with app_session_factory() as session:
        # Set tenant context to Tenant A
        await set_tenant_context(session, org_a)

        # First query: should only see Tenant A's customer
        res1 = await session.execute(select(Customer))
        customers1 = res1.scalars().all()
        assert len(customers1) == 1
        assert customers1[0].name == "Customer Alpha of Tenant A"
        assert customers1[0].organization_id == org_a

        # Commit mid-request (this closes the PostgreSQL transaction and resets session_local settings)
        await session.commit()

        # Query again after commit without explicitly re-calling set_tenant_context:
        # The after_begin hook MUST automatically re-apply app.tenant_id from session.info!
        res2 = await session.execute(select(Customer))
        customers2 = res2.scalars().all()
        assert len(customers2) == 1
        assert customers2[0].name == "Customer Alpha of Tenant A"
        assert customers2[0].organization_id == org_a

        # Tenant B's customer MUST NEVER be visible
        for c in customers2:
            assert c.organization_id != org_b, "Tenant isolation leak: Tenant B customer visible to Tenant A!"


@pytest.mark.asyncio
async def test_cross_tenant_write_blocked_by_rls_as_app_user():
    """
    Connecting as app_user with Tenant A context:
    Attempting to insert a row with Tenant B's organization_id violates RLS WITH CHECK policy.
    """
    admin_engine = create_async_engine(ASYNC_TEST_DB_URL, echo=False)
    admin_session_factory = async_sessionmaker(admin_engine, class_=AsyncSession, expire_on_commit=False)

    org_a = uuid4()
    org_b = uuid4()

    async with admin_session_factory() as session:
        org1 = Organization(id=org_a, name="Write Org A", slug=f"write-a-{org_a.hex[:6]}")
        org2 = Organization(id=org_b, name="Write Org B", slug=f"write-b-{org_b.hex[:6]}")
        session.add_all([org1, org2])
        await session.commit()

    app_engine = create_async_engine(APP_USER_DB_URL, echo=False)
    app_session_factory = async_sessionmaker(app_engine, class_=AsyncSession, expire_on_commit=False)

    async with app_session_factory() as session:
        # Act as Tenant A
        await set_tenant_context(session, org_a)

        # Attempt to insert a Customer with Tenant B's organization_id
        cross_tenant_customer = Customer(
            id=uuid4(),
            organization_id=org_b,
            name="Rogue Customer Infiltration",
            email="rogue@infiltrate.io"
        )
        session.add(cross_tenant_customer)

        # Under PostgreSQL RLS WITH CHECK, this INSERT must be rejected
        with pytest.raises(Exception) as exc_info:
            await session.commit()

        # Verify it failed due to RLS check policy violation
        err_str = str(exc_info.value).lower()
        assert "row-level security" in err_str or "policy" in err_str or "violates" in err_str
