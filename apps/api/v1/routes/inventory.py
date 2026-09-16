"""
Inventory REST API routes.
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query

from packages.database.tenant_context import TenantDB
from packages.auth.dependencies import CurrentUser, require_role, require_min_role
from packages.erp.services.inventory_service import InventoryService
from packages.erp.repositories.inventory_repo import InsufficientStockError
from packages.schemas.erp import (
    ProductCreate, ProductResponse,
    WarehouseCreate, WarehouseResponse,
    StockAdjustmentRequest, StockLevelResponse
)

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    body: ProductCreate,
    current_user: CurrentUser,
    db: TenantDB,
    _: None = Depends(require_role("owner", "admin", "manager")),
):
    service = InventoryService(db)
    product = await service.create_product(
        organization_id=current_user.org_id,
        sku=body.sku,
        name=body.name,
        unit_price=body.unit_price,
        cost_price=body.cost_price,
        unit_of_measure=body.unit_of_measure,
        description=body.description,
        category=body.category,
    )
    return product


@router.get("/products", response_model=List[ProductResponse])
async def list_products(
    current_user: CurrentUser,
    db: TenantDB,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    service = InventoryService(db)
    return await service.list_products(current_user.org_id, page=page, page_size=page_size)


@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: UUID,
    current_user: CurrentUser,
    db: TenantDB,
):
    service = InventoryService(db)
    product = await service.get_product(product_id)
    if not product or product.organization_id != current_user.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@router.post("/warehouses", response_model=WarehouseResponse, status_code=status.HTTP_201_CREATED)
async def create_warehouse(
    body: WarehouseCreate,
    current_user: CurrentUser,
    db: TenantDB,
    _: None = Depends(require_role("owner", "admin", "manager")),
):
    service = InventoryService(db)
    return await service.create_warehouse(
        organization_id=current_user.org_id,
        name=body.name,
        code=body.code,
        location=body.location,
    )


@router.get("/warehouses", response_model=List[WarehouseResponse])
async def list_warehouses(
    current_user: CurrentUser,
    db: TenantDB,
):
    service = InventoryService(db)
    return await service.list_warehouses(current_user.org_id)


@router.post("/stock/adjust", response_model=StockLevelResponse)
async def adjust_stock(
    body: StockAdjustmentRequest,
    current_user: CurrentUser,
    db: TenantDB,
    _: None = Depends(require_role("owner", "admin", "manager")),
):
    service = InventoryService(db)
    try:
        level = await service.adjust_stock(
            organization_id=current_user.org_id,
            product_id=body.product_id,
            warehouse_id=body.warehouse_id,
            delta=body.delta,
            movement_type=body.movement_type,
            reference=body.reference,
            notes=body.notes,
            created_by_id=current_user.user_id,
        )
        return level
    except InsufficientStockError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/stock/levels", response_model=List[StockLevelResponse])
async def list_stock_levels(
    current_user: CurrentUser,
    db: TenantDB,
    warehouse_id: Optional[UUID] = None,
):
    service = InventoryService(db)
    return await service.list_stock_levels(current_user.org_id, warehouse_id=warehouse_id)
