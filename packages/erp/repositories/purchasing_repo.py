"""
Purchasing repository.

Handles data access for Vendors, PurchaseOrders, PurchaseOrderLines, GoodsReceipts, GoodsReceiptLines.
"""

from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.models.erp.purchasing import (
    Vendor, PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine, POStatus
)


class PurchasingRepository:

    def __init__(self, session: AsyncSession):
        self._session = session

    # ── Vendors ───────────────────────────────────────────────

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
        vendor = Vendor(
            organization_id=organization_id,
            name=name,
            email=email,
            phone=phone,
            address=address,
            payment_terms=payment_terms,
            currency=currency,
            tax_id=tax_id,
        )
        self._session.add(vendor)
        await self._session.flush()
        return vendor

    async def get_vendor(self, vendor_id: UUID) -> Optional[Vendor]:
        result = await self._session.execute(
            select(Vendor).where(Vendor.id == vendor_id, Vendor.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def list_vendors(
        self, organization_id: UUID, page: int = 1, page_size: int = 20
    ) -> List[Vendor]:
        offset = (page - 1) * page_size
        result = await self._session.execute(
            select(Vendor)
            .where(Vendor.organization_id == organization_id, Vendor.is_deleted == False)
            .offset(offset)
            .limit(page_size)
            .order_by(Vendor.name)
        )
        return list(result.scalars().all())

    # ── Purchase Orders ───────────────────────────────────────

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
        po = PurchaseOrder(
            organization_id=organization_id,
            vendor_id=vendor_id,
            po_number=po_number,
            order_date=order_date,
            expected_delivery_date=expected_delivery_date,
            status=POStatus.DRAFT,
            notes=notes,
            currency=currency,
        )
        self._session.add(po)
        await self._session.flush()

        for l in lines:
            qty = Decimal(str(l["quantity"]))
            unit_cost = Decimal(str(l["unit_cost"]))
            line_total = qty * unit_cost
            po_line = PurchaseOrderLine(
                organization_id=organization_id,
                order_id=po.id,
                product_id=l["product_id"],
                quantity=qty,
                unit_cost=unit_cost,
                line_total=line_total,
            )
            self._session.add(po_line)

        await self._session.flush()
        return po

    async def get_purchase_order(self, po_id: UUID) -> Optional[PurchaseOrder]:
        result = await self._session.execute(
            select(PurchaseOrder)
            .options(selectinload(PurchaseOrder.lines), selectinload(PurchaseOrder.receipts))
            .where(PurchaseOrder.id == po_id, PurchaseOrder.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def list_purchase_orders(
        self, organization_id: UUID, status: Optional[POStatus] = None, page: int = 1, page_size: int = 20
    ) -> List[PurchaseOrder]:
        offset = (page - 1) * page_size
        q = select(PurchaseOrder).where(PurchaseOrder.organization_id == organization_id, PurchaseOrder.is_deleted == False)
        if status:
            q = q.where(PurchaseOrder.status == status)
        q = q.offset(offset).limit(page_size).order_by(PurchaseOrder.order_date.desc())
        result = await self._session.execute(q)
        return list(result.scalars().all())

    # ── Goods Receipts ────────────────────────────────────────

    async def create_goods_receipt(
        self,
        organization_id: UUID,
        purchase_order_id: UUID,
        received_date: date,
        lines: List[Dict[str, Any]],
        received_by_id: Optional[UUID] = None,
        notes: Optional[str] = None,
    ) -> GoodsReceipt:
        receipt = GoodsReceipt(
            organization_id=organization_id,
            purchase_order_id=purchase_order_id,
            received_date=received_date,
            received_by_id=received_by_id,
            notes=notes,
        )
        self._session.add(receipt)
        await self._session.flush()

        for l in lines:
            receipt_line = GoodsReceiptLine(
                organization_id=organization_id,
                receipt_id=receipt.id,
                po_line_id=l["po_line_id"],
                quantity_received=Decimal(str(l["quantity_received"])),
                warehouse_id=l["warehouse_id"],
            )
            self._session.add(receipt_line)

        await self._session.flush()
        return receipt
