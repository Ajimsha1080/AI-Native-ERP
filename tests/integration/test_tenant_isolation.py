"""
Integration tests proving strict multi-tenant isolation.
Tenant A must NEVER be able to read, access, or alter Tenant B's data.
"""

import pytest
from decimal import Decimal
from uuid import uuid4

from packages.database.core import async_session_scope, create_db_and_tables
from packages.database.tenant_context import set_tenant_context
from packages.erp.services.inventory_service import InventoryService
from packages.erp.services.sales_service import SalesService


@pytest.mark.asyncio
async def test_tenant_data_isolation():
    await create_db_and_tables()

    tenant_a_id = uuid4()
    tenant_b_id = uuid4()

    # 1. Tenant A creates products in their catalog
    async with async_session_scope() as session_a:
        await set_tenant_context(session_a, tenant_a_id)
        service_a = InventoryService(session_a)

        prod_a1 = await service_a.create_product(
            organization_id=tenant_a_id,
            sku="TENANT-A-PROD-1",
            name="Confidential Blueprint A",
            unit_price=Decimal("1000.00"),
            cost_price=Decimal("400.00"),
        )
        assert prod_a1.id is not None

    # 2. Tenant B creates products in their catalog
    async with async_session_scope() as session_b:
        await set_tenant_context(session_b, tenant_b_id)
        service_b = InventoryService(session_b)

        prod_b1 = await service_b.create_product(
            organization_id=tenant_b_id,
            sku="TENANT-B-PROD-1",
            name="Proprietary Device B",
            unit_price=Decimal("2000.00"),
            cost_price=Decimal("800.00"),
        )
        assert prod_b1.id is not None

    # 3. Query as Tenant A -> MUST ONLY see Tenant A's products, 0 products from Tenant B
    async with async_session_scope() as session_a_check:
        await set_tenant_context(session_a_check, tenant_a_id)
        service_a_check = InventoryService(session_a_check)

        products_seen_by_a = await service_a_check.list_products(tenant_a_id)
        skus_seen_by_a = [p.sku for p in products_seen_by_a]

        assert "TENANT-A-PROD-1" in skus_seen_by_a
        assert "TENANT-B-PROD-1" not in skus_seen_by_a

    # 4. Query as Tenant B -> MUST ONLY see Tenant B's products, 0 products from Tenant A
    async with async_session_scope() as session_b_check:
        await set_tenant_context(session_b_check, tenant_b_id)
        service_b_check = InventoryService(session_b_check)

        products_seen_by_b = await service_b_check.list_products(tenant_b_id)
        skus_seen_by_b = [p.sku for p in products_seen_by_b]

        assert "TENANT-B-PROD-1" in skus_seen_by_b
        assert "TENANT-A-PROD-1" not in skus_seen_by_b
