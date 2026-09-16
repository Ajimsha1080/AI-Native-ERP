"""
Inventory repository.

All methods accept an AsyncSession that must already have tenant context set
(via set_tenant_context). RLS policies ensure cross-tenant data leakage is
impossible even if the application layer makes a mistake.

Key business rule:
  adjust_stock() raises InsufficientStockError if the adjustment would
  result in quantity_on_hand < 0. The DB CHECK constraint is a last-resort
  safety net — the service raises the error first with a useful message.
"""

from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.models.erp.inventory import (
    Product, Warehouse, StockLevel, StockMovement, MovementType
)


class InsufficientStockError(Exception):
    """Raised when an adjustment would cause negative stock."""
    def __init__(self, product_id: UUID, warehouse_id: UUID, available: Decimal, requested: Decimal):
        self.product_id = product_id
        self.warehouse_id = warehouse_id
        self.available = available
        self.requested = requested
        super().__init__(
            f"Insufficient stock for product {product_id} in warehouse {warehouse_id}: "
            f"available={available}, requested={requested}"
        )


class InventoryRepository:
    """
    Data access layer for inventory domain.

    All methods require the session to already have tenant context applied.
    Never adds organization_id to queries — RLS handles isolation.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    # ── Products ──────────────────────────────────────────────

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
        product = Product(
            organization_id=organization_id,
            sku=sku,
            name=name,
            unit_price=unit_price,
            cost_price=cost_price,
            unit_of_measure=unit_of_measure,
            description=description,
            category=category,
        )
        self._session.add(product)
        await self._session.flush()
        return product

    async def get_product(self, product_id: UUID) -> Optional[Product]:
        result = await self._session.execute(
            select(Product).where(Product.id == product_id, Product.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def list_products(
        self, organization_id: UUID, page: int = 1, page_size: int = 20
    ) -> list[Product]:
        offset = (page - 1) * page_size
        result = await self._session.execute(
            select(Product)
            .where(Product.organization_id == organization_id, Product.is_deleted == False)
            .offset(offset)
            .limit(page_size)
            .order_by(Product.name)
        )
        return list(result.scalars().all())

    async def update_product(self, product_id: UUID, **fields) -> Optional[Product]:
        product = await self.get_product(product_id)
        if not product:
            return None
        for key, value in fields.items():
            setattr(product, key, value)
        await self._session.flush()
        return product

    async def soft_delete_product(self, product_id: UUID) -> bool:
        product = await self.get_product(product_id)
        if not product:
            return False
        product.is_deleted = True
        from datetime import datetime, timezone
        product.deleted_at = datetime.now(timezone.utc)
        await self._session.flush()
        return True

    # ── Warehouses ────────────────────────────────────────────

    async def create_warehouse(
        self,
        organization_id: UUID,
        name: str,
        code: str,
        location: Optional[str] = None,
    ) -> Warehouse:
        warehouse = Warehouse(
            organization_id=organization_id,
            name=name,
            code=code,
            location=location,
        )
        self._session.add(warehouse)
        await self._session.flush()
        return warehouse

    async def get_warehouse(self, warehouse_id: UUID) -> Optional[Warehouse]:
        result = await self._session.execute(
            select(Warehouse).where(Warehouse.id == warehouse_id, Warehouse.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def list_warehouses(self, organization_id: UUID) -> list[Warehouse]:
        result = await self._session.execute(
            select(Warehouse)
            .where(Warehouse.organization_id == organization_id, Warehouse.is_deleted == False)
            .order_by(Warehouse.name)
        )
        return list(result.scalars().all())

    # ── Stock Levels ──────────────────────────────────────────

    async def get_stock_level(
        self, product_id: UUID, warehouse_id: UUID
    ) -> Optional[StockLevel]:
        result = await self._session.execute(
            select(StockLevel).where(
                StockLevel.product_id == product_id,
                StockLevel.warehouse_id == warehouse_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create_stock_level(
        self, organization_id: UUID, product_id: UUID, warehouse_id: UUID
    ) -> StockLevel:
        level = await self.get_stock_level(product_id, warehouse_id)
        if level is None:
            level = StockLevel(
                organization_id=organization_id,
                product_id=product_id,
                warehouse_id=warehouse_id,
                quantity_on_hand=Decimal("0"),
            )
            self._session.add(level)
            await self._session.flush()
        return level

    async def list_stock_levels(
        self, organization_id: UUID, warehouse_id: Optional[UUID] = None
    ) -> list[StockLevel]:
        q = select(StockLevel).where(StockLevel.organization_id == organization_id)
        if warehouse_id:
            q = q.where(StockLevel.warehouse_id == warehouse_id)
        result = await self._session.execute(q)
        return list(result.scalars().all())

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
        Atomically adjust stock level and create an immutable stock movement.

        Raises:
            InsufficientStockError: If delta is negative and would result in
                                    quantity_on_hand < 0.
        """
        level = await self.get_or_create_stock_level(organization_id, product_id, warehouse_id)

        new_qty = level.quantity_on_hand + delta
        if new_qty < 0:
            raise InsufficientStockError(product_id, warehouse_id, level.quantity_on_hand, abs(delta))

        level.quantity_on_hand = new_qty

        movement = StockMovement(
            organization_id=organization_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            movement_type=movement_type,
            quantity=delta,
            reference=reference,
            notes=notes,
            created_by_id=created_by_id,
        )
        self._session.add(movement)
        await self._session.flush()
        return level

    async def list_stock_movements(
        self,
        organization_id: UUID,
        product_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> list[StockMovement]:
        q = select(StockMovement).where(StockMovement.organization_id == organization_id)
        if product_id:
            q = q.where(StockMovement.product_id == product_id)
        q = q.order_by(StockMovement.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self._session.execute(q)
        return list(result.scalars().all())
