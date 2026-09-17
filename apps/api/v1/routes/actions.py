"""Action and Approval State Machine Routes with TenantDB & CurrentUser."""

from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone

from packages.database.tenant_context import TenantDB
from packages.auth.dependencies import CurrentUser
from packages.database.models import (
    Action, Approval, User, Agent, AuditEvent, AuditEventType, ActionStatus, ActionType
)

router = APIRouter(prefix="/actions", tags=["Actions"])


@router.get("/approvals-queue")
async def get_approvals_queue(
    current_user: CurrentUser,
    db: TenantDB,
):
    """
    Get actions formatted for Human-in-the-Loop Approvals Page scoped to tenant.
    """
    stmt = (
        select(Action, Agent)
        .outerjoin(Agent, Action.agent_id == Agent.id)
        .where(Action.organization_id == current_user.org_id)
        .order_by(desc(Action.proposed_at))
    )
    result = await db.execute(stmt)
    rows = result.all()

    items = []
    for action, agent in rows:
        status_str = "pending"
        raw_status = str(action.status.value if hasattr(action.status, 'value') else action.status).lower()
        if raw_status in ["approved", "executed", "verified"]:
            status_str = "approved"
        elif raw_status in ["rejected", "failed", "cancelled"]:
            status_str = "rejected"
        else:
            status_str = "pending"

        amount_val = 0.0
        if action.action_data and isinstance(action.action_data, dict):
            amount_val = float(action.action_data.get("amount", 0.0))

        items.append({
            "id": str(action.id),
            "title": action.name,
            "subtitle": action.description or f"Action proposed by {agent.name if agent else 'Autonomous Agent'}",
            "amount": f"${amount_val:,.2f}" if amount_val > 0 else "$1,000.00+",
            "status": status_str,
            "raw_status": raw_status,
            "agent": agent.name if agent else "Autonomous Agent",
            "system": "Enterprise Decision Gate",
            "time": action.proposed_at.strftime("%b %d, %H:%M") if action.proposed_at else "Just now",
            "urgent": amount_val > 2500,
            "details": [
                f"Proposed at: {action.proposed_at.strftime('%Y-%m-%d %H:%M UTC') if action.proposed_at else 'Recent'}",
                "Autonomous spending threshold: $1,000.00",
                f"Policy compliance: {'Verified' if action.policy_compliant else 'Review needed'}"
            ],
            "action_data": action.action_data or {}
        })

    return items


@router.get("")
async def list_actions(
    current_user: CurrentUser,
    db: TenantDB,
    page: int = 1,
    page_size: int = 20,
    action_type: Optional[str] = None,
    status_filter: Optional[str] = None,
):
    """List all actions for tenant with optional filters."""
    query = select(Action).where(Action.organization_id == current_user.org_id)

    if action_type:
        query = query.where(Action.action_type == action_type)
    if status_filter:
        query = query.where(Action.status == status_filter)

    query = query.order_by(desc(Action.proposed_at))
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    actions = result.scalars().all()

    return {
        "items": actions,
        "page": page,
        "page_size": page_size
    }


@router.get("/{action_id}")
async def get_action(
    action_id: str,
    current_user: CurrentUser,
    db: TenantDB,
):
    """Get single action by ID scoped to tenant."""
    try:
        action_uuid = UUID(action_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid action UUID format")

    result = await db.execute(
        select(Action).where(
            Action.id == action_uuid,
            Action.organization_id == current_user.org_id
        )
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    return action


@router.post("/{action_id}/approve")
async def approve_action(
    action_id: str,
    current_user: CurrentUser,
    db: TenantDB,
    payload: Optional[Dict[str, Any]] = Body(default={}),
):
    """
    Approve an action in APPROVAL_REQUIRED status.
    """
    try:
        action_uuid = UUID(action_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid action UUID format")

    result = await db.execute(
        select(Action).where(
            Action.id == action_uuid,
            Action.organization_id == current_user.org_id
        )
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    action.status = ActionStatus.APPROVED
    action.approved_at = datetime.now(timezone.utc)
    action.approved_by_id = current_user.id

    app_res = await db.execute(select(Approval).where(Approval.action_id == action_uuid))
    approval = app_res.scalars().first()
    if approval:
        approval.status = "approved"
        approval.approved_at = datetime.now(timezone.utc)
        approval.approver_id = current_user.id
    else:
        approval = Approval(
            action_id=action.id,
            approver_id=current_user.id,
            status="approved",
            approval_type="financial",
            approved_at=datetime.now(timezone.utc),
            justification=payload.get("comments", "Authorized by Executive via Human Approvals Gate")
        )
        db.add(approval)

    audit_ev = AuditEvent(
        organization_id=current_user.org_id,
        user_id=current_user.id,
        user_email=current_user.email,
        user_role="Executive Approver",
        action_id=action.id,
        event_type=AuditEventType.ACTION_APPROVE,
        event_name=f"Action Approved: {action.name}",
        description=f"Action {action.name} authorized by executive. Status transitioned to APPROVED.",
        result="success"
    )
    db.add(audit_ev)

    await db.commit()
    await db.refresh(action)

    return {
        "ok": True,
        "message": f"Action '{action.name}' approved successfully.",
        "action_id": str(action.id),
        "status": "approved"
    }


@router.post("/{action_id}/reject")
async def reject_action(
    action_id: str,
    current_user: CurrentUser,
    db: TenantDB,
    payload: Optional[Dict[str, Any]] = Body(default={}),
):
    """
    Reject an action in APPROVAL_REQUIRED status.
    """
    try:
        action_uuid = UUID(action_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid action UUID format")

    result = await db.execute(
        select(Action).where(
            Action.id == action_uuid,
            Action.organization_id == current_user.org_id
        )
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    action.status = ActionStatus.REJECTED

    app_res = await db.execute(select(Approval).where(Approval.action_id == action_uuid))
    approval = app_res.scalars().first()
    if approval:
        approval.status = "rejected"
        approval.approver_id = current_user.id
    else:
        approval = Approval(
            action_id=action.id,
            approver_id=current_user.id,
            status="rejected",
            approval_type="financial",
            justification=payload.get("rejection_reason", "Declined by Executive")
        )
        db.add(approval)

    audit_ev = AuditEvent(
        organization_id=current_user.org_id,
        user_id=current_user.id,
        user_email=current_user.email,
        user_role="Executive Approver",
        action_id=action.id,
        event_type=AuditEventType.ACTION_REJECT,
        event_name=f"Action Rejected: {action.name}",
        description=f"Action {action.name} rejected by executive.",
        result="success"
    )
    db.add(audit_ev)

    await db.commit()
    await db.refresh(action)

    return {
        "ok": True,
        "message": f"Action '{action.name}' rejected.",
        "action_id": str(action.id),
        "status": "rejected"
    }


@router.put("/{action_id}")
async def update_action(
    action_id: str,
    current_user: CurrentUser,
    db: TenantDB,
    payload: Dict[str, Any] = Body(...),
):
    """Update action parameters scoped to tenant."""
    try:
        action_uuid = UUID(action_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid action UUID format")

    result = await db.execute(
        select(Action).where(
            Action.id == action_uuid,
            Action.organization_id == current_user.org_id
        )
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    if "name" in payload:
        action.name = payload["name"]
    if "description" in payload:
        action.description = payload["description"]
    if "action_data" in payload:
        action.action_data = payload["action_data"]
    elif "amount" in payload:
        data = dict(action.action_data or {})
        try:
            data["amount"] = float(str(payload["amount"]).replace("$", "").replace(",", ""))
        except ValueError:
            pass
        action.action_data = data

    action.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(action)

    return {
        "ok": True,
        "action_id": str(action.id),
        "action": action
    }