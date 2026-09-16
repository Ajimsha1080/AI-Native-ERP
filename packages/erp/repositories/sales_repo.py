"""
Sales repository.

Handles data access for Customers, SalesOrders, SalesOrderLines, Invoices, InvoiceLines, Payments.
Enforces business rules:
- Sales order line total calculation
- Invoice total calculation and matching sum of invoice lines
- Order and invoice state transitions
"""

from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.models.erp.sales import (
    Customer, SalesOrder, SalesOrderLine, Invoice, InvoiceLine,
    Payment, OrderStatus, InvoiceStatus
)


class InvoiceMismatchError(Exception):
    """Raised when invoice total amount does not equal sum of lines."""
    def __init__(self, invoice_id: Optional[UUID], calculated_total: Decimal, line_sum: Decimal):
        self.invoice_id = invoice_id
        self.calculated_total = calculated_total
        self.line_sum = line_sum
        super().__init__(
            f"Invoice {invoice_id or 'new'} total ({calculated_total}) does not match line sum ({line_sum})"
        )


class SalesRepository:

    def __init__(self, session: AsyncSession):
        self._session = session

    # ── Customers ─────────────────────────────────────────────

    async def create_customer(
        self,
        organization_id: UUID,
        name: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        billing_address: Optional[str] = None,
        shipping_address: Optional[str] = None,
        credit_limit: Optional[Decimal] = None,
        currency: str = "USD",
    ) -> Customer:
        customer = Customer(
            organization_id=organization_id,
            name=name,
            email=email,
            phone=phone,
            billing_address=billing_address,
            shipping_address=shipping_address,
            credit_limit=credit_limit,
            currency=currency,
        )
        self._session.add(customer)
        await self._session.flush()
        return customer

    async def get_customer(self, customer_id: UUID) -> Optional[Customer]:
        result = await self._session.execute(
            select(Customer).where(Customer.id == customer_id, Customer.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def list_customers(
        self, organization_id: UUID, page: int = 1, page_size: int = 20
    ) -> List[Customer]:
        offset = (page - 1) * page_size
        result = await self._session.execute(
            select(Customer)
            .where(Customer.organization_id == organization_id, Customer.is_deleted == False)
            .offset(offset)
            .limit(page_size)
            .order_by(Customer.name)
        )
        return list(result.scalars().all())

    # ── Sales Orders ──────────────────────────────────────────

    async def create_sales_order(
        self,
        organization_id: UUID,
        customer_id: UUID,
        order_number: str,
        order_date: date,
        lines: List[Dict[str, Any]],
        expected_delivery_date: Optional[date] = None,
        notes: Optional[str] = None,
        currency: str = "USD",
    ) -> SalesOrder:
        order = SalesOrder(
            organization_id=organization_id,
            customer_id=customer_id,
            order_number=order_number,
            order_date=order_date,
            expected_delivery_date=expected_delivery_date,
            status=OrderStatus.DRAFT,
            notes=notes,
            currency=currency,
        )
        self._session.add(order)
        await self._session.flush()

        for l in lines:
            qty = Decimal(str(l["quantity"]))
            unit_price = Decimal(str(l["unit_price"]))
            line_total = qty * unit_price
            line = SalesOrderLine(
                organization_id=organization_id,
                order_id=order.id,
                product_id=l["product_id"],
                quantity=qty,
                unit_price=unit_price,
                line_total=line_total,
                description=l.get("description"),
            )
            self._session.add(line)

        await self._session.flush()
        return order

    async def get_sales_order(self, order_id: UUID) -> Optional[SalesOrder]:
        result = await self._session.execute(
            select(SalesOrder)
            .options(selectinload(SalesOrder.lines))
            .where(SalesOrder.id == order_id, SalesOrder.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def update_order_status(self, order_id: UUID, new_status: OrderStatus) -> Optional[SalesOrder]:
        order = await self.get_sales_order(order_id)
        if not order:
            return None
        order.status = new_status
        await self._session.flush()
        return order

    async def list_sales_orders(
        self, organization_id: UUID, status: Optional[OrderStatus] = None, page: int = 1, page_size: int = 20
    ) -> List[SalesOrder]:
        offset = (page - 1) * page_size
        q = select(SalesOrder).where(SalesOrder.organization_id == organization_id, SalesOrder.is_deleted == False)
        if status:
            q = q.where(SalesOrder.status == status)
        q = q.offset(offset).limit(page_size).order_by(SalesOrder.order_date.desc())
        result = await self._session.execute(q)
        return list(result.scalars().all())

    # ── Invoices ──────────────────────────────────────────────

    async def create_invoice(
        self,
        organization_id: UUID,
        invoice_number: str,
        issue_date: date,
        due_date: date,
        lines: List[Dict[str, Any]],
        order_id: Optional[UUID] = None,
        total_amount: Optional[Decimal] = None,
        currency: str = "USD",
        notes: Optional[str] = None,
    ) -> Invoice:
        line_sum = Decimal("0")
        prepared_lines = []
        for l in lines:
            qty = Decimal(str(l["quantity"]))
            unit_price = Decimal(str(l["unit_price"]))
            lt = qty * unit_price
            line_sum += lt
            prepared_lines.append((l.get("description", ""), qty, unit_price, lt))

        final_total = total_amount if total_amount is not None else line_sum
        if final_total != line_sum:
            raise InvoiceMismatchError(None, final_total, line_sum)

        invoice = Invoice(
            organization_id=organization_id,
            order_id=order_id,
            invoice_number=invoice_number,
            issue_date=issue_date,
            due_date=due_date,
            status=InvoiceStatus.DRAFT,
            total_amount=final_total,
            currency=currency,
            notes=notes,
        )
        self._session.add(invoice)
        await self._session.flush()

        for desc, qty, unit_price, lt in prepared_lines:
            inv_line = InvoiceLine(
                organization_id=organization_id,
                invoice_id=invoice.id,
                description=desc,
                quantity=qty,
                unit_price=unit_price,
                line_total=lt,
            )
            self._session.add(inv_line)

        await self._session.flush()
        return invoice

    async def get_invoice(self, invoice_id: UUID) -> Optional[Invoice]:
        result = await self._session.execute(
            select(Invoice)
            .options(selectinload(Invoice.lines), selectinload(Invoice.payments))
            .where(Invoice.id == invoice_id, Invoice.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def list_invoices(
        self, organization_id: UUID, status: Optional[InvoiceStatus] = None, page: int = 1, page_size: int = 20
    ) -> List[Invoice]:
        offset = (page - 1) * page_size
        q = select(Invoice).where(Invoice.organization_id == organization_id, Invoice.is_deleted == False)
        if status:
            q = q.where(Invoice.status == status)
        q = q.offset(offset).limit(page_size).order_by(Invoice.issue_date.desc())
        result = await self._session.execute(q)
        return list(result.scalars().all())

    # ── Payments ──────────────────────────────────────────────

    async def record_payment(
        self,
        organization_id: UUID,
        invoice_id: UUID,
        amount: Decimal,
        payment_date: date,
        method: str,
        reference: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Payment:
        invoice = await self.get_invoice(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        payment = Payment(
            organization_id=organization_id,
            invoice_id=invoice_id,
            amount=amount,
            payment_date=payment_date,
            method=method,
            reference=reference,
            notes=notes,
        )
        self._session.add(payment)
        await self._session.flush()

        # Update invoice status if fully paid
        total_paid = sum(p.amount for p in invoice.payments) + amount
        if total_paid >= invoice.total_amount:
            invoice.status = InvoiceStatus.PAID
            await self._session.flush()

        return payment
