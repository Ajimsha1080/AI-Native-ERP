"""
Sales REST API routes.
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query

from packages.database.tenant_context import TenantDB
from packages.auth.dependencies import CurrentUser, require_role
from packages.erp.services.sales_service import SalesService
from packages.erp.repositories.sales_repo import InvoiceMismatchError
from packages.database.models.erp.sales import OrderStatus, InvoiceStatus
from packages.schemas.erp import (
    CustomerCreate, CustomerResponse,
    SalesOrderCreate, SalesOrderResponse,
    InvoiceCreate, InvoiceResponse,
    PaymentCreate, PaymentResponse,
)

router = APIRouter(prefix="/sales", tags=["Sales"])


@router.post("/customers", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    body: CustomerCreate,
    current_user: CurrentUser,
    db: TenantDB,
    _: None = Depends(require_role("owner", "admin", "manager")),
):
    service = SalesService(db)
    return await service.create_customer(
        organization_id=current_user.org_id,
        name=body.name,
        email=body.email,
        phone=body.phone,
        billing_address=body.billing_address,
        shipping_address=body.shipping_address,
        credit_limit=body.credit_limit,
        currency=body.currency,
    )


@router.get("/customers", response_model=List[CustomerResponse])
async def list_customers(
    current_user: CurrentUser,
    db: TenantDB,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    service = SalesService(db)
    return await service.list_customers(current_user.org_id, page=page, page_size=page_size)


@router.post("/orders", response_model=SalesOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_sales_order(
    body: SalesOrderCreate,
    current_user: CurrentUser,
    db: TenantDB,
    _: None = Depends(require_role("owner", "admin", "manager")),
):
    service = SalesService(db)
    return await service.create_sales_order(
        organization_id=current_user.org_id,
        customer_id=body.customer_id,
        order_number=body.order_number,
        order_date=body.order_date,
        lines=[l.model_dump() for l in body.lines],
        expected_delivery_date=body.expected_delivery_date,
        notes=body.notes,
        currency=body.currency,
    )


@router.post("/orders/{order_id}/confirm", response_model=SalesOrderResponse)
async def confirm_sales_order(
    order_id: UUID,
    current_user: CurrentUser,
    db: TenantDB,
    _: None = Depends(require_role("owner", "admin", "manager")),
):
    service = SalesService(db)
    try:
        return await service.confirm_sales_order(order_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/orders", response_model=List[SalesOrderResponse])
async def list_sales_orders(
    current_user: CurrentUser,
    db: TenantDB,
    status: Optional[OrderStatus] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    service = SalesService(db)
    return await service.list_sales_orders(current_user.org_id, status=status, page=page, page_size=page_size)


@router.post("/invoices", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    body: InvoiceCreate,
    current_user: CurrentUser,
    db: TenantDB,
    _: None = Depends(require_role("owner", "admin", "manager")),
):
    service = SalesService(db)
    try:
        return await service.create_invoice(
            organization_id=current_user.org_id,
            invoice_number=body.invoice_number,
            issue_date=body.issue_date,
            due_date=body.due_date,
            lines=[l.model_dump() for l in body.lines],
            order_id=body.order_id,
            total_amount=body.total_amount,
            currency=body.currency,
            notes=body.notes,
        )
    except InvoiceMismatchError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.get("/invoices", response_model=List[InvoiceResponse])
async def list_invoices(
    current_user: CurrentUser,
    db: TenantDB,
    status: Optional[InvoiceStatus] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    service = SalesService(db)
    return await service.list_invoices(current_user.org_id, status=status, page=page, page_size=page_size)


@router.post("/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def record_payment(
    body: PaymentCreate,
    current_user: CurrentUser,
    db: TenantDB,
    _: None = Depends(require_role("owner", "admin", "manager")),
):
    service = SalesService(db)
    try:
        return await service.record_payment(
            organization_id=current_user.org_id,
            invoice_id=body.invoice_id,
            amount=body.amount,
            payment_date=body.payment_date,
            method=body.method,
            reference=body.reference,
            notes=body.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
