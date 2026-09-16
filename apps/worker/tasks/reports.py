"""
Celery asynchronous report generation tasks.
"""

import asyncio
from uuid import UUID
from datetime import datetime, timezone
from typing import Dict, Any

from celery import shared_task

from packages.database.core import async_session_scope
from packages.database.tenant_context import set_tenant_context
from packages.erp.services.inventory_service import InventoryService
from packages.erp.services.sales_service import SalesService


@shared_task(bind=True, name="tasks.generate_inventory_report")
def generate_inventory_report(self, organization_id: str) -> Dict[str, Any]:
    """Generates an inventory valuation & stock summary report."""
    org_uuid = UUID(organization_id)

    async def _run():
        async with async_session_scope() as session:
            await set_tenant_context(session, org_uuid)
            inv_service = InventoryService(session)
            products = await inv_service.list_products(org_uuid, page=1, page_size=1000)
            levels = await inv_service.list_stock_levels(org_uuid)

            product_map = {p.id: p for p in products}
            total_valuation = 0.0
            stock_summary = []

            for lvl in levels:
                prod = product_map.get(lvl.product_id)
                if prod:
                    val = float(lvl.quantity_on_hand) * float(prod.cost_price)
                    total_valuation += val
                    stock_summary.append({
                        "sku": prod.sku,
                        "name": prod.name,
                        "quantity": float(lvl.quantity_on_hand),
                        "unit_cost": float(prod.cost_price),
                        "valuation": val,
                    })

            return {
                "organization_id": organization_id,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "total_products": len(products),
                "total_valuation_usd": total_valuation,
                "items": stock_summary,
            }

    return asyncio.run(_run())


@shared_task(bind=True, name="tasks.generate_sales_report")
def generate_sales_report(self, organization_id: str) -> Dict[str, Any]:
    """Generates a revenue and sales order summary report."""
    org_uuid = UUID(organization_id)

    async def _run():
        async with async_session_scope() as session:
            await set_tenant_context(session, org_uuid)
            sales_service = SalesService(session)
            invoices = await sales_service.list_invoices(org_uuid, page=1, page_size=1000)

            total_billed = sum(float(i.total_amount) for i in invoices)
            return {
                "organization_id": organization_id,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "invoice_count": len(invoices),
                "total_billed_usd": total_billed,
            }

    return asyncio.run(_run())
