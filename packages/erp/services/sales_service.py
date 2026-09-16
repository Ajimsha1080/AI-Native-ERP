"""
Sales Service.

Enforces business logic for customer lifecycle, orders, invoice generation & validation, and payment reconciliation.
"""

from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.models.erp.sales import (
    Customer, SalesOrder, Invoice, Payment, OrderStatus, InvoiceStatus
)
from packages.erp.repositories.sales_repo import (
    SalesRepository, InvoiceMismatchError
)


class SalesService:

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = SalesRepository(session)

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
        customer = await self.repo.create_customer(
            organization_id=organization_id,
            name=name,
            email=email,
            phone=phone,
            billing_address=billing_address,
            shipping_address=shipping_address,
            credit_limit=credit_limit,
            currency=currency,
        )
        await self.session.commit()
        return customer

    async def list_customers(
        self, organization_id: UUID, page: int = 1, page_size: int = 20
    ) -> List[Customer]:
        return await self.repo.list_customers(organization_id, page=page, page_size=page_size)

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
        order = await self.repo.create_sales_order(
            organization_id=organization_id,
            customer_id=customer_id,
            order_number=order_number,
            order_date=order_date,
            lines=lines,
            expected_delivery_date=expected_delivery_date,
            notes=notes,
            currency=currency,
        )
        await self.session.commit()
        return order

    async def confirm_sales_order(self, order_id: UUID) -> SalesOrder:
        order = await self.repo.update_order_status(order_id, OrderStatus.CONFIRMED)
        if not order:
            raise ValueError(f"Sales order {order_id} not found")
        await self.session.commit()
        return order

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
        invoice = await self.repo.create_invoice(
            organization_id=organization_id,
            invoice_number=invoice_number,
            issue_date=issue_date,
            due_date=due_date,
            lines=lines,
            order_id=order_id,
            total_amount=total_amount,
            currency=currency,
            notes=notes,
        )
        await self.session.commit()
        return invoice

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
        payment = await self.repo.record_payment(
            organization_id=organization_id,
            invoice_id=invoice_id,
            amount=amount,
            payment_date=payment_date,
            method=method,
            reference=reference,
            notes=notes,
        )
        await self.session.commit()
        return payment

    async def list_sales_orders(
        self, organization_id: UUID, status: Optional[OrderStatus] = None, page: int = 1, page_size: int = 20
    ) -> List[SalesOrder]:
        return await self.repo.list_sales_orders(organization_id, status=status, page=page, page_size=page_size)

    async def list_invoices(
        self, organization_id: UUID, status: Optional[InvoiceStatus] = None, page: int = 1, page_size: int = 20
    ) -> List[Invoice]:
        return await self.repo.list_invoices(organization_id, status=status, page=page, page_size=page_size)
