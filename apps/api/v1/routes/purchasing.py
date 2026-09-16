"""
Purchasing REST API routes.
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query

from packages.database.tenant_context import TenantDB
from packages.auth.dependencies import CurrentUser, require_role
from packages.erp.services.purchasing_service import PurchasingService
from packages.database.models.erp.purchasing import POStatus
from packages.schemas.erp import (
    VendorCreate, VendorResponse,
    PurchaseOrderCreate, PurchaseOrderResponse,
    GoodsReceiptCreate, GoodsReceiptResponse,
)

router = APIRouter(prefix="/purchasing", tags=["Purchasing"])


@router.post("/vendors", response_model=VendorResponse, status_code=status.HTTP_201_CREATED)
async def create_vendor(
    body: VendorCreate,
    current_user: CurrentUser,
    db: TenantDB,
    _: None = Depends(require_role("owner", "admin", "manager")),
):
    service = PurchasingService(db)
    return await service.create_vendor(
        organization_id=current_user.org_id,
        name=body.name,
        email=body.email,
        phone=body.phone,
        address=body.address,
        payment_terms=body.payment_terms,
        currency=body.currency,
        tax_id=body.tax_id,
    )


@router.get("/vendors", response_model=List[VendorResponse])
async def list_vendors(
    current_user: CurrentUser,
    db: TenantDB,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    service = PurchasingService(db)
    return await service.list_vendors(current_user.org_id, page=page, page_size=page_size)


@router.post("/orders", response_model=PurchaseOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_purchase_order(
    body: PurchaseOrderCreate,
    current_user: CurrentUser,
    db: TenantDB,
    _: None = Depends(require_role("owner", "admin", "manager")),
):
    service = PurchasingService(db)
    return await service.create_purchase_order(
        organization_id=current_user.org_id,
        vendor_id=body.vendor_id,
        po_number=body.po_number,
        order_date=body.order_date,
        lines=[l.model_dump() for l in body.lines],
        expected_delivery_date=body.expected_delivery_date,
        notes=body.notes,
        currency=body.currency,
    )


@router.post("/orders/{order_id}/receipts", response_model=GoodsReceiptResponse, status_code=status.HTTP_201_CREATED)
async def receive_goods(
    order_id: UUID,
    body: GoodsReceiptCreate,
    current_user: CurrentUser,
    db: TenantDB,
    _: None = Depends(require_role("owner", "admin", "manager")),
):
    service = PurchasingService(db)
    try:
        return await service.receive_goods(
            organization_id=current_user.org_id,
            purchase_order_id=order_id,
            received_date=body.received_date,
            lines=[l.model_dump() for l in body.lines],
            received_by_id=current_user.user_id,
            notes=body.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/orders", response_model=List[PurchaseOrderResponse])
async def list_purchase_orders(
    current_user: CurrentUser,
    db: TenantDB,
    status: Optional[POStatus] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    service = PurchasingService(db)
    return await service.list_purchase_orders(current_user.org_id, status=status, page=page, page_size=page_size)
