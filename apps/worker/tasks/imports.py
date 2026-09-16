"""
Celery asynchronous bulk CSV import tasks.
"""

import asyncio
from decimal import Decimal
from uuid import UUID
from typing import Dict, Any, List

from celery import shared_task

from packages.database.core import async_session_scope
from packages.database.tenant_context import set_tenant_context
from packages.erp.services.inventory_service import InventoryService


@shared_task(bind=True, name="tasks.bulk_import_products")
def bulk_import_products(self, organization_id: str, products_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Bulk imports a batch of product records asynchronously."""
    org_uuid = UUID(organization_id)

    async def _run():
        success_count = 0
        errors = []

        async with async_session_scope() as session:
            await set_tenant_context(session, org_uuid)
            service = InventoryService(session)

            for item in products_data:
                try:
                    await service.create_product(
                        organization_id=org_uuid,
                        sku=item["sku"],
                        name=item["name"],
                        unit_price=Decimal(str(item.get("unit_price", 0))),
                        cost_price=Decimal(str(item.get("cost_price", 0))),
                        unit_of_measure=item.get("unit_of_measure", "unit"),
                        description=item.get("description"),
                        category=item.get("category"),
                    )
                    success_count += 1
                except Exception as e:
                    errors.append({"sku": item.get("sku"), "error": str(e)})

        return {
            "total": len(products_data),
            "imported": success_count,
            "failed": len(errors),
            "errors": errors,
        }

    return asyncio.run(_run())
