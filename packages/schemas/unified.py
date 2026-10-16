from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

class UnifiedBaseModel(BaseModel):
    """
    Base model for all Unified records.
    Ensures that provenance and multi-tenant boundaries are never lost.
    """
    id: str = Field(..., description="The internal canonical ID")
    organization_id: str = Field(..., description="Tenant isolation boundary")
    source_system: str = Field(..., description="e.g., 'sap', 'salesforce', 'custom'")
    source_connector_id: str = Field(..., description="ID of the connection config")
    source_record_id: str = Field(..., description="Original ID in the source system")
    last_synced_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UnifiedCustomer(UnifiedBaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    billing_address: Optional[Dict[str, Any]] = None

class UnifiedProduct(UnifiedBaseModel):
    sku: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    unit_price: float
    currency: str = "USD"

class UnifiedInventory(UnifiedBaseModel):
    product_sku: str
    quantity_on_hand: int
    reorder_point: Optional[int] = None
    warehouse_location: Optional[str] = None
    reserved_quantity: int = 0

class UnifiedPurchaseOrder(UnifiedBaseModel):
    supplier_id: str
    status: str = Field(..., description="e.g., draft, submitted, approved, fulfilled")
    total_amount: float
    currency: str = "USD"
    items: List[Dict[str, Any]]
    expected_delivery_date: Optional[datetime] = None
