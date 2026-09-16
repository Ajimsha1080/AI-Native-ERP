"""
Sales domain models.

Tables: customers, sales_orders, sales_order_lines, invoices, invoice_lines, payments

Business rules:
  - SalesOrderLine.line_total == quantity * unit_price  (enforced in service, checked in DB)
  - Invoice.total_amount == sum(InvoiceLine.line_total)  (enforced in service)
  - Order status is a state machine: draft → confirmed → shipped → delivered
  - Invoice status: draft → sent → paid | overdue | void
"""

from enum import Enum as PyEnum
from sqlalchemy import (
    Column, String, Text, Numeric, Date, DateTime,
    ForeignKey, CheckConstraint, Index, Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from packages.database.models.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin


class OrderStatus(str, PyEnum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class InvoiceStatus(str, PyEnum):
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
    VOID = "void"


class Customer(SoftDeleteMixin, Base):
    """A customer (B2B or B2C) belonging to a tenant organisation."""
    __tablename__ = "customers"

    organization_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    billing_address = Column(Text, nullable=True)
    shipping_address = Column(Text, nullable=True)
    credit_limit = Column(Numeric(15, 2), nullable=True)
    currency = Column(String(3), nullable=False, default="USD")

    # Relationships
    sales_orders = relationship("SalesOrder", back_populates="customer")

    __table_args__ = (
        Index("ix_customer_organization", "organization_id"),
        Index("ix_customer_email", "email"),
    )


class SalesOrder(SoftDeleteMixin, Base):
    """
    A sales order from a customer.

    Status flows: draft → confirmed → shipped → delivered
    Cancellation is allowed from draft or confirmed.
    """
    __tablename__ = "sales_orders"

    organization_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    order_number = Column(String(50), nullable=False)
    order_date = Column(Date, nullable=False)
    expected_delivery_date = Column(Date, nullable=True)
    status = Column(
        SAEnum(OrderStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=OrderStatus.DRAFT,
    )
    notes = Column(Text, nullable=True)
    currency = Column(String(3), nullable=False, default="USD")

    # Relationships
    customer = relationship("Customer", back_populates="sales_orders")
    lines = relationship("SalesOrderLine", back_populates="order", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="order")

    __table_args__ = (
        Index("ix_sales_order_organization", "organization_id"),
        Index("ix_sales_order_customer", "customer_id"),
        Index("ix_sales_order_status", "status"),
    )


class SalesOrderLine(Base):
    """A line item on a sales order."""
    __tablename__ = "sales_order_lines"

    organization_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("sales_orders.id", ondelete="CASCADE"),
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
    unit_price = Column(Numeric(15, 4), nullable=False)
    # line_total is stored (not computed) to preserve historical pricing
    # The service enforces line_total == quantity * unit_price before saving
    line_total = Column(Numeric(15, 4), nullable=False)
    description = Column(Text, nullable=True)

    # Relationships
    order = relationship("SalesOrder", back_populates="lines")
    product = relationship("Product", back_populates="sales_order_lines")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_sol_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="chk_sol_unit_price"),
        CheckConstraint("line_total >= 0", name="chk_sol_line_total"),
        Index("ix_sales_order_line_order", "order_id"),
        Index("ix_sales_order_line_product", "product_id"),
    )


class Invoice(SoftDeleteMixin, Base):
    """
    A billing document issued against a sales order.

    total_amount must equal the sum of all InvoiceLine.line_total values.
    This is enforced by the sales service before committing.
    """
    __tablename__ = "invoices"

    organization_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("sales_orders.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    invoice_number = Column(String(50), nullable=False)
    issue_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    status = Column(
        SAEnum(InvoiceStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=InvoiceStatus.DRAFT,
    )
    total_amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    notes = Column(Text, nullable=True)

    # Relationships
    order = relationship("SalesOrder", back_populates="invoices")
    lines = relationship("InvoiceLine", back_populates="invoice", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="invoice")

    __table_args__ = (
        CheckConstraint("total_amount >= 0", name="chk_invoice_total_non_negative"),
        Index("ix_invoice_organization", "organization_id"),
        Index("ix_invoice_order", "order_id"),
        Index("ix_invoice_status", "status"),
    )


class InvoiceLine(Base):
    """A line item on an invoice."""
    __tablename__ = "invoice_lines"

    organization_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invoice_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    description = Column(Text, nullable=False)
    quantity = Column(Numeric(15, 4), nullable=False)
    unit_price = Column(Numeric(15, 4), nullable=False)
    line_total = Column(Numeric(15, 4), nullable=False)

    # Relationships
    invoice = relationship("Invoice", back_populates="lines")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_invoice_line_quantity_positive"),
        CheckConstraint("line_total >= 0", name="chk_invoice_line_total"),
        Index("ix_invoice_line_invoice", "invoice_id"),
    )


class Payment(Base):
    """A payment received against an invoice."""
    __tablename__ = "payments"

    organization_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invoice_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    amount = Column(Numeric(15, 2), nullable=False)
    payment_date = Column(Date, nullable=False)
    method = Column(String(50), nullable=False)   # cash, bank_transfer, card, etc.
    reference = Column(String(255), nullable=True) # Bank reference / transaction id
    notes = Column(Text, nullable=True)

    # Relationships
    invoice = relationship("Invoice", back_populates="payments")

    __table_args__ = (
        CheckConstraint("amount > 0", name="chk_payment_amount_positive"),
        Index("ix_payment_organization", "organization_id"),
        Index("ix_payment_invoice", "invoice_id"),
    )
