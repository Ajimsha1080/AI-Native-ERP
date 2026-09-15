"""Action and Approval State Machine Routes."""

from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from packages.database import get_db
from packages.database.models import (
    Action, Approval, User, Agent, AuditEvent, AuditEventType, ActionStatus, ActionType
)
from packages.security.auth import get_current_user

router = APIRouter(prefix="/actions", tags=["Actions"])


@router.get("/approvals-queue")
async def get_approvals_queue(db: AsyncSession = Depends(get_db)):
    """
    Get all actions formatted specifically for the Human-in-the-Loop Approvals Page.
    """
    stmt = (
        select(Action, Agent)
        .outerjoin(Agent, Action.agent_id == Agent.id)
        .order_by(desc(Action.proposed_at))
    )
    result = await db.execute(stmt)
    rows = result.all()

    items = []
    for action, agent in rows:
        # Determine status string
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
                f"Autonomous spending threshold: $1,000.00",
                f"Policy compliance: {'Verified' if action.policy_compliant else 'Review needed'}"
            ],
            "action_data": action.action_data or {}
        })

    return items


@router.get("")
async def list_actions(
    page: int = 1,
    page_size: int = 20,
    action_type: Optional[str] = None,
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """List all actions with optional filters."""
    query = select(Action)

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
    db: AsyncSession = Depends(get_db)
):
    """Get single action by ID."""
    try:
        action_uuid = UUID(action_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid action UUID format")

    result = await db.execute(select(Action).where(Action.id == action_uuid))
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    return action


@router.post("/{action_id}/approve")
async def approve_action(
    action_id: str,
    payload: Optional[Dict[str, Any]] = Body(default={}),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Approve an action in APPROVAL_REQUIRED status.
    Executes state transition, logs approval record and audit event.
    """
    try:
        action_uuid = UUID(action_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid action UUID format")

    result = await db.execute(select(Action).where(Action.id == action_uuid))
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    # Transition status
    action.status = ActionStatus.APPROVED
    action.approved_at = datetime.utcnow()
    action.approved_by_id = current_user.id if current_user else None

    # Update or create approval record
    app_res = await db.execute(select(Approval).where(Approval.action_id == action_uuid))
    approval = app_res.scalars().first()
    if approval:
        approval.status = "approved"
        approval.approved_at = datetime.utcnow()
        if current_user:
            approval.approver_id = current_user.id
    else:
        approval = Approval(
            id=UUID(int=0) if False else None,
            action_id=action.id,
            approver_id=current_user.id if current_user else None,
            status="approved",
            approval_type="financial",
            approved_at=datetime.utcnow(),
            justification=payload.get("comments", "Authorized by Executive via Human Approvals Gate")
        )
        db.add(approval)

    # Log Audit Event
    audit_ev = AuditEvent(
        organization_id=action.organization_id,
        user_id=current_user.id if current_user else None,
        user_email=current_user.email if current_user else "admin@acme.com",
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
    payload: Optional[Dict[str, Any]] = Body(default={}),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Reject an action in APPROVAL_REQUIRED status.
    """
    try:
        action_uuid = UUID(action_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid action UUID format")

    result = await db.execute(select(Action).where(Action.id == action_uuid))
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    # Transition status
    action.status = ActionStatus.REJECTED

    # Update or create approval record
    app_res = await db.execute(select(Approval).where(Approval.action_id == action_uuid))
    approval = app_res.scalars().first()
    if approval:
        approval.status = "rejected"
        if current_user:
            approval.approver_id = current_user.id
    else:
        approval = Approval(
            action_id=action.id,
            approver_id=current_user.id if current_user else None,
            status="rejected",
            approval_type="financial",
            justification=payload.get("rejection_reason", "Declined by Executive")
        )
        db.add(approval)

    # Log Audit Event
    audit_ev = AuditEvent(
        organization_id=action.organization_id,
        user_id=current_user.id if current_user else None,
        user_email=current_user.email if current_user else "admin@acme.com",
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
    payload: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db)
):
    """Update action parameters (e.g. adjusted amount or notes)."""
    try:
        action_uuid = UUID(action_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid action UUID format")

    result = await db.execute(select(Action).where(Action.id == action_uuid))
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

    action.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(action)

    return {
        "ok": True,
        "action_id": str(action.id),
        "action": action
    }
