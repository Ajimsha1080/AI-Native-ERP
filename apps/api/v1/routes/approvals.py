"""
Approvals REST API routes for human-in-the-loop agent actions.
"""

from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from packages.database.tenant_context import TenantDB
from packages.auth.dependencies import CurrentUser, require_role
from packages.database.models.erp.agent_runs import PendingApproval, ApprovalStatus
from packages.agents.graph.tools.erp_tools import tool_adjust_stock

router = APIRouter(prefix="/approvals", tags=["Approvals"])


class PendingApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    tool_name: str
    inputs: dict
    status: ApprovalStatus
    risk_level: str
    reason: Optional[str] = None


@router.get("", response_model=List[PendingApprovalResponse])
async def list_pending_approvals(
    current_user: CurrentUser,
    db: TenantDB,
    status_filter: Optional[ApprovalStatus] = ApprovalStatus.PENDING,
):
    q = select(PendingApproval).where(PendingApproval.organization_id == current_user.org_id)
    if status_filter:
        q = q.where(PendingApproval.status == status_filter)
    result = await db.execute(q)
    return list(result.scalars().all())


@router.post("/{approval_id}/approve", response_model=PendingApprovalResponse)
async def approve_action(
    approval_id: UUID,
    current_user: CurrentUser,
    db: TenantDB,
    _: None = Depends(require_role("owner", "admin", "manager")),
):
    result = await db.execute(
        select(PendingApproval).where(
            PendingApproval.id == approval_id,
            PendingApproval.organization_id == current_user.org_id,
        )
    )
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found")

    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Action already {approval.status.value}")

    # Execute approved action
    exec_result = {}
    if approval.tool_name == "adjust_stock":
        inp = approval.inputs
        exec_result = await tool_adjust_stock(
            organization_id=current_user.org_id,
            product_id=UUID(inp["product_id"]),
            warehouse_id=UUID(inp["warehouse_id"]),
            delta=float(inp["delta"]),
            reason=inp.get("reason", "Approved by human operator"),
        )

    approval.status = ApprovalStatus.APPROVED
    approval.approved_by_id = current_user.user_id
    approval.approved_at = datetime.now(timezone.utc)
    approval.execution_result = exec_result
    await db.commit()

    return approval


@router.post("/{approval_id}/reject", response_model=PendingApprovalResponse)
async def reject_action(
    approval_id: UUID,
    current_user: CurrentUser,
    db: TenantDB,
    _: None = Depends(require_role("owner", "admin", "manager")),
):
    result = await db.execute(
        select(PendingApproval).where(
            PendingApproval.id == approval_id,
            PendingApproval.organization_id == current_user.org_id,
        )
    )
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval request not found")

    approval.status = ApprovalStatus.REJECTED
    approval.approved_by_id = current_user.user_id
    approval.approved_at = datetime.now(timezone.utc)
    await db.commit()

    return approval
