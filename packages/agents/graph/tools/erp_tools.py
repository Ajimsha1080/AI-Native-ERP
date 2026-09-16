"""
Typed agent tools calling the service layer directly.
No raw SQL execution from agents.
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
) -> Dict[str, Any]:
    """Adjust product stock quantity (requires approval for large quantities)."""
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, organization_id)
        service = InventoryService(session)
        level = await service.adjust_stock(
            organization_id=organization_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            delta=Decimal(str(delta)),
            movement_type=MovementType.ADJUSTMENT,
            notes=reason,
        )
        return {"status": "success", "new_quantity": float(level.quantity_on_hand)}


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


# ── Purchasing Tools ──────────────────────────────────────────

async def tool_list_vendors(organization_id: UUID) -> List[Dict[str, Any]]:
    """List approved vendors."""
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, organization_id)
        service = PurchasingService(session)
        vendors = await service.list_vendors(organization_id)
        return [{"id": str(v.id), "name": v.name, "email": v.email} for v in vendors]


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
) -> Dict[str, Any]:
    """Create a draft double-entry journal entry."""
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, organization_id)
        service = AccountingService(session)
        entry = await service.create_journal_entry(
            organization_id=organization_id,
            entry_date=date.today(),
            description=description,
            lines=lines,
        )
        return {"status": "success", "journal_entry_id": str(entry.id), "entry_status": str(entry.status.value)}
