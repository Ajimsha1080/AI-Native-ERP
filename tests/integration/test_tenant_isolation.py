import pytest
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from tests.conftest import ASYNC_TEST_DB_URL
from packages.database.tenant_context import set_tenant_context
from packages.database.models import Organization
from packages.database.models.erp.inventory import Product
from packages.erp.repositories.inventory_repo import InventoryRepository

# Connect as app_user (non-superuser) so PostgreSQL RLS is strictly enforced
APP_DB_URL = ASYNC_TEST_DB_URL.replace("postgres:postgres@", "app_user:app_pass@") if "postgres:postgres@" in ASYNC_TEST_DB_URL else ASYNC_TEST_DB_URL


@pytest.mark.asyncio
async def test_rls_tenant_isolation_reads_and_writes():
    """
    Proves that PostgreSQL Row-Level Security (RLS) enforces tenant isolation
    even when repository queries completely omit the organization_id WHERE clause.
    """
    engine = create_async_engine(APP_DB_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    org_a_id = uuid4()
    org_b_id = uuid4()

    # 1. Setup organizations in database
    async with session_factory() as setup_session:
        org_a = Organization(
            id=org_a_id,
            name="Acme Tenant A",
            slug=f"acme-{org_a_id.hex[:6]}",
            plan="enterprise",
            status="active"
        )
        org_b = Organization(
            id=org_b_id,
            name="Beta Tenant B",
            slug=f"beta-{org_b_id.hex[:6]}",
            plan="enterprise",
            status="active"
        )
        setup_session.add_all([org_a, org_b])
        await setup_session.commit()

    # 2. Tenant A creates a product
    product_a_id = None
    async with session_factory() as session_a:
        await set_tenant_context(session_a, org_a_id)
        repo_a = InventoryRepository(session_a)
        
        prod_a = await repo_a.create_product(
            organization_id=org_a_id,
            sku=f"SKU-TENANT-A-{uuid4().hex[:4]}",
            name="Confidential Product A",
            unit_price=Decimal("150.00"),
            cost_price=Decimal("80.00"),
        )
        await session_a.commit()
        product_a_id = prod_a.id

    assert product_a_id is not None

    # 3. Tenant B queries products WITHOUT WHERE organization_id clause:
    # Proves RLS — not just application code — stops the leak!
    async with session_factory() as session_b:
        await set_tenant_context(session_b, org_b_id)
        repo_b = InventoryRepository(session_b)

        # Standard list query for Tenant B
        tenant_b_products = await repo_b.list_products(organization_id=org_b_id)
        assert len(tenant_b_products) == 0

        # DELIBERATE TEST: Query Product table completely omitting organization_id in WHERE clause
        query_without_org_filter = select(Product).where(Product.is_deleted == False)
        res = await session_b.execute(query_without_org_filter)
        unfiltered_products = res.scalars().all()
        unfiltered_ids = [p.id for p in unfiltered_products]
        assert product_a_id not in unfiltered_ids, "RLS FAILURE: Deliberately unfiltered query leaked Tenant A's product to Tenant B!"

        # Direct fetch by ID (get_product has NO organization_id in its WHERE clause)
        fetched_product = await repo_b.get_product(product_a_id)
        assert fetched_product is None, "RLS FAILURE: get_product(product_a_id) returned a cross-tenant product to Tenant B!"

        # Direct raw SQL query with NO WHERE clause
        raw_res = await session_b.execute(text("SELECT id, organization_id FROM products;"))
        rows = raw_res.fetchall()
        for r in rows:
            assert r[1] == org_b_id, f"RLS FAILURE: Raw SELECT leaked product row from organization {r[1]} to Tenant B!"

    # 4. Tenant B attempts to write a product with Tenant A's organization_id (WITH CHECK clause verification)
    async with session_factory() as session_b_write:
        await set_tenant_context(session_b_write, org_b_id)
        
        # Attempting to insert a product with org_a_id while session has app.tenant_id = org_b_id
        # Must be rejected by PostgreSQL RLS WITH CHECK policy
        with pytest.raises(Exception) as exc_info:
            bad_product = Product(
                organization_id=org_a_id,
                sku=f"SPOOF-SKU-{uuid4().hex[:4]}",
                name="Spoofed Product",
                unit_price=Decimal("99.00"),
                cost_price=Decimal("50.00"),
                unit_of_measure="unit",
            )
            session_b_write.add(bad_product)
            await session_b_write.commit()

        error_msg = str(exc_info.value).lower()
        assert "row-level security" in error_msg or "rls" in error_msg or "policy" in error_msg, f"Unexpected error: {exc_info.value}"
        await session_b_write.rollback()

    # 5. Tenant A queries products - must see their own product
    async with session_factory() as session_a_read:
        await set_tenant_context(session_a_read, org_a_id)
        repo_a_read = InventoryRepository(session_a_read)
        
        prod = await repo_a_read.get_product(product_a_id)
        assert prod is not None
        assert prod.id == product_a_id
        assert prod.name == "Confidential Product A"

        # List query under Tenant A session
        prods = await repo_a_read.list_products(organization_id=org_a_id)
        assert any(p.id == product_a_id for p in prods)

    await engine.dispose()
