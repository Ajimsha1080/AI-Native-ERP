"""
Purchasing domain models.

Tables: vendors, purchase_orders, purchase_order_lines, goods_receipts, goods_receipt_lines

Business rules:
  - GoodsReceipt triggers StockMovements (handled in purchasing service)
  - PO status: draft → sent → acknowledged → partially_received → received | cancelled
"""

from enum import Enum as PyEnum
from sqlalchemy import (
    Column, String, Text, Numeric, Date, ForeignKey,
    CheckConstraint, Index, Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from packages.database.models.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin


class POStatus(str, PyEnum):
    DRAFT = "draft"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    PARTIALLY_RECEIVED = "partially_received"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class Vendor(SoftDeleteMixin, Base):
    """A supplier / vendor that products are purchased from."""
    __tablename__ = "vendors"

    organization_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    payment_terms = Column(String(100), nullable=True)  # e.g. "Net 30"
    currency = Column(String(3), nullable=False, default="USD")
    tax_id = Column(String(100), nullable=True)

    # Relationships
    purchase_orders = relationship("PurchaseOrder", back_populates="vendor")

    __table_args__ = (
        Index("ix_vendor_organization", "organization_id"),
    )


class PurchaseOrder(SoftDeleteMixin, Base):
    """A purchase order sent to a vendor."""
    __tablename__ = "purchase_orders"

    organization_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vendor_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("vendors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    po_number = Column(String(50), nullable=False)
    order_date = Column(Date, nullable=False)
    expected_delivery_date = Column(Date, nullable=True)
    status = Column(
        SAEnum(POStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=POStatus.DRAFT,
    )
    notes = Column(Text, nullable=True)
    currency = Column(String(3), nullable=False, default="USD")

    # Relationships
    vendor = relationship("Vendor", back_populates="purchase_orders")
    lines = relationship("PurchaseOrderLine", back_populates="order", cascade="all, delete-orphan")
    receipts = relationship("GoodsReceipt", back_populates="purchase_order")

    __table_args__ = (
        Index("ix_po_organization", "organization_id"),
        Index("ix_po_vendor", "vendor_id"),
        Index("ix_po_status", "status"),
    )


class PurchaseOrderLine(Base):
    """A line item on a purchase order."""
    __tablename__ = "purchase_order_lines"

    organization_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("purchase_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    quantity = Column(Numeric(15, 4), nullable=False)
    unit_cost = Column(Numeric(15, 4), nullable=False)
    line_total = Column(Numeric(15, 4), nullable=False)

    # Relationships
    order = relationship("PurchaseOrder", back_populates="lines")
    product = relationship("Product", back_populates="purchase_order_lines")
    receipt_lines = relationship("GoodsReceiptLine", back_populates="po_line")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_pol_quantity_positive"),
        CheckConstraint("unit_cost >= 0", name="chk_pol_unit_cost"),
        CheckConstraint("line_total >= 0", name="chk_pol_line_total"),
        Index("ix_pol_order", "order_id"),
    )


class GoodsReceipt(Base):
    """
    Record of goods physically received against a purchase order.

    Creating a GoodsReceipt triggers StockMovement records
    (one per line) via the purchasing service.
    """
    __tablename__ = "goods_receipts"

    organization_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    purchase_order_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("purchase_orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    received_date = Column(Date, nullable=False)
    received_by_id = Column(PG_UUID(as_uuid=True), nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    purchase_order = relationship("PurchaseOrder", back_populates="receipts")
    lines = relationship("GoodsReceiptLine", back_populates="receipt", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_gr_organization", "organization_id"),
        Index("ix_gr_po", "purchase_order_id"),
    )


class GoodsReceiptLine(Base):
    """A line on a goods receipt — quantity actually received for a PO line."""
    __tablename__ = "goods_receipt_lines"

    organization_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    receipt_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("goods_receipts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    po_line_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("purchase_order_lines.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    quantity_received = Column(Numeric(15, 4), nullable=False)
    # Destination warehouse for this receipt
    warehouse_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Relationships
    receipt = relationship("GoodsReceipt", back_populates="lines")
    po_line = relationship("PurchaseOrderLine", back_populates="receipt_lines")

    __table_args__ = (
        CheckConstraint("quantity_received > 0", name="chk_grl_quantity_positive"),
        Index("ix_grl_receipt", "receipt_id"),
    )
