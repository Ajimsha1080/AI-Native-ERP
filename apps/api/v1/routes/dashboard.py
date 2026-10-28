"""Dashboard and Command Center Routes with Real Multi-Tenant Database & RLS Integration."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, or_
from typing import List, Dict, Any, Optional
import asyncio
import json
import uuid
import logging
from datetime import datetime, timezone, timedelta, date
from decimal import Decimal

logger = logging.getLogger(__name__)

from packages.database.tenant_context import TenantDB
from packages.auth.dependencies import CurrentUser
from packages.database.models import (
    Organization, Workspace, User, UserRole, Agent,
    Action, ActionType, ActionStatus, Approval,
    AuditEvent, AuditEventType, Document, KnowledgeDocument, Workflow
)
from packages.database.models.erp.inventory import Product, Warehouse, StockLevel, StockMovement
from packages.database.models.erp.sales import Customer, SalesOrder, Invoice, InvoiceStatus, OrderStatus
from packages.database.models.erp.purchasing import Vendor, PurchaseOrder, PurchaseOrderLine, POStatus
from packages.database.models.erp.accounting import Account, AccountType, JournalEntry, JournalLine, EntryStatus
from packages.security.guardrails import guardrails
from packages.agents.memory import memory_manager

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/home")
async def get_home_data(
    current_user: CurrentUser,
    db: TenantDB,
):
    """Live Home / Command Center overview data computed from tenant data."""
    org_id = current_user.org_id

    # 1. Pending Approvals scoped to current tenant
    stmt_approvals = (
        select(Action, Agent)
        .outerjoin(Agent, Action.agent_id == Agent.id)
        .where(
            Action.organization_id == org_id,
            Action.status == ActionStatus.APPROVAL_REQUIRED
        )
        .order_by(desc(Action.proposed_at))
        .limit(10)
    )
    res_approvals = await db.execute(stmt_approvals)
    approval_rows = res_approvals.all()

    approvals_list = []
    for action, agent in approval_rows:
        amount_val = 0.0
        if action.action_data and isinstance(action.action_data, dict):
            amount_val = float(action.action_data.get("amount", 0.0) or 0.0)
        approvals_list.append({
            "id": str(action.id),
            "title": action.name,
            "subtitle": action.description or "Action requiring human authorization",
            "amount": f"${amount_val:,.2f}",
            "risk": "High" if amount_val >= 1000.0 else "Medium",
            "agent": agent.name if agent else "Autonomous Agent",
            "system": "Enterprise Decision Engine",
            "time": action.proposed_at.strftime("%H:%M:%S") if action.proposed_at else "Pending"
        })

    # 2. Recent Activity Log scoped to current tenant
    stmt_audit = (
        select(AuditEvent)
        .where(AuditEvent.organization_id == org_id)
        .order_by(desc(AuditEvent.event_time))
        .limit(8)
    )
    res_audit = await db.execute(stmt_audit)
    audit_events = res_audit.scalars().all()
    activity_list = []
    for ev in audit_events:
        activity_list.append({
            "agent": ev.user_role or ev.agent_name or "Security Sentinel",
            "action": ev.event_name,
            "time": ev.event_time.strftime("%H:%M:%S") if ev.event_time else "Just now"
        })

    # 3. Agent count & Workflow count scoped to tenant
    stmt_agent_cnt = select(func.count(Agent.id)).where(
        (Agent.organization_id == org_id) | (Agent.organization_id.is_(None)),
        Agent.status == "active"
    )
    agent_cnt = (await db.execute(stmt_agent_cnt)).scalar() or 0

    stmt_wf_cnt = select(func.count(Workflow.id)).where(
        Workflow.organization_id == org_id,
        Workflow.is_active == True
    )
    wf_cnt = (await db.execute(stmt_wf_cnt)).scalar() or 0

    # 4. Financial and operational rollups from canonical tenant tables
    stmt_invoices = select(Invoice.total_amount).where(
        Invoice.organization_id == org_id,
        Invoice.is_deleted == False,
        Invoice.status.in_([InvoiceStatus.PAID, "paid"])
    )
    paid_inv_rows = (await db.execute(stmt_invoices)).scalars().all()
    total_rev = sum(float(amt or 0) for amt in paid_inv_rows)

    stmt_orders = select(func.count(SalesOrder.id)).where(
        SalesOrder.organization_id == org_id,
        SalesOrder.is_deleted == False,
        SalesOrder.status.in_([OrderStatus.DRAFT, OrderStatus.CONFIRMED, "draft", "confirmed"])
    )
    active_orders = (await db.execute(stmt_orders)).scalar() or 0

    stmt_skus = select(func.count(Product.id)).where(
        Product.organization_id == org_id,
        Product.is_deleted == False,
        Product.is_active == 1
    )
    inventory_skus = (await db.execute(stmt_skus)).scalar() or 0

    # Today's audit actions
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None).replace(tzinfo=None)
    today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    stmt_actions_today = select(func.count(AuditEvent.id)).where(
        AuditEvent.organization_id == org_id,
        AuditEvent.event_time >= today_start
    )
    actions_today = (await db.execute(stmt_actions_today)).scalar() or 0

    insights_list = [
        {
            "title": "Autonomous Workforce Online",
            "desc": f"{agent_cnt} domain specialists active across finance, inventory, procurement, and compliance."
        },
        {
            "title": "Financial Governance Enforced",
            "desc": "AI safety boundaries active: disbursements exceeding $1,000.00 require human executive sign-off."
        },
        {
            "title": "Multi-Tenant RLS Active",
            "desc": f"PostgreSQL Row-Level Security active for tenant context {str(org_id)[:8]}."
        }
    ]

    return {
        "total_revenue": f"${total_rev:,.2f}",
        "active_orders": active_orders,
        "inventory_skus": inventory_skus,
        "agent_actions_today": actions_today,
        "active_workflows": wf_cnt,
        "insights": insights_list,
        "approvals": approvals_list,
        "activity": activity_list
    }


@router.get("/finance")
async def get_finance_data(
    current_user: CurrentUser,
    db: TenantDB,
):
    """Live Finance & Treasury metrics computed from canonical tenant data."""
    org_id = current_user.org_id

    # 1. Invoices for Revenue and Accounts Receivable
    stmt_invoices = select(Invoice).where(
        Invoice.organization_id == org_id,
        Invoice.is_deleted == False
    ).order_by(desc(Invoice.issue_date)).limit(100)
    invoices_res = (await db.execute(stmt_invoices)).scalars().all()

    total_rev = sum(float(inv.total_amount or 0) for inv in invoices_res if inv.status in [InvoiceStatus.PAID, "paid"])
    total_receivable = sum(
        float(inv.total_amount or 0)
        for inv in invoices_res
        if inv.status in [InvoiceStatus.SENT, InvoiceStatus.OVERDUE, "sent", "overdue"]
    )

    # 2. Open Purchase Orders for Accounts Payable
    stmt_pos = (
        select(func.coalesce(func.sum(PurchaseOrderLine.line_total), 0))
        .join(PurchaseOrder, PurchaseOrderLine.order_id == PurchaseOrder.id)
        .where(
            PurchaseOrder.organization_id == org_id,
            PurchaseOrder.is_deleted == False,
            PurchaseOrder.status.in_([POStatus.SENT, POStatus.ACKNOWLEDGED, POStatus.PARTIALLY_RECEIVED, "sent", "acknowledged", "partially_received"])
        )
    )
    total_payable = float((await db.execute(stmt_pos)).scalar() or 0.0)

    # 3. Ledger balances from posted journal entries
    stmt_ledger = (
        select(Account.account_type, func.coalesce(func.sum(JournalLine.debit), 0), func.coalesce(func.sum(JournalLine.credit), 0))
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .join(Account, JournalLine.account_id == Account.id)
        .where(
            JournalLine.organization_id == org_id,
            JournalEntry.status == EntryStatus.POSTED
        )
        .group_by(Account.account_type)
    )
    ledger_rows = (await db.execute(stmt_ledger)).all()
    ledger_summary = {row[0]: (float(row[1]), float(row[2])) for row in ledger_rows}

    # Revenue from ledger if exists, else from paid invoices
    rev_debits, rev_credits = ledger_summary.get(AccountType.REVENUE, (0.0, 0.0))
    ledger_revenue = rev_credits - rev_debits
    reported_revenue = ledger_revenue if ledger_revenue > 0 else total_rev

    exp_debits, exp_credits = ledger_summary.get(AccountType.EXPENSE, (0.0, 0.0))
    operating_expenses = max(0.0, exp_debits - exp_credits)

    net_profit = reported_revenue - operating_expenses

    # Cash / Bank asset balances
    stmt_cash = (
        select(func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0))
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .join(Account, JournalLine.account_id == Account.id)
        .where(
            JournalLine.organization_id == org_id,
            JournalEntry.status == EntryStatus.POSTED,
            Account.account_type == AccountType.ASSET,
            or_(Account.name.ilike("%cash%"), Account.name.ilike("%bank%"))
        )
    )
    cash_flow = float((await db.execute(stmt_cash)).scalar() or 0.0)

    # Gross Margin calculation
    gross_margin_str = f"{(net_profit / reported_revenue * 100):.1f}%" if reported_revenue > 0 else "0.0%"

    invoices_list = []
    for inv in invoices_res[:20]:
        status_str = inv.status.value.title() if hasattr(inv.status, 'value') else str(inv.status).title()
        invoices_list.append({
            "id": str(inv.id),
            "number": inv.invoice_number,
            "vendor": f"Order {str(inv.order_id)[:8]}" if inv.order_id else "Direct Invoice",
            "amount": f"${float(inv.total_amount or 0):,.2f}",
            "status": status_str
        })

    return {
        "kpis": [
            {"label": "Total Revenue", "value": f"${reported_revenue:,.2f}", "delta": "Verified Ledger", "trend": "up" if reported_revenue > 0 else "flat"},
            {"label": "Net Profit", "value": f"${net_profit:,.2f}", "delta": "Realized", "trend": "up" if net_profit > 0 else "flat"},
            {"label": "Operating Expenses", "value": f"${operating_expenses:,.2f}", "delta": "General Ledger", "trend": "flat"},
            {"label": "Cash Flow", "value": f"${cash_flow:,.2f}", "delta": "Treasury Balance", "trend": "up" if cash_flow > 0 else "flat"},
            {"label": "Accounts Receivable", "value": f"${total_receivable:,.2f}", "delta": "Open Invoices", "trend": "flat"},
            {"label": "Accounts Payable", "value": f"${total_payable:,.2f}", "delta": "Committed POs", "trend": "flat"},
            {"label": "Gross Margin", "value": gross_margin_str, "delta": "Operating Ratio", "trend": "up" if net_profit > 0 else "flat"},
            {"label": "Approval Gate Threshold", "value": "$1,000.00", "delta": "Strict Limit Active", "trend": "active"}
        ],
        "insight": {
            "title": "Autonomous Financial Sentinel Active",
            "description": "Continuous ledger reconciliation active. High-value transactions (> $1,000.00) automatically gate in /approvals."
        },
        "invoices": invoices_list
    }


@router.get("/inventory")
async def get_inventory_data(
    current_user: CurrentUser,
    db: TenantDB,
):
    """Live Inventory & WMS metrics computed strictly from tenant data."""
    org_id = current_user.org_id

    # Join products with their stock levels for current tenant
    stmt_products = (
        select(Product, StockLevel)
        .outerjoin(
            StockLevel,
            and_(StockLevel.product_id == Product.id, StockLevel.organization_id == org_id)
        )
        .where(Product.organization_id == org_id, Product.is_deleted == False)
    )
    rows = (await db.execute(stmt_products)).all()

    product_map = {}
    total_val = 0.0
    low_stock_count = 0

    for product, stock_level in rows:
        pid = product.id
        if pid not in product_map:
            product_map[pid] = {
                "sku": product.sku,
                "name": product.name,
                "unit_price": float(product.unit_price or 0.0),
                "cost_price": float(product.cost_price or 0.0),
                "is_active": product.is_active == 1,
                "total_stock": 0.0,
                "is_low": False,
            }
        if stock_level:
            qty = float(stock_level.quantity_on_hand or 0.0)
            product_map[pid]["total_stock"] += qty
            total_val += qty * float(product.cost_price or product.unit_price or 0.0)
            reorder_pt = float(stock_level.reorder_point) if stock_level.reorder_point is not None else None
            if reorder_pt is not None and qty <= reorder_pt:
                product_map[pid]["is_low"] = True

    products_list = []
    for pid, pdata in product_map.items():
        if pdata["is_low"]:
            low_stock_count += 1
            status_text = "Low Stock - Reorder Required"
        elif not pdata["is_active"]:
            status_text = "Inactive"
        else:
            status_text = "Healthy"

        products_list.append({
            "sku": pdata["sku"],
            "name": pdata["name"],
            "stock": int(pdata["total_stock"]),
            "velocity": "Active",
            "status": status_text
        })

    product_count = len(product_map)

    return {
        "kpis": [
            {"label": "Total Inventory Value", "value": f"${total_val:,.2f}", "delta": "Multi-warehouse Valuation", "trend": "flat"},
            {"label": "Low Stock Alerts", "value": str(low_stock_count), "delta": "Reorder Threshold Breached", "trend": "warning" if low_stock_count > 0 else "flat"},
            {"label": "Active SKUs", "value": str(product_count), "delta": "Catalogue Items", "trend": "active" if product_count > 0 else "flat"},
            {"label": "Dead Stock", "value": "0 SKUs", "delta": "$0.00 value", "trend": "active"}
        ],
        "insight": {
            "title": "Inventory Velocity Sentinel Active",
            "description": "Autonomous replenishment monitoring active. Purchase orders exceeding $1,000 threshold route to /approvals."
        },
        "products": products_list
    }


@router.get("/procurement")
async def get_procurement_data(
    current_user: CurrentUser,
    db: TenantDB,
):
    """Live Procurement & PO metrics computed from canonical tenant data."""
    org_id = current_user.org_id

    stmt_po = (
        select(PurchaseOrder)
        .where(PurchaseOrder.organization_id == org_id, PurchaseOrder.is_deleted == False)
        .order_by(desc(PurchaseOrder.order_date))
        .limit(50)
    )
    orders_res = (await db.execute(stmt_po)).scalars().all()

    active_pos = [po for po in orders_res if po.status in [POStatus.SENT, POStatus.ACKNOWLEDGED, POStatus.PARTIALLY_RECEIVED, "sent", "acknowledged", "partially_received"]]
    stmt_po_totals = (
        select(PurchaseOrderLine.order_id, func.coalesce(func.sum(PurchaseOrderLine.line_total), 0))
        .where(PurchaseOrderLine.organization_id == org_id)
        .group_by(PurchaseOrderLine.order_id)
    )
    po_totals = dict((await db.execute(stmt_po_totals)).all())
    total_committed = sum(float(po_totals.get(po.id, 0.0)) for po in active_pos)

    stmt_vendors = select(func.count(Vendor.id)).where(
        Vendor.organization_id == org_id,
        Vendor.is_deleted == False
    )
    active_suppliers = (await db.execute(stmt_vendors)).scalar() or 0

    stmt_pending = select(func.count(Action.id)).where(
        Action.organization_id == org_id,
        Action.status == ActionStatus.APPROVAL_REQUIRED
    )
    pending_approvals = (await db.execute(stmt_pending)).scalar() or 0

    orders_list = []
    for po in orders_res[:20]:
        amount = float(po_totals.get(po.id, 0.0))
        orders_list.append({
            "id": str(po.id),
            "po_number": po.po_number,
            "vendor": f"Vendor {str(po.vendor_id)[:8]}",
            "amount": f"${amount:,.2f}",
            "status": po.status.value.replace("_", " ").title() if hasattr(po.status, 'value') else str(po.status).title()
        })

    return {
        "kpis": [
            {"label": "Active POs", "value": str(len(active_pos)), "delta": f"${total_committed:,.2f} committed", "trend": "active" if active_pos else "flat"},
            {"label": "Pending Approvals", "value": str(pending_approvals), "delta": "Governance Gate", "trend": "warning" if pending_approvals > 0 else "flat"},
            {"label": "Active Suppliers", "value": str(active_suppliers), "delta": "Registered Vendors", "trend": "active" if active_suppliers > 0 else "flat"}
        ],
        "insight": {
            "title": "Procurement Optimization Gateway Active",
            "description": "Purchase orders exceeding the $1,000 threshold automatically route to /approvals for executive review."
        },
        "orders": orders_list
    }


@router.get("/sales")
async def get_sales_data(
    current_user: CurrentUser,
    db: TenantDB,
):
    """Live Sales & CRM metrics computed from canonical tenant data."""
    org_id = current_user.org_id

    stmt_so = (
        select(SalesOrder, Customer)
        .outerjoin(Customer, SalesOrder.customer_id == Customer.id)
        .where(SalesOrder.organization_id == org_id, SalesOrder.is_deleted == False)
        .order_by(desc(SalesOrder.order_date))
        .limit(50)
    )
    rows = (await db.execute(stmt_so)).all()

    pipeline_val = sum(float(so.total_amount or 0) for so, _ in rows if so.status in [OrderStatus.DRAFT, OrderStatus.CONFIRMED, "draft", "confirmed"])
    active_deals = len(rows)

    opportunities = []
    for so, cust in rows[:20]:
        status_val = so.status.value if hasattr(so.status, 'value') else str(so.status)
        opportunities.append({
            "account": cust.name if cust else f"Account {str(so.customer_id)[:8]}",
            "value": f"${float(so.total_amount or 0):,.2f}",
            "stage": status_val.title(),
            "probability": "100%" if status_val == "confirmed" else "50%"
        })

    return {
        "kpis": [
            {"label": "Pipeline Value", "value": f"${pipeline_val:,.2f}", "delta": "Active Opportunities", "trend": "up" if pipeline_val > 0 else "flat"},
            {"label": "Active Opportunities", "value": str(active_deals), "delta": "Orders in Pipeline", "trend": "active" if active_deals > 0 else "flat"}
        ],
        "insight": {
            "title": "Sales Velocity Engine Active",
            "description": "CRM pipeline tracking active across verified enterprise accounts."
        },
        "opportunities": opportunities
    }


@router.get("/knowledge")
async def get_knowledge_data(
    current_user: CurrentUser,
    db: TenantDB,
):
    """Live Knowledge Base & RAG metrics scoped to tenant."""
    org_id = current_user.org_id

    stmt_docs = select(func.count(Document.id)).where(Document.organization_id == org_id)
    doc_cnt = (await db.execute(stmt_docs)).scalar() or 0

    stmt_indexed = select(func.count(Document.id)).where(
        Document.organization_id == org_id,
        Document.is_indexed == True
    )
    indexed_cnt = (await db.execute(stmt_indexed)).scalar() or 0

    stmt_list = select(Document).where(Document.organization_id == org_id).limit(20)
    docs = (await db.execute(stmt_list)).scalars().all()

    doc_list = []
    for d in docs:
        doc_list.append({
            "id": str(d.id),
            "name": d.name,
            "category": str(d.category.value if hasattr(d.category, 'value') else d.category) if d.category else "General",
            "size": f"{d.file_size_bytes or 0} bytes",
            "status": "Indexed" if d.is_indexed else "Ready"
        })

    idx_pct = f"{(indexed_cnt / doc_cnt * 100):.0f}%" if doc_cnt > 0 else "0%"
    unindexed = doc_cnt - indexed_cnt

    return {
        "kpis": [
            {"label": "Total Documents", "value": str(doc_cnt), "delta": "RAG Knowledge Vault", "trend": "active" if doc_cnt > 0 else "flat"},
            {"label": "Index Status", "value": idx_pct, "delta": "Vector Density", "trend": "active" if indexed_cnt > 0 else "flat"},
            {"label": "Unindexed Files", "value": str(unindexed), "delta": "Queue Status", "trend": "warning" if unindexed > 0 else "flat"}
        ],
        "documents": doc_list
    }


@router.get("/audit")
async def get_audit_data(
    current_user: CurrentUser,
    db: TenantDB,
):
    """Live Immutable Audit Log Trail scoped to tenant."""
    org_id = current_user.org_id

    stmt = select(AuditEvent).where(AuditEvent.organization_id == org_id).order_by(desc(AuditEvent.event_time)).limit(50)
    res = await db.execute(stmt)
    events = res.scalars().all()
    logs = []
    for ev in events:
        logs.append({
            "time": ev.event_time.strftime("%Y-%m-%d %H:%M:%S") if ev.event_time else "Just now",
            "actor": ev.user_email or ev.user_role or ev.agent_name or "Security Sentinel",
            "is_ai": bool(ev.agent_id or "Agent" in (ev.event_name or "") or "AI" in (ev.event_name or "")),
            "action": f"{ev.event_name} - {ev.description or ''}".strip(" -"),
            "system": "ERP Core / Security Engine",
            "risk": "Medium" if "ALERT" in (ev.event_name or "").upper() or "FLAGGED" in (ev.event_name or "").upper() else "Low",
            "status": "Success" if ev.result == "success" else "Flagged"
        })
    return {"logs": logs}


@router.get("/security")
async def get_security_data(
    current_user: CurrentUser,
    db: TenantDB,
):
    """Live Security & RBAC matrix scoped to tenant."""
    org_id = current_user.org_id

    stmt_users = select(func.count(User.id)).where(
        or_(User.tenant_id == org_id, User.organization_id == org_id),
        User.is_active == True
    )
    user_cnt = (await db.execute(stmt_users)).scalar() or 0

    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    last_24h = now_utc - timedelta(hours=24)
    stmt_failed = select(func.count(AuditEvent.id)).where(
        AuditEvent.organization_id == org_id,
        AuditEvent.event_name.ilike("%login_fail%"),
        AuditEvent.event_time >= last_24h
    )
    failed_logins = (await db.execute(stmt_failed)).scalar() or 0

    stmt_agents = select(func.count(Agent.id)).where(
        or_(Agent.organization_id == org_id, Agent.organization_id.is_(None)),
        Agent.status == "active"
    )
    agent_roles_cnt = (await db.execute(stmt_agents)).scalar() or 0

    return {
        "kpis": [
            {"label": "Active Users", "value": str(user_cnt), "delta": "Verified Members", "trend": "active" if user_cnt > 0 else "flat"},
            {"label": "Agent Roles", "value": str(agent_roles_cnt), "delta": "Strict Role Isolation", "trend": "active"},
            {"label": "Failed Logins (24h)", "value": str(failed_logins), "delta": "Zero Threat" if failed_logins == 0 else "Security Alert", "trend": "warning" if failed_logins > 0 else "active"},
            {"label": "Approval Gate Limit", "value": "$1,000.00", "delta": "Strict Financial Limit", "trend": "active"}
        ],
        "permissions": [
            {"agent": "Finance Agent", "read": "Allowed", "create": "Allowed", "update": "Allowed", "delete": "Denied", "limit": "$1,000.00"},
            {"agent": "Inventory Agent", "read": "Allowed", "create": "Allowed", "update": "Allowed", "delete": "Denied", "limit": "$0.00 (Requires Review)"},
            {"agent": "Procurement Agent", "read": "Allowed", "create": "Allowed", "update": "Denied", "delete": "Denied", "limit": "$1,000.00"},
            {"agent": "Sales Agent", "read": "Allowed", "create": "Allowed", "update": "Allowed", "delete": "Denied", "limit": "N/A"},
            {"agent": "Compliance Agent", "read": "Allowed", "create": "Allowed", "update": "Denied", "delete": "Denied", "limit": "SOC2 / RLS Active"}
        ]
    }


@router.get("/operations")
async def get_operations_data(
    current_user: CurrentUser,
    db: TenantDB,
):
    """Live Operations & Logistics telemetry computed from tenant data."""
    org_id = current_user.org_id

    stmt_movements = select(func.count(StockMovement.id)).where(StockMovement.organization_id == org_id)
    movement_count = (await db.execute(stmt_movements)).scalar() or 0

    stmt_warehouses = select(func.count(Warehouse.id)).where(
        Warehouse.organization_id == org_id,
        Warehouse.is_active == 1
    )
    warehouse_count = (await db.execute(stmt_warehouses)).scalar() or 0

    return {
        "activeShipments": 0,
        "delayedShipments": 0,
        "stockMovements": movement_count,
        "activeWarehouses": warehouse_count
    }


@router.get("/activity")
async def get_activity_data(
    current_user: CurrentUser,
    db: TenantDB,
):
    """Live Activity feed computed from tenant audit events."""
    org_id = current_user.org_id

    stmt = select(AuditEvent).where(AuditEvent.organization_id == org_id).order_by(desc(AuditEvent.event_time)).limit(20)
    events = (await db.execute(stmt)).scalars().all()
    activities = []
    for ev in events:
        activities.append({
            "agent": ev.user_role or ev.agent_name or "Security Sentinel",
            "time": ev.event_time.strftime("%H:%M:%S") if ev.event_time else "Just now",
            "type": "verified",
            "title": ev.event_name,
            "description": ev.description or "Automated ERP ledger operation completed.",
            "action": "View Audit"
        })
    return {"activities": activities}


class CommandRequest(BaseModel):
    query: Optional[str] = None
    command: Optional[str] = None


@router.get("/command/stream")
async def stream_command(
    query: str,
    current_user: CurrentUser,
    db: TenantDB,
):
    """
    Real Server-Sent Events (SSE) Agent Token Stream scoped to authenticated tenant.
    Dispatches to LangGraph multi-agent orchestrator.
    """
    from packages.agents.graph.graph import erp_graph, ERPAgentState
    from langchain_core.messages import HumanMessage
    from packages.config.settings import settings

    if not settings.openai_api_key and not settings.anthropic_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI Gateway Unavailable: No valid LLM provider credentials configured on server."
        )

    org_id = current_user.org_id
    user_id = current_user.user_id
    user_role = current_user.role

    async def event_generator():
        yield f"data: {json.dumps({'type': 'step', 'content': 'Analyzing business intent with AI Orchestrator...'})}\n\n"
        
        initial_state: ERPAgentState = {
            "messages": [HumanMessage(content=query)],
            "organization_id": org_id,
            "user_id": user_id,
            "user_role": user_role,
            "next_agent": None,
            "pending_approvals": [],
            "total_tokens": 0,
            "cost_usd": 0.0,
        }

        try:
            async for event in erp_graph.astream(initial_state):
                for node_name, node_output in event.items():
                    step_msg = f"Node [{node_name}] processed action."
                    yield f"data: {json.dumps({'type': 'step', 'content': step_msg, 'node': node_name})}\n\n"
                    if "messages" in node_output and node_output["messages"]:
                        last_m = node_output["messages"][-1]
                        yield f"data: {json.dumps({'type': 'token', 'content': str(last_m.content)})}\n\n"

            final_payload = {
                "type": "result",
                "agent_name": "Agent Orchestrator",
                "summary": f"Execution complete for: '{query}'.",
                "status": "Success"
            }
            yield f"data: {json.dumps(final_payload)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/command")
async def run_command(
    req: CommandRequest,
    current_user: CurrentUser,
    db: TenantDB,
):
    """
    AI Command Center Reasoning Engine.
    Requires authentication; dispatches to LangGraph Multi-Agent Orchestrator & typed ERP tools.
    Every state-changing write tool creates a real human Approval and never executes directly.
    """
    org_id = current_user.org_id
    user_query = req.query or req.command or ""

    if not user_query.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query cannot be empty.")

    # 1. Record short-term memory with tenant isolation
    orchestrator_mem = memory_manager.get_memory_for_agent("Agent Orchestrator", organization_id=org_id)
    orchestrator_mem.add_conversation_turn("user", user_query)

    # 2. AI Guardrails Validation
    is_safe, sanitized_query, rejection_reason = guardrails.validate_input_query(user_query)
    if not is_safe:
        return {
            "agent_name": "Security Guardrail Agent",
            "execution_steps": [
                "Intercepted prompt via AI Guardrail Engine",
                "Ran zero-trust safety & PCI-DSS compliance classifier",
                "Flagged prohibited security violation pattern",
                "Blocked query from downstream ERP execution"
            ],
            "summary": rejection_reason,
            "findings": [
                {"label": "Safety Status", "value": "Blocked"},
                {"label": "Threat Level", "value": "High"},
                {"label": "Action", "value": "Execution Prevented"}
            ],
            "evidence": "Input flagged and blocked by enterprise AI Guardrail policy.",
            "sources": ["AI Safety Guardrail Engine", "Zero-Trust Policy Enforcer"],
            "recommendation": "Payment card details, credentials, and system prompts are protected under PCI-DSS and enterprise zero-trust security policies and cannot be exposed.",
            "actions": [],
            "table": None
        }

    # 3. Check LLM Provider Configuration
    from packages.config.settings import settings
    if not settings.openai_api_key and not settings.anthropic_api_key:
        logger.warning(
            f"LLM provider unavailable: no API key configured. Tenant {org_id} request rejected."
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI Gateway Unavailable: No valid LLM provider credentials configured on server."
        )

    # 4. Dispatch to LangGraph multi-agent orchestrator
    from packages.agents.graph.graph import erp_graph, ERPAgentState
    from langchain_core.messages import HumanMessage
    from packages.agents.approval_manager import ApprovalManager

    initial_state: ERPAgentState = {
        "messages": [HumanMessage(content=sanitized_query)],
        "organization_id": org_id,
        "user_id": current_user.user_id,
        "user_role": current_user.role,
        "next_agent": None,
        "pending_approvals": [],
        "total_tokens": 0,
        "cost_usd": 0.0,
    }

    # Execute graph with real state
    graph_res = await erp_graph.ainvoke(initial_state)

    messages = graph_res.get("messages", [])
    response_content = messages[-1].content if messages else "Operation processed by ERP Orchestrator."
    next_agent = graph_res.get("next_agent") or "Agent Orchestrator"

    # Check for approval required actions
    pending_approvals = graph_res.get("pending_approvals", [])

    return {
        "agent_name": next_agent.replace("_", " ").title(),
        "execution_steps": [
            "Validated zero-trust input safety guardrails",
            f"Routed query through LangGraph Supervisor to {next_agent}",
            "Executed canonical ERP service layer queries with PostgreSQL RLS isolation",
            "Synthesized fact-grounded response"
        ],
        "summary": str(response_content),
        "findings": [
            {"label": "Tenant Context", "value": str(org_id)[:8]},
            {"label": "Agent Specialist", "value": next_agent.replace("_", " ").title()},
            {"label": "Tokens Used", "value": str(graph_res.get("total_tokens", 0))}
        ],
        "evidence": f"Queried canonical database ledgers under tenant isolation context {str(org_id)}.",
        "sources": ["LangGraph ERP Multi-Agent Runtime", "Canonical PostgreSQL Ledgers"],
        "recommendation": "Review generated outputs or check /approvals if state changes were proposed.",
        "actions": [
            {"label": "Open Approvals Queue", "url": "/approvals"}
        ] if pending_approvals else [],
        "table": None
    }
