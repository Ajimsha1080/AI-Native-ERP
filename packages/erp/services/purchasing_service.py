"""
Purchasing Service.

Enforces business logic for vendors, PO lifecycle, and goods receipt which creates inventory stock movements automatically.
"""

from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.models.erp.purchasing import (
    Vendor, PurchaseOrder, GoodsReceipt, POStatus
)
from packages.database.models.erp.inventory import MovementType
from packages.erp.repositories.purchasing_repo import PurchasingRepository
from packages.erp.repositories.inventory_repo import InventoryRepository


class PurchasingService:

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PurchasingRepository(session)
        self.inventory_repo = InventoryRepository(session)

    async def create_vendor(
        self,
        organization_id: UUID,
        name: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        address: Optional[str] = None,
        payment_terms: Optional[str] = None,
        currency: str = "USD",
        tax_id: Optional[str] = None,
    ) -> Vendor:
        vendor = await self.repo.create_vendor(
            organization_id=organization_id,
            name=name,
            email=email,
            phone=phone,
            address=address,
            payment_terms=payment_terms,
            currency=currency,
            tax_id=tax_id,
        )
        await self.session.commit()
        return vendor

    async def list_vendors(
        self, organization_id: UUID, page: int = 1, page_size: int = 20
    ) -> List[Vendor]:
        return await self.repo.list_vendors(organization_id, page=page, page_size=page_size)

    async def create_purchase_order(
        self,
        organization_id: UUID,
        vendor_id: UUID,
        po_number: str,
        order_date: date,
        lines: List[Dict[str, Any]],
        expected_delivery_date: Optional[date] = None,
        notes: Optional[str] = None,
        currency: str = "USD",
    ) -> PurchaseOrder:
        po = await self.repo.create_purchase_order(
            organization_id=organization_id,
            vendor_id=vendor_id,
            po_number=po_number,
            order_date=order_date,
            lines=lines,
            expected_delivery_date=expected_delivery_date,
            notes=notes,
            currency=currency,
        )
        await self.session.commit()
        return po

    async def receive_goods(
        self,
        organization_id: UUID,
        purchase_order_id: UUID,
        received_date: date,
        lines: List[Dict[str, Any]],
        received_by_id: Optional[UUID] = None,
        notes: Optional[str] = None,
    ) -> GoodsReceipt:
        """
        Records goods receipt AND updates inventory levels via stock movements.
        """
        po = await self.repo.get_purchase_order(purchase_order_id)
        if not po:
            raise ValueError(f"Purchase order {purchase_order_id} not found")

        receipt = await self.repo.create_goods_receipt(
            organization_id=organization_id,
            purchase_order_id=purchase_order_id,
            received_date=received_date,
            lines=lines,
            received_by_id=received_by_id,
            notes=notes,
        )

        # Map po_line_id to product_id
        po_lines_map = {line.id: line.product_id for line in po.lines}

        for l in lines:
            po_line_id = l["po_line_id"]
            product_id = po_lines_map.get(po_line_id)
            if product_id:
                qty = Decimal(str(l["quantity_received"]))
                warehouse_id = l["warehouse_id"]
                await self.inventory_repo.adjust_stock(
                    organization_id=organization_id,
                    product_id=product_id,
                    warehouse_id=warehouse_id,
                    delta=qty,
                    movement_type=MovementType.RECEIPT,
                    reference=f"GR-{receipt.id}",
                    notes=f"Goods received for PO {po.po_number}",
                    created_by_id=received_by_id,
                )

        po.status = POStatus.RECEIVED
        await self.session.commit()
        return receipt

    async def list_purchase_orders(
        self, organization_id: UUID, status: Optional[POStatus] = None, page: int = 1, page_size: int = 20
    ) -> List[PurchaseOrder]:
        return await self.repo.list_purchase_orders(organization_id, status=status, page=page, page_size=page_size)
