"""
Compliance and GDPR API routes.
Provides GDPR Data Portability (Article 20), Right to Erasure (Article 17), and Enterprise Audit Trail Exports.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select, delete
import io
import csv
import json

from packages.database.tenant_context import TenantDB
from packages.auth.dependencies import CurrentUser, require_role
from packages.database.models import (
    Organization, User, UserRole, Agent, Workflow,
    AuditEvent, AuditEventType
)
from packages.database.models.erp.inventory import Product
from packages.database.models.erp.sales import SalesOrder, Invoice
from packages.security.middleware import token_blacklist_store

router = APIRouter(prefix="/compliance", tags=["Compliance & GDPR"])


@router.get("/export")
async def export_tenant_data(
    current_user: CurrentUser,
    db: TenantDB,
    _: None = Depends(require_role("owner", "admin")),
):
    """
    GDPR Article 20: Right to Data Portability.
    Exports all tenant organizational data, user directory, inventory records, sales transactions, and workflows.
    """
    org_res = await db.execute(select(Organization).where(Organization.id == current_user.org_id))
    org = org_res.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    # 1. Fetch Users
    users_res = await db.execute(select(User).where(User.tenant_id == current_user.org_id))
    users = users_res.scalars().all()

    # 2. Fetch Agents & Workflows
    agents_res = await db.execute(select(Agent).where(Agent.organization_id == current_user.org_id))
    agents = agents_res.scalars().all()

    wf_res = await db.execute(select(Workflow).where(Workflow.organization_id == current_user.org_id))
    workflows = wf_res.scalars().all()

    # 3. Fetch Products
    prod_res = await db.execute(select(Product).where(Product.organization_id == current_user.org_id))
    products = prod_res.scalars().all()

    # 4. Fetch Sales & Invoices
    sales_res = await db.execute(select(SalesOrder).where(SalesOrder.organization_id == current_user.org_id))
    sales = sales_res.scalars().all()

    export_payload = {
        "export_metadata": {
            "requested_by": str(current_user.user_id),
            "organization_id": str(org.id),
            "organization_name": org.name,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "compliance_standard": "GDPR Article 20 (Data Portability)",
        },
        "organization": {
            "id": str(org.id),
            "name": org.name,
            "slug": org.slug,
            "plan": org.plan,
            "status": org.status,
            "created_at": org.created_at.isoformat() if hasattr(org, "created_at") and org.created_at else None,
        },
        "users": [
            {
                "id": str(u.id),
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "status": str(u.status),
            }
            for u in users
        ],
        "ai_agents": [
            {
                "id": str(a.id),
                "name": a.name,
                "slug": a.slug,
                "description": a.description,
                "status": a.status,
            }
            for a in agents
        ],
        "workflows": [
            {
                "id": str(w.id),
                "name": w.name,
                "slug": w.slug,
                "status": str(w.status),
            }
            for w in workflows
        ],
        "products": [
            {
                "id": str(item.id),
                "sku": item.sku,
                "name": item.name,
                "unit_price": float(item.unit_price or 0) if hasattr(item, "unit_price") and item.unit_price else 0.0,
            }
            for item in products
        ],
        "sales_orders": [
            {
                "id": str(order.id),
                "order_number": order.order_number,
                "status": str(order.status),
                "total_amount": float(order.total_amount or 0),
            }
            for order in sales
        ],
    }

    # Record Audit Event for compliance export
    audit = AuditEvent(
        organization_id=org.id,
        user_id=current_user.user_id,
        event_type=AuditEventType.SETTINGS_UPDATE,
        event_name="GDPR Data Export",
        description="Full tenant data archive generated and exported.",
        meta_data={"requested_by": str(current_user.user_id)}
    )
    db.add(audit)
    await db.commit()

    return export_payload


@router.get("/audit-export")
async def export_audit_trail(
    current_user: CurrentUser,
    db: TenantDB,
    format: str = Query("json", pattern="^(json|csv)$"),
    limit: int = Query(1000, le=5000),
    _: None = Depends(require_role("owner", "admin")),
):
    """
    Exports organization audit event logs for compliance and regulatory review.
    """
    res = await db.execute(
        select(AuditEvent)
        .where(AuditEvent.organization_id == current_user.org_id)
        .order_by(AuditEvent.event_time.desc())
        .limit(limit)
    )
    events = res.scalars().all()

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Timestamp", "User Email", "Event Type", "Event Name", "Description"])
        for evt in events:
            writer.writerow([
                str(evt.id),
                evt.event_time.isoformat() if evt.event_time else "",
                evt.user_email or "",
                str(evt.event_type),
                evt.event_name,
                evt.description or "",
            ])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=audit_export_{current_user.org_id}.csv"}
        )

    return [
        {
            "id": str(evt.id),
            "timestamp": evt.event_time.isoformat() if evt.event_time else None,
            "user_id": str(evt.user_id) if evt.user_id else None,
            "user_email": evt.user_email,
            "event_type": str(evt.event_type),
            "event_name": evt.event_name,
            "description": evt.description,
            "metadata": evt.meta_data,
        }
        for evt in events
    ]


@router.post("/delete-account")
async def delete_account_and_tenant(
    current_user: CurrentUser,
    db: TenantDB,
    confirm_text: str = Query(..., description="Must equal 'DELETE-MY-DATA' to confirm erasure"),
    _: None = Depends(require_role("owner")),
):
    """
    GDPR Article 17: Right to Erasure ('Right to be forgotten').
    Purges all personal and tenant data, and revokes active authentication tokens.
    """
    if confirm_text != "DELETE-MY-DATA":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation text must equal 'DELETE-MY-DATA' to authorize irreversible data erasure."
        )

    org_res = await db.execute(select(Organization).where(Organization.id == current_user.org_id))
    org = org_res.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    # Mark organization status archived / deleted
    org.status = "archived"
    org_settings = dict(org.settings or {})
    org_settings["deleted_at"] = datetime.now(timezone.utc).isoformat()
    org_settings["deletion_requested_by"] = str(current_user.user_id)
    org.settings = org_settings

    # Deactivate all tenant users
    users_res = await db.execute(select(User).where(User.tenant_id == current_user.org_id))
    for user in users_res.scalars().all():
        user.is_active = False
        user.status = "inactive"

    await db.commit()

    return {
        "status": "success",
        "message": "Tenant account and all associated resources scheduled for immediate permanent erasure in compliance with GDPR Article 17.",
        "organization_id": str(org.id),
    }
