"""
Pydantic v2 schemas for ERP domain modules.
"""

from decimal import Decimal
from typing import Optional, List
from uuid import UUID
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field

from packages.database.models.erp.inventory import MovementType
from packages.database.models.erp.sales import OrderStatus, InvoiceStatus
from packages.database.models.erp.purchasing import POStatus
from packages.database.models.erp.accounting import AccountType, EntryStatus
from packages.database.models.erp.hr import LeaveType, LeaveStatus


# ── Inventory Schemas ─────────────────────────────────────────

class ProductCreate(BaseModel):
    sku: str
    name: str
    unit_price: Decimal = Field(ge=0)
    cost_price: Decimal = Field(ge=0)
    unit_of_measure: str = "unit"
    description: Optional[str] = None
    category: Optional[str] = None


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    sku: str
    name: str
    unit_price: Decimal
    cost_price: Decimal
    unit_of_measure: str
    description: Optional[str] = None
    category: Optional[str] = None
    is_active: int


class WarehouseCreate(BaseModel):
    name: str
    code: str
    location: Optional[str] = None


class WarehouseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    name: str
    code: str
    location: Optional[str] = None


class StockAdjustmentRequest(BaseModel):
    product_id: UUID
    warehouse_id: UUID
    delta: Decimal
    movement_type: MovementType
    reference: Optional[str] = None
    notes: Optional[str] = None


class StockLevelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    product_id: UUID
    warehouse_id: UUID
    quantity_on_hand: Decimal
    reorder_point: Optional[Decimal] = None


# ── Sales Schemas ─────────────────────────────────────────────

class CustomerCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    billing_address: Optional[str] = None
    shipping_address: Optional[str] = None
    credit_limit: Optional[Decimal] = None
    currency: str = "USD"


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    currency: str


class SalesOrderLineCreate(BaseModel):
    product_id: UUID
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    description: Optional[str] = None


class SalesOrderLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    product_id: UUID
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal
    description: Optional[str] = None


class SalesOrderCreate(BaseModel):
    customer_id: UUID
    order_number: str
    order_date: date
    expected_delivery_date: Optional[date] = None
    notes: Optional[str] = None
    currency: str = "USD"
    lines: List[SalesOrderLineCreate]


class SalesOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    customer_id: UUID
    order_number: str
    order_date: date
    status: OrderStatus
    currency: str
    lines: List[SalesOrderLineResponse] = []


class InvoiceLineCreate(BaseModel):
    description: str
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)


class InvoiceLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    description: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal


class InvoiceCreate(BaseModel):
    invoice_number: str
    issue_date: date
    due_date: date
    order_id: Optional[UUID] = None
    total_amount: Optional[Decimal] = None
    currency: str = "USD"
    notes: Optional[str] = None
    lines: List[InvoiceLineCreate]


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    invoice_number: str
    issue_date: date
    due_date: date
    status: InvoiceStatus
    total_amount: Decimal
    currency: str
    lines: List[InvoiceLineResponse] = []


class PaymentCreate(BaseModel):
    invoice_id: UUID
    amount: Decimal = Field(gt=0)
    payment_date: date
    method: str
    reference: Optional[str] = None
    notes: Optional[str] = None


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    invoice_id: UUID
    amount: Decimal
    payment_date: date
    method: str
    reference: Optional[str] = None


# ── Purchasing Schemas ────────────────────────────────────────

class VendorCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    payment_terms: Optional[str] = None
    currency: str = "USD"
    tax_id: Optional[str] = None


class VendorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    name: str
    email: Optional[str] = None
    currency: str


class PurchaseOrderLineCreate(BaseModel):
    product_id: UUID
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(ge=0)


class PurchaseOrderLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    product_id: UUID
    quantity: Decimal
    unit_cost: Decimal
    line_total: Decimal


class PurchaseOrderCreate(BaseModel):
    vendor_id: UUID
    po_number: str
    order_date: date
    expected_delivery_date: Optional[date] = None
    notes: Optional[str] = None
    currency: str = "USD"
    lines: List[PurchaseOrderLineCreate]


class PurchaseOrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    vendor_id: UUID
    po_number: str
    order_date: date
    status: POStatus
    currency: str
    lines: List[PurchaseOrderLineResponse] = []


class GoodsReceiptLineCreate(BaseModel):
    po_line_id: UUID
    quantity_received: Decimal = Field(gt=0)
    warehouse_id: UUID


class GoodsReceiptCreate(BaseModel):
    purchase_order_id: UUID
    received_date: date
    notes: Optional[str] = None
    lines: List[GoodsReceiptLineCreate]


class GoodsReceiptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    purchase_order_id: UUID
    received_date: date


# ── Accounting Schemas ────────────────────────────────────────

class AccountCreate(BaseModel):
    code: str
    name: str
    account_type: AccountType
    currency: str = "USD"
    description: Optional[str] = None
    parent_id: Optional[UUID] = None


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    code: str
    name: str
    account_type: AccountType
    currency: str
    is_active: bool


class JournalLineCreate(BaseModel):
    account_id: UUID
    debit: Decimal = Field(default=Decimal("0"), ge=0)
    credit: Decimal = Field(default=Decimal("0"), ge=0)
    description: Optional[str] = None


class JournalLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    account_id: UUID
    debit: Decimal
    credit: Decimal
    description: Optional[str] = None


class JournalEntryCreate(BaseModel):
    entry_date: date
    description: str
    reference: Optional[str] = None
    lines: List[JournalLineCreate]


class JournalEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    entry_date: date
    description: str
    status: EntryStatus
    lines: List[JournalLineResponse] = []


# ── HR Schemas ────────────────────────────────────────────────

class DepartmentCreate(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    manager_id: Optional[UUID] = None


class DepartmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    name: str
    code: str
    description: Optional[str] = None


class EmployeeCreate(BaseModel):
    first_name: str
    last_name: str
    hire_date: date
    department_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    job_title: Optional[str] = None
    employee_number: Optional[str] = None
    salary: Optional[Decimal] = Field(default=None, ge=0)
    salary_currency: str = "USD"


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    first_name: str
    last_name: str
    email: Optional[str] = None
    job_title: Optional[str] = None
    hire_date: date


class AttendanceCreate(BaseModel):
    employee_id: UUID
    record_date: date
    check_in: datetime
    check_out: Optional[datetime] = None
    notes: Optional[str] = None


class AttendanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    employee_id: UUID
    date: date
    check_in: datetime
    check_out: Optional[datetime] = None
    hours_worked: Optional[Decimal] = None


class LeaveRequestCreate(BaseModel):
    employee_id: UUID
    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: Optional[str] = None


class LeaveRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    employee_id: UUID
    leave_type: LeaveType
    start_date: date
    end_date: date
    status: LeaveStatus
