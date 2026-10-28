"""
Approvals REST API routes for human-in-the-loop agent actions.
Unified on Action + Approval enterprise governance flow.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, desc

from packages.database.tenant_context import TenantDB
from packages.auth.dependencies import CurrentUser, require_role
from packages.database.models import Action, ActionStatus
from packages.agents.approval_service import process_approval_decision

router = APIRouter(prefix="/approvals", tags=["Approvals"])


class PendingApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    tool_name: str
    inputs: dict
    status: str
    risk_level: str
    reason: Optional[str] = None
    execution_result: Optional[dict] = None


@router.get("", response_model=List[PendingApprovalResponse])
async def list_pending_approvals(
    current_user: CurrentUser,
    db: TenantDB,
    status_filter: Optional[str] = "pending",
):
    """List actions requiring approval scoped to tenant."""
    q = (
        select(Action)
        .where(Action.organization_id == current_user.org_id)
        .order_by(desc(Action.proposed_at))
    )
    if status_filter:
        s = status_filter.lower()
        if s == "pending":
            q = q.where(Action.status.in_([ActionStatus.APPROVAL_REQUIRED, ActionStatus.PROPOSED]))
        elif s == "approved":
            q = q.where(Action.status.in_([ActionStatus.APPROVED, ActionStatus.EXECUTED]))
        elif s == "rejected":
            q = q.where(Action.status == ActionStatus.REJECTED)

    result = await db.execute(q)
    actions = result.scalars().all()

    items = []
    for a in actions:
        raw_s = str(a.status.value if hasattr(a.status, 'value') else a.status).lower()
        disp_status = "approved" if raw_s in ["approved", "executed"] else ("rejected" if raw_s == "rejected" else "pending")
        amount = float(a.estimated_cost or (a.action_data or {}).get("amount", 0.0))
        items.append(
            PendingApprovalResponse(
                id=a.id,
                organization_id=a.organization_id,
                tool_name=a.name,
                inputs=a.action_data or {},
                status=disp_status,
                risk_level="high" if amount >= 1000.0 else "medium",
                reason=a.description,
                execution_result=a.execution_result
            )
        )
    return items


@router.post("/{approval_id}/approve", response_model=PendingApprovalResponse)
async def approve_action(
    approval_id: UUID,
    current_user: CurrentUser,
    db: TenantDB,
    _: None = Depends(require_role("owner", "admin", "manager")),
):
    result = await process_approval_decision(
        session=db,
        action_id=approval_id,
        approver_id=current_user.user_id,
        approver_email=current_user.email,
        approver_role=current_user.role,
        organization_id=current_user.org_id,
        decision="approve",
    )

    stmt = select(Action).where(Action.id == approval_id, Action.organization_id == current_user.org_id)
    action = (await db.execute(stmt)).scalar_one()

    return PendingApprovalResponse(
        id=action.id,
        organization_id=action.organization_id,
        tool_name=action.name,
        inputs=action.action_data or {},
        status=result.get("status", "pending"),
        risk_level="high" if float(action.estimated_cost or 0) >= 1000.0 else "medium",
        reason=result.get("message", action.description),
        execution_result=action.execution_result
    )


@router.post("/{approval_id}/reject", response_model=PendingApprovalResponse)
async def reject_action(
    approval_id: UUID,
    current_user: CurrentUser,
    db: TenantDB,
    _: None = Depends(require_role("owner", "admin", "manager")),
):
    result = await process_approval_decision(
        session=db,
        action_id=approval_id,
        approver_id=current_user.user_id,
        approver_email=current_user.email,
        approver_role=current_user.role,
        organization_id=current_user.org_id,
        decision="reject",
    )

    stmt = select(Action).where(Action.id == approval_id, Action.organization_id == current_user.org_id)
    action = (await db.execute(stmt)).scalar_one()

    return PendingApprovalResponse(
        id=action.id,
        organization_id=action.organization_id,
        tool_name=action.name,
        inputs=action.action_data or {},
        status="rejected",
        risk_level="high" if float(action.estimated_cost or 0) >= 1000.0 else "medium",
        reason=result.get("message", action.description),
        execution_result=action.execution_result
    )
