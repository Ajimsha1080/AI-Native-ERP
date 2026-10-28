"""
Typed agent tools calling the service layer directly.
No raw SQL execution from agents.
All state-changing write operations create an Action in APPROVAL_REQUIRED and never execute directly.
"""

from decimal import Decimal
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import date

from packages.database.core import AsyncSessionLocal
from packages.database.tenant_context import set_tenant_context
from packages.erp.services.inventory_service import InventoryService
from packages.erp.services.sales_service import SalesService
from packages.erp.services.purchasing_service import PurchasingService
from packages.erp.services.accounting_service import AccountingService
from packages.database.models.erp.inventory import MovementType
from packages.database.models.erp.accounting import AccountType
from packages.agents.approval_service import propose_state_changing_action


# ── Inventory Tools ───────────────────────────────────────────

async def tool_list_products(organization_id: UUID) -> List[Dict[str, Any]]:
    """Get list of active inventory products."""
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, organization_id)
        service = InventoryService(session)
        products = await service.list_products(organization_id)
        return [{"id": str(p.id), "sku": p.sku, "name": p.name, "unit_price": float(p.unit_price)} for p in products]


async def tool_check_stock(organization_id: UUID, warehouse_id: Optional[UUID] = None) -> List[Dict[str, Any]]:
    """Check stock levels across warehouses."""
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, organization_id)
        service = InventoryService(session)
        levels = await service.list_stock_levels(organization_id, warehouse_id=warehouse_id)
        return [{"product_id": str(l.product_id), "warehouse_id": str(l.warehouse_id), "quantity": float(l.quantity_on_hand)} for l in levels]


async def tool_adjust_stock(
    organization_id: UUID,
    product_id: UUID,
    warehouse_id: UUID,
    delta: float,
    reason: str,
    requested_by_id: Optional[UUID] = None,
) -> Dict[str, Any]:
    """
    Adjust product stock quantity.
    State-changing tool: NEVER executes directly. Creates an approval request.
    """
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, organization_id)
        action = await propose_state_changing_action(
            session=session,
            organization_id=organization_id,
            tool_name="adjust_stock",
            inputs={
                "product_id": str(product_id),
                "warehouse_id": str(warehouse_id),
                "delta": delta,
                "reason": reason,
            },
            requested_by_id=requested_by_id,
            description=f"Stock adjustment: {delta:+g} units for product {product_id} ({reason})",
        )
        return {
            "status": "approval_required",
            "action_id": str(action.id),
            "tool_name": "adjust_stock",
            "message": "Stock adjustment requires human authorization before database execution."
        }


# ── Sales Tools ───────────────────────────────────────────────

async def tool_list_customers(organization_id: UUID) -> List[Dict[str, Any]]:
    """List customers registered with the tenant."""
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, organization_id)
        service = SalesService(session)
        customers = await service.list_customers(organization_id)
        return [{"id": str(c.id), "name": c.name, "email": c.email} for c in customers]


async def tool_list_invoices(organization_id: UUID) -> List[Dict[str, Any]]:
    """List recent invoices."""
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, organization_id)
        service = SalesService(session)
        invoices = await service.list_invoices(organization_id)
        return [{"id": str(i.id), "invoice_number": i.invoice_number, "status": str(i.status.value), "total": float(i.total_amount)} for i in invoices]


async def tool_record_payment(
    organization_id: UUID,
    invoice_id: UUID,
    amount: float,
    payment_method: str = "wire_transfer",
    requested_by_id: Optional[UUID] = None,
) -> Dict[str, Any]:
    """
    Record payment against an invoice.
    State-changing tool: NEVER executes directly. Creates an approval request.
    """
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, organization_id)
        action = await propose_state_changing_action(
            session=session,
            organization_id=organization_id,
            tool_name="record_payment",
            inputs={
                "invoice_id": str(invoice_id),
                "amount": amount,
                "payment_method": payment_method,
            },
            requested_by_id=requested_by_id,
            description=f"Payment disbursement of ${amount:,.2f} for invoice {invoice_id}",
        )
        return {
            "status": "approval_required",
            "action_id": str(action.id),
            "tool_name": "record_payment",
            "amount": amount,
            "message": f"Payment disbursement of ${amount:,.2f} requires human approval."
        }


# ── Purchasing Tools ──────────────────────────────────────────

async def tool_list_vendors(organization_id: UUID) -> List[Dict[str, Any]]:
    """List approved vendors."""
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, organization_id)
        service = PurchasingService(session)
        vendors = await service.list_vendors(organization_id)
        return [{"id": str(v.id), "name": v.name, "email": v.email} for v in vendors]


async def tool_create_purchase_order(
    organization_id: UUID,
    vendor_id: UUID,
    lines: List[Dict[str, Any]],
    requested_by_id: Optional[UUID] = None,
) -> Dict[str, Any]:
    """
    Create a purchase order.
    State-changing tool: NEVER executes directly. Creates an approval request.
    """
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, organization_id)
        total_amount = sum(float(l.get("quantity", 0)) * float(l.get("unit_cost", 0)) for l in lines)
        action = await propose_state_changing_action(
            session=session,
            organization_id=organization_id,
            tool_name="create_purchase_order",
            inputs={
                "vendor_id": str(vendor_id),
                "lines": lines,
                "amount": total_amount,
            },
            requested_by_id=requested_by_id,
            description=f"Purchase order to vendor {vendor_id} for ${total_amount:,.2f}",
        )
        return {
            "status": "approval_required",
            "action_id": str(action.id),
            "tool_name": "create_purchase_order",
            "amount": total_amount,
            "message": f"Purchase order for ${total_amount:,.2f} requires human approval."
        }


# ── Accounting Tools ──────────────────────────────────────────

async def tool_list_accounts(organization_id: UUID) -> List[Dict[str, Any]]:
    """List chart of accounts."""
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, organization_id)
        service = AccountingService(session)
        accounts = await service.list_accounts(organization_id)
        return [{"id": str(a.id), "code": a.code, "name": a.name, "type": str(a.account_type.value)} for a in accounts]


async def tool_create_journal_entry(
    organization_id: UUID,
    description: str,
    lines: List[Dict[str, Any]],
    requested_by_id: Optional[UUID] = None,
) -> Dict[str, Any]:
    """
    Create a draft double-entry journal entry.
    State-changing tool: NEVER executes directly. Creates an approval request.
    """
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, organization_id)
        total_debits = sum(float(l.get("debit", 0.0) or 0.0) for l in lines)
        action = await propose_state_changing_action(
            session=session,
            organization_id=organization_id,
            tool_name="create_journal_entry",
            inputs={
                "description": description,
                "lines": lines,
                "amount": total_debits,
            },
            requested_by_id=requested_by_id,
            description=f"Double-entry journal: {description} (Total ${total_debits:,.2f})",
        )
        return {
            "status": "approval_required",
            "action_id": str(action.id),
            "tool_name": "create_journal_entry",
            "amount": total_debits,
            "message": f"Journal entry for ${total_debits:,.2f} requires human approval."
        }
