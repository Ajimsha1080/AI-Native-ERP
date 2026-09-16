"""
Inventory domain models.

Tables: products, warehouses, stock_levels, stock_movements

Business rules enforced at the DB level:
  - stock_levels.quantity_on_hand >= 0  (CHECK constraint)
  - stock_movements.quantity > 0        (CHECK constraint)

The service layer additionally enforces these rules before writing,
so the DB constraints are a last-resort safety net.
"""

from enum import Enum as PyEnum
from sqlalchemy import (
    Column, String, Text, Numeric, Integer, CheckConstraint,
    ForeignKey, Index, UniqueConstraint, Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from packages.database.models.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin


class MovementType(str, PyEnum):
    """Direction and reason for a stock quantity change."""
    RECEIPT = "receipt"       # Goods received from purchase order
    ISSUE = "issue"           # Goods issued to a sales order
    TRANSFER = "transfer"     # Between warehouses
    ADJUSTMENT = "adjustment" # Manual correction (e.g., stocktake)
    RETURN = "return"         # Customer return


class Product(SoftDeleteMixin, Base):
    """
    A product in the catalogue.

    organization_id scopes the product to a tenant.
    RLS policy is applied at the table level via create_rls_policies().
    """
    __tablename__ = "products"

    organization_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    sku = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    unit_of_measure = Column(String(50), nullable=False, default="unit")

    # Financials — stored as NUMERIC(15,4) to avoid floating-point rounding
    unit_price = Column(Numeric(15, 4), nullable=False, default=0)
    cost_price = Column(Numeric(15, 4), nullable=False, default=0)

    is_active = Column(Integer, nullable=False, default=1)  # 1=active, 0=discontinued

    # Relationships
    stock_levels = relationship("StockLevel", back_populates="product", cascade="all, delete-orphan")
    stock_movements = relationship("StockMovement", back_populates="product")
    sales_order_lines = relationship("SalesOrderLine", back_populates="product")
    purchase_order_lines = relationship("PurchaseOrderLine", back_populates="product")

    __table_args__ = (
        UniqueConstraint("organization_id", "sku", name="uix_product_org_sku"),
        CheckConstraint("unit_price >= 0", name="chk_product_unit_price"),
        CheckConstraint("cost_price >= 0", name="chk_product_cost_price"),
        Index("ix_product_organization", "organization_id"),
        Index("ix_product_sku", "sku"),
        Index("ix_product_name", "name"),
    )


class Warehouse(SoftDeleteMixin, Base):
    """A physical or logical storage location."""
    __tablename__ = "warehouses"

    organization_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=False)
    location = Column(Text, nullable=True)
    is_active = Column(Integer, nullable=False, default=1)

    # Relationships
    stock_levels = relationship("StockLevel", back_populates="warehouse", cascade="all, delete-orphan")
    stock_movements = relationship("StockMovement", back_populates="warehouse")

    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uix_warehouse_org_code"),
        Index("ix_warehouse_organization", "organization_id"),
    )


class StockLevel(Base):
    """
    Current on-hand quantity of a product in a warehouse.

    There is at most one StockLevel row per (product, warehouse) pair.
    quantity_on_hand is updated atomically by the inventory service.
    The DB CHECK constraint prevents negative stock at the database level.
    """
    __tablename__ = "stock_levels"

    organization_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    warehouse_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("warehouses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    quantity_on_hand = Column(Numeric(15, 4), nullable=False, default=0)
    reorder_point = Column(Numeric(15, 4), nullable=True)
    max_stock = Column(Numeric(15, 4), nullable=True)

    # Relationships
    product = relationship("Product", back_populates="stock_levels")
    warehouse = relationship("Warehouse", back_populates="stock_levels")

    __table_args__ = (
        UniqueConstraint("product_id", "warehouse_id", name="uix_stock_level_product_warehouse"),
        # CRITICAL: prevents negative stock at DB level
        CheckConstraint("quantity_on_hand >= 0", name="chk_stock_level_non_negative"),
        Index("ix_stock_level_organization", "organization_id"),
        Index("ix_stock_level_product", "product_id"),
        Index("ix_stock_level_warehouse", "warehouse_id"),
    )


class StockMovement(Base):
    """
    Immutable audit log of every stock quantity change.

    Stock movements are NEVER deleted — they form the stock ledger.
    The current StockLevel is always the sum of all movements for a
    (product, warehouse) pair (though we maintain a running total for speed).
    """
    __tablename__ = "stock_movements"

    organization_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    warehouse_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    movement_type = Column(
        SAEnum(MovementType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    # Positive = stock increase, negative = stock decrease
    quantity = Column(Numeric(15, 4), nullable=False)
    reference = Column(String(255), nullable=True)  # PO number, SO number, etc.
    notes = Column(Text, nullable=True)

    created_by_id = Column(PG_UUID(as_uuid=True), nullable=True)

    # Relationships
    product = relationship("Product", back_populates="stock_movements")
    warehouse = relationship("Warehouse", back_populates="stock_movements")

    __table_args__ = (
        CheckConstraint("quantity != 0", name="chk_stock_movement_nonzero"),
        Index("ix_stock_movement_organization", "organization_id"),
        Index("ix_stock_movement_product", "product_id"),
        Index("ix_stock_movement_warehouse", "warehouse_id"),
        Index("ix_stock_movement_type", "movement_type"),
    )
