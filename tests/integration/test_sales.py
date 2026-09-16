"""
Integration tests for Sales Service (Orders, Invoices, line sums validation, and payments).
"""

import pytest
from decimal import Decimal
from uuid import uuid4
from datetime import date

from packages.database.core import async_session_scope, create_db_and_tables
from packages.database.tenant_context import set_tenant_context
from packages.erp.services.sales_service import SalesService
from packages.erp.repositories.sales_repo import InvoiceMismatchError
from packages.database.models.erp.sales import OrderStatus, InvoiceStatus


@pytest.mark.asyncio
async def test_sales_invoice_line_sum_matching_and_payments():
    await create_db_and_tables()
    org_id = uuid4()

    async with async_session_scope() as session:
        await set_tenant_context(session, org_id)
        service = SalesService(session)

        # 1. Create customer
        customer = await service.create_customer(
            organization_id=org_id,
            name="Acme Corp",
            email="billing@acme.com",
        )
        assert customer.id is not None

        # 2. Valid invoice (Line sum: 2 * 100 + 1 * 50 = 250)
        lines = [
            {"description": "Item A", "quantity": Decimal("2"), "unit_price": Decimal("100.00")},
            {"description": "Item B", "quantity": Decimal("1"), "unit_price": Decimal("50.00")},
        ]
        invoice = await service.create_invoice(
            organization_id=org_id,
            invoice_number=f"INV-{uuid4().hex[:6]}",
            issue_date=date.today(),
            due_date=date.today(),
            lines=lines,
            total_amount=Decimal("250.00"),
        )
        assert invoice.total_amount == Decimal("250.00")
        assert invoice.status == InvoiceStatus.DRAFT

        # 3. Invalid invoice (Calculated total 300 does not match line sum 250) -> MUST raise InvoiceMismatchError
        with pytest.raises(InvoiceMismatchError):
            await service.create_invoice(
                organization_id=org_id,
                invoice_number=f"INV-{uuid4().hex[:6]}",
                issue_date=date.today(),
                due_date=date.today(),
                lines=lines,
                total_amount=Decimal("300.00"),
            )

        # 4. Record full payment -> invoice status transitions to PAID
        payment = await service.record_payment(
            organization_id=org_id,
            invoice_id=invoice.id,
            amount=Decimal("250.00"),
            payment_date=date.today(),
            method="wire_transfer",
        )
        assert payment.amount == Decimal("250.00")
        assert invoice.status == InvoiceStatus.PAID
