"""
Integration tests for Inventory Service (Product CRUD, non-negative stock rule).
"""

import pytest
from decimal import Decimal
from uuid import uuid4

from packages.database.core import async_session_scope, create_db_and_tables
from packages.database.tenant_context import set_tenant_context
from packages.erp.services.inventory_service import InventoryService
from packages.erp.repositories.inventory_repo import InsufficientStockError
from packages.database.models.erp.inventory import MovementType


@pytest.mark.asyncio
async def test_inventory_non_negative_stock_enforcement():
    await create_db_and_tables()
    org_id = uuid4()

    async with async_session_scope() as session:
        await set_tenant_context(session, org_id)
        service = InventoryService(session)

        # 1. Create product
        product = await service.create_product(
            organization_id=org_id,
            sku=f"SKU-{uuid4().hex[:6]}",
            name="Industrial Widget",
            unit_price=Decimal("150.00"),
            cost_price=Decimal("90.00"),
        )
        assert product.id is not None

        # 2. Create warehouse
        warehouse = await service.create_warehouse(
            organization_id=org_id,
            name="Main Warehouse",
            code=f"WH-{uuid4().hex[:4]}",
        )
        assert warehouse.id is not None

        # 3. Add initial stock (+50 units)
        level = await service.adjust_stock(
            organization_id=org_id,
            product_id=product.id,
            warehouse_id=warehouse.id,
            delta=Decimal("50"),
            movement_type=MovementType.RECEIPT,
        )
        assert level.quantity_on_hand == Decimal("50")

        # 4. Issue partial stock (-20 units) -> 30 remaining
        level = await service.adjust_stock(
            organization_id=org_id,
            product_id=product.id,
            warehouse_id=warehouse.id,
            delta=Decimal("-20"),
            movement_type=MovementType.ISSUE,
        )
        assert level.quantity_on_hand == Decimal("30")

        # 5. Attempt over-allocation (-35 units when only 30 available) -> MUST raise InsufficientStockError
        with pytest.raises(InsufficientStockError) as exc_info:
            await service.adjust_stock(
                organization_id=org_id,
                product_id=product.id,
                warehouse_id=warehouse.id,
                delta=Decimal("-35"),
                movement_type=MovementType.ISSUE,
            )
        assert "Insufficient stock" in str(exc_info.value)
