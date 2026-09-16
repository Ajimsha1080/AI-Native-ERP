"""
ERP business module tables — initial migration.

Creates: products, warehouses, stock_levels, stock_movements,
         customers, sales_orders, sales_order_lines, invoices,
         invoice_lines, payments, vendors, purchase_orders,
         purchase_order_lines, goods_receipts, goods_receipt_lines,
         accounts, journal_entries, journal_lines,
         departments, employees, attendance_records, leave_requests

Revision ID: 0001_erp_modules
Revises: (initial — no prior revision)
Create Date: 2026-09-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = "0001_erp_modules"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================================
    # INVENTORY
    # =========================================================
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, default=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sku", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("unit_of_measure", sa.String(50), nullable=False, server_default="unit"),
        sa.Column("unit_price", sa.Numeric(15, 4), nullable=False, server_default="0"),
        sa.Column("cost_price", sa.Numeric(15, 4), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("organization_id", "sku", name="uix_product_org_sku"),
        sa.CheckConstraint("unit_price >= 0", name="chk_product_unit_price"),
        sa.CheckConstraint("cost_price >= 0", name="chk_product_cost_price"),
    )
    op.create_index("ix_product_organization", "products", ["organization_id"])
    op.create_index("ix_product_sku", "products", ["sku"])

    op.create_table(
        "warehouses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, default=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("organization_id", "code", name="uix_warehouse_org_code"),
    )
    op.create_index("ix_warehouse_organization", "warehouses", ["organization_id"])

    op.create_table(
        "stock_levels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quantity_on_hand", sa.Numeric(15, 4), nullable=False, server_default="0"),
        sa.Column("reorder_point", sa.Numeric(15, 4), nullable=True),
        sa.Column("max_stock", sa.Numeric(15, 4), nullable=True),
        sa.UniqueConstraint("product_id", "warehouse_id", name="uix_stock_level_product_warehouse"),
        sa.CheckConstraint("quantity_on_hand >= 0", name="chk_stock_level_non_negative"),
    )
    op.create_index("ix_stock_level_organization", "stock_levels", ["organization_id"])
    op.create_index("ix_stock_level_product", "stock_levels", ["product_id"])
    op.create_index("ix_stock_level_warehouse", "stock_levels", ["warehouse_id"])

    op.create_table(
        "stock_movements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("movement_type", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Numeric(15, 4), nullable=False),
        sa.Column("reference", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint("quantity != 0", name="chk_stock_movement_nonzero"),
    )
    op.create_index("ix_stock_movement_organization", "stock_movements", ["organization_id"])
    op.create_index("ix_stock_movement_product", "stock_movements", ["product_id"])

    # =========================================================
    # SALES
    # =========================================================
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, default=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("billing_address", sa.Text(), nullable=True),
        sa.Column("shipping_address", sa.Text(), nullable=True),
        sa.Column("credit_limit", sa.Numeric(15, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
    )
    op.create_index("ix_customer_organization", "customers", ["organization_id"])

    op.create_table(
        "sales_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, default=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("order_number", sa.String(50), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("expected_delivery_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
    )
    op.create_index("ix_sales_order_organization", "sales_orders", ["organization_id"])
    op.create_index("ix_sales_order_status", "sales_orders", ["status"])

    op.create_table(
        "sales_order_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("sales_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Numeric(15, 4), nullable=False),
        sa.Column("unit_price", sa.Numeric(15, 4), nullable=False),
        sa.Column("line_total", sa.Numeric(15, 4), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.CheckConstraint("quantity > 0", name="chk_sol_quantity_positive"),
        sa.CheckConstraint("line_total >= 0", name="chk_sol_line_total"),
    )
    op.create_index("ix_sales_order_line_order", "sales_order_lines", ["order_id"])

    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, default=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("sales_orders.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("invoice_number", sa.String(50), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("total_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint("total_amount >= 0", name="chk_invoice_total_non_negative"),
    )
    op.create_index("ix_invoice_organization", "invoices", ["organization_id"])
    op.create_index("ix_invoice_status", "invoices", ["status"])

    op.create_table(
        "invoice_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(15, 4), nullable=False),
        sa.Column("unit_price", sa.Numeric(15, 4), nullable=False),
        sa.Column("line_total", sa.Numeric(15, 4), nullable=False),
        sa.CheckConstraint("quantity > 0", name="chk_invoice_line_quantity_positive"),
        sa.CheckConstraint("line_total >= 0", name="chk_invoice_line_total"),
    )
    op.create_index("ix_invoice_line_invoice", "invoice_lines", ["invoice_id"])

    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("method", sa.String(50), nullable=False),
        sa.Column("reference", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint("amount > 0", name="chk_payment_amount_positive"),
    )
    op.create_index("ix_payment_organization", "payments", ["organization_id"])
    op.create_index("ix_payment_invoice", "payments", ["invoice_id"])

    # =========================================================
    # PURCHASING
    # =========================================================
    op.create_table(
        "vendors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, default=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("payment_terms", sa.String(100), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("tax_id", sa.String(100), nullable=True),
    )
    op.create_index("ix_vendor_organization", "vendors", ["organization_id"])

    op.create_table(
        "purchase_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, default=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("vendors.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("po_number", sa.String(50), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("expected_delivery_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
    )
    op.create_index("ix_po_organization", "purchase_orders", ["organization_id"])
    op.create_index("ix_po_status", "purchase_orders", ["status"])

    op.create_table(
        "purchase_order_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Numeric(15, 4), nullable=False),
        sa.Column("unit_cost", sa.Numeric(15, 4), nullable=False),
        sa.Column("line_total", sa.Numeric(15, 4), nullable=False),
        sa.CheckConstraint("quantity > 0", name="chk_pol_quantity_positive"),
        sa.CheckConstraint("line_total >= 0", name="chk_pol_line_total"),
    )
    op.create_index("ix_pol_order", "purchase_order_lines", ["order_id"])

    op.create_table(
        "goods_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purchase_order_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("purchase_orders.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("received_date", sa.Date(), nullable=False),
        sa.Column("received_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_gr_organization", "goods_receipts", ["organization_id"])
    op.create_index("ix_gr_po", "goods_receipts", ["purchase_order_id"])

    op.create_table(
        "goods_receipt_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("receipt_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("goods_receipts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("po_line_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("purchase_order_lines.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity_received", sa.Numeric(15, 4), nullable=False),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False),
        sa.CheckConstraint("quantity_received > 0", name="chk_grl_quantity_positive"),
    )
    op.create_index("ix_grl_receipt", "goods_receipt_lines", ["receipt_id"])

    # =========================================================
    # ACCOUNTING
    # =========================================================
    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, default=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("account_type", sa.String(20), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("organization_id", "code", name="uix_account_org_code"),
    )
    op.create_index("ix_account_organization", "accounts", ["organization_id"])
    op.create_index("ix_account_type", "accounts", ["account_type"])

    op.create_table(
        "journal_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("reference", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_journal_entry_organization", "journal_entries", ["organization_id"])
    op.create_index("ix_journal_entry_date", "journal_entries", ["entry_date"])
    op.create_index("ix_journal_entry_status", "journal_entries", ["status"])

    op.create_table(
        "journal_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entry_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("debit", sa.Numeric(15, 4), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(15, 4), nullable=False, server_default="0"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.CheckConstraint("debit >= 0", name="chk_jl_debit_non_negative"),
        sa.CheckConstraint("credit >= 0", name="chk_jl_credit_non_negative"),
        sa.CheckConstraint(
            "(debit = 0 AND credit > 0) OR (debit > 0 AND credit = 0)",
            name="chk_jl_single_side",
        ),
    )
    op.create_index("ix_journal_line_entry", "journal_lines", ["entry_id"])
    op.create_index("ix_journal_line_account", "journal_lines", ["account_id"])

    # =========================================================
    # HR
    # =========================================================
    op.create_table(
        "departments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, default=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("manager_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_department_organization", "departments", ["organization_id"])

    op.create_table(
        "employees",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, default=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("job_title", sa.String(255), nullable=True),
        sa.Column("employee_number", sa.String(50), nullable=True),
        sa.Column("hire_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("salary", sa.Numeric(15, 2), nullable=True),
        sa.Column("salary_currency", sa.String(3), nullable=False, server_default="USD"),
        sa.CheckConstraint("salary IS NULL OR salary >= 0", name="chk_employee_salary"),
    )
    op.create_index("ix_employee_organization", "employees", ["organization_id"])
    op.create_index("ix_employee_department", "employees", ["department_id"])

    # Add FK from departments.manager_id → employees.id (deferred to avoid circular)
    op.create_foreign_key(
        "fk_department_manager",
        "departments", "employees",
        ["manager_id"], ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "attendance_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("check_in", sa.DateTime(timezone=True), nullable=False),
        sa.Column("check_out", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hours_worked", sa.Numeric(5, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "check_out IS NULL OR check_out > check_in",
            name="chk_attendance_checkout_after_checkin",
        ),
        sa.CheckConstraint(
            "hours_worked IS NULL OR hours_worked >= 0",
            name="chk_attendance_hours_non_negative",
        ),
    )
    op.create_index("ix_attendance_organization", "attendance_records", ["organization_id"])
    op.create_index("ix_attendance_employee", "attendance_records", ["employee_id"])
    op.create_index("ix_attendance_date", "attendance_records", ["date"])

    op.create_table(
        "leave_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("leave_type", sa.String(20), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("approved_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.CheckConstraint("end_date >= start_date", name="chk_leave_end_after_start"),
    )
    op.create_index("ix_leave_organization", "leave_requests", ["organization_id"])
    op.create_index("ix_leave_employee", "leave_requests", ["employee_id"])
    op.create_index("ix_leave_status", "leave_requests", ["status"])


def downgrade() -> None:
    """Drop all ERP tables in reverse dependency order."""
    op.drop_table("leave_requests")
    op.drop_table("attendance_records")
    op.drop_constraint("fk_department_manager", "departments", type_="foreignkey")
    op.drop_table("employees")
    op.drop_table("departments")
    op.drop_table("journal_lines")
    op.drop_table("journal_entries")
    op.drop_table("accounts")
    op.drop_table("goods_receipt_lines")
    op.drop_table("goods_receipts")
    op.drop_table("purchase_order_lines")
    op.drop_table("purchase_orders")
    op.drop_table("vendors")
    op.drop_table("payments")
    op.drop_table("invoice_lines")
    op.drop_table("invoices")
    op.drop_table("sales_order_lines")
    op.drop_table("sales_orders")
    op.drop_table("customers")
    op.drop_table("stock_movements")
    op.drop_table("stock_levels")
    op.drop_table("warehouses")
    op.drop_table("products")
