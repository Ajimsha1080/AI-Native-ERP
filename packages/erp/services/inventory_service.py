"""
Inventory Service.

Enforces high-level business logic, orchestrates repository calls, and manages transactions.
"""

from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.models.erp.inventory import (
    Product, Warehouse, StockLevel, StockMovement, MovementType
)
from packages.erp.repositories.inventory_repo import (
    InventoryRepository, InsufficientStockError
)


class InventoryService:

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = InventoryRepository(session)

    async def create_product(
        self,
        organization_id: UUID,
        sku: str,
        name: str,
        unit_price: Decimal,
        cost_price: Decimal,
        unit_of_measure: str = "unit",
        description: Optional[str] = None,
        category: Optional[str] = None,
    ) -> Product:
        product = await self.repo.create_product(
            organization_id=organization_id,
            sku=sku,
            name=name,
            unit_price=unit_price,
            cost_price=cost_price,
            unit_of_measure=unit_of_measure,
            description=description,
            category=category,
        )
        await self.session.commit()
        return product

    async def get_product(self, product_id: UUID) -> Optional[Product]:
        return await self.repo.get_product(product_id)

    async def list_products(
        self, organization_id: UUID, page: int = 1, page_size: int = 20
    ) -> List[Product]:
        return await self.repo.list_products(organization_id, page=page, page_size=page_size)

    async def create_warehouse(
        self,
        organization_id: UUID,
        name: str,
        code: str,
        location: Optional[str] = None,
    ) -> Warehouse:
        warehouse = await self.repo.create_warehouse(
            organization_id=organization_id,
            name=name,
            code=code,
            location=location,
        )
        await self.session.commit()
        return warehouse

    async def list_warehouses(self, organization_id: UUID) -> List[Warehouse]:
        return await self.repo.list_warehouses(organization_id)

    async def adjust_stock(
        self,
        organization_id: UUID,
        product_id: UUID,
        warehouse_id: UUID,
        delta: Decimal,
        movement_type: MovementType,
        reference: Optional[str] = None,
        notes: Optional[str] = None,
        created_by_id: Optional[UUID] = None,
    ) -> StockLevel:
        """
        Adjust stock with non-negative validation and create movement audit record.
        """
        level = await self.repo.adjust_stock(
            organization_id=organization_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            delta=delta,
            movement_type=movement_type,
            reference=reference,
            notes=notes,
            created_by_id=created_by_id,
        )
        await self.session.commit()
        return level

    async def list_stock_levels(
        self, organization_id: UUID, warehouse_id: Optional[UUID] = None
    ) -> List[StockLevel]:
        return await self.repo.list_stock_levels(organization_id, warehouse_id=warehouse_id)

    async def list_stock_movements(
        self,
        organization_id: UUID,
        product_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> List[StockMovement]:
        return await self.repo.list_stock_movements(
            organization_id, product_id=product_id, page=page, page_size=page_size
        )
