"""
User and Organization Membership Management with TenantDB and Real RBAC.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.tenant_context import TenantDB
from packages.database.models.base import utc_now
from packages.database.models.user import (
    User, UserStatus, OrganizationMember, OrganizationMemberRole, AuthenticationProvider
)
from packages.database.models.audit import AuditEvent, AuditEventType
from packages.auth.dependencies import CurrentUser, require_role, require_min_role
from ..schemas.base import PaginatedResponse

router = APIRouter(prefix="/users", tags=["Users"])


class InviteUserRequest(BaseModel):
    email: EmailStr
    role: str = "viewer"  # owner, admin, manager, viewer
    first_name: Optional[str] = "Invited"
    last_name: Optional[str] = "User"


class ChangeRoleRequest(BaseModel):
    role: str  # owner, admin, manager, viewer


class UserMemberResponse(BaseModel):
    id: UUID
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: Optional[datetime] = None


@router.get("", response_model=PaginatedResponse[Dict[str, Any]])
async def list_users(
    current_user: CurrentUser,
    db: TenantDB,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
):
    """List members belonging to the current user's organization."""
    query = (
        select(User, OrganizationMember.role)
        .join(OrganizationMember, User.id == OrganizationMember.user_id)
        .where(
            OrganizationMember.organization_id == current_user.org_id,
            User.is_active == True,
        )
    )

    if search:
        search_filter = or_(
            User.first_name.ilike(f"%{search}%"),
            User.last_name.ilike(f"%{search}%"),
            User.email.ilike(f"%{search}%"),
        )
        query = query.where(search_filter)

    count_query = (
        select(func.count(User.id))
        .join(OrganizationMember, User.id == OrganizationMember.user_id)
        .where(
            OrganizationMember.organization_id == current_user.org_id,
            User.is_active == True,
        )
    )
    if search:
        count_query = count_query.where(search_filter)

    total_res = await db.execute(count_query)
    total = total_res.scalar() or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    rows = result.all()

    items = []
    for user, role in rows:
        items.append({
            "id": str(user.id),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "full_name": user.full_name or f"{user.first_name} {user.last_name}",
            "role": role,
            "is_active": user.is_active,
            "status": getattr(user.status, "value", str(user.status)),
            "created_at": user.created_at.isoformat() if user.created_at else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.post("/invite", status_code=status.HTTP_201_CREATED)
async def invite_user(
    body: InviteUserRequest,
    current_user: CurrentUser,
    db: TenantDB,
    _: None = Depends(require_min_role("admin")),
):
    """
    Invite a user and grant them an explicit RBAC role in this organization.
    Restricted to Owner and Admin only.
    """
    allowed_roles = [r.value for r in OrganizationMemberRole]
    if body.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{body.role}'. Must be one of: {allowed_roles}"
        )

    from packages.billing.plan_limits import PlanLimitEnforcer
    await PlanLimitEnforcer.check_seat_limit(db, current_user.org_id)

    # Check if user already exists
    user_res = await db.execute(select(User).where(User.email == body.email.lower()))
    user = user_res.scalar_one_or_none()

    if not user:
        user = User(
            email=body.email.lower(),
            first_name=body.first_name or "Invited",
            last_name=body.last_name or "User",
            full_name=f"{body.first_name or 'Invited'} {body.last_name or 'User'}",
            organization_id=current_user.org_id,
            is_active=True,
            is_verified=False,
            status=UserStatus.PENDING,
            provider=AuthenticationProvider.EMAIL,
        )
        db.add(user)
        await db.flush()

    # Check if membership already exists in this org
    mem_res = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == current_user.org_id,
            OrganizationMember.user_id == user.id,
        )
    )
    existing_member = mem_res.scalar_one_or_none()
    if existing_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this organization."
        )

    membership = OrganizationMember(
        organization_id=current_user.org_id,
        user_id=user.id,
        role=body.role,
    )
    db.add(membership)

    from packages.security.audit import log_audit_event
    from packages.database.models.audit import AuditEventType
    await log_audit_event(
        db=db,
        organization_id=current_user.org_id,
        user_id=current_user.user_id,
        event_type=AuditEventType.USER_ROLE_ASSIGN,
        event_name="User Invited",
        description=f"User {body.email} invited with role '{body.role}'",
        user_email=current_user.email,
        user_role=current_user.role,
        resource_type="OrganizationMember",
        resource_id=str(user.id),
        action_data={"invited_email": body.email, "role": body.role},
    )
    await db.commit()

    return {
        "message": f"User {body.email} successfully invited with role '{body.role}'.",
        "user_id": str(user.id),
        "organization_id": str(current_user.org_id),
        "role": body.role,
    }


@router.patch("/{user_id}/role")
async def change_user_role(
    user_id: UUID,
    body: ChangeRoleRequest,
    current_user: CurrentUser,
    db: TenantDB,
    _: None = Depends(require_min_role("admin")),
):
    """
    Change a member's RBAC role in this organization.
    Restricted to Owner and Admin only.
    Guards against demoting or removing the last remaining Owner.
    """
    allowed_roles = [r.value for r in OrganizationMemberRole]
    if body.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{body.role}'. Must be one of: {allowed_roles}"
        )

    mem_res = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == current_user.org_id,
            OrganizationMember.user_id == user_id,
        )
    )
    membership = mem_res.scalar_one_or_none()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User membership not found in this organization."
        )

    # Guard: Cannot demote the last owner
    if membership.role == "owner" and body.role != "owner":
        owners_count_res = await db.execute(
            select(func.count(OrganizationMember.id)).where(
                OrganizationMember.organization_id == current_user.org_id,
                OrganizationMember.role == "owner",
            )
        )
        owner_count = owners_count_res.scalar() or 0
        if owner_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote the last remaining owner of the organization."
            )

    old_role = membership.role
    membership.role = body.role

    from packages.security.audit import log_audit_event
    from packages.database.models.audit import AuditEvent, AuditEventType
    await log_audit_event(
        db=db,
        organization_id=current_user.org_id,
        user_id=current_user.user_id,
        event_type=AuditEventType.USER_ROLE_ASSIGN,
        event_name="Member Role Changed",
        description=f"Member {user_id} role updated from '{old_role}' to '{body.role}'",
        user_email=current_user.email,
        user_role=current_user.role,
        resource_type="OrganizationMember",
        resource_id=str(user_id),
        action_data={"old_role": old_role, "new_role": body.role},
    )
    await db.commit()

    return {
        "message": "Role successfully updated.",
        "user_id": str(user_id),
        "role": body.role,
    }


# ------------------------------------------------------------------------------
# GDPR Compliance Endpoints (Articles 17 & 20)
# ------------------------------------------------------------------------------

@router.get("/me/export")
async def export_my_data(
    current_user: CurrentUser,
    db: TenantDB,
):
    """GDPR Article 20: Right to data portability - export all user personal and organizational records."""
    user_res = await db.execute(select(User).where(User.id == current_user.user_id))
    user = user_res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    mem_res = await db.execute(
        select(OrganizationMember).where(OrganizationMember.user_id == current_user.user_id)
    )
    memberships = [
        {
            "organization_id": str(m.organization_id),
            "role": m.role,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in mem_res.scalars().all()
    ]

    audit_res = await db.execute(
        select(AuditEvent).where(AuditEvent.user_id == current_user.user_id).order_by(AuditEvent.event_time.desc()).limit(100)
    )
    audit_logs = [
        {
            "event_type": str(a.event_type),
            "event_name": a.event_name,
            "description": a.description,
            "event_time": a.event_time.isoformat() if a.event_time else None,
            "result": a.result,
        }
        for a in audit_res.scalars().all()
    ]

    return {
        "personal_data": {
            "id": str(user.id),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "full_name": user.full_name,
            "is_verified": user.is_verified,
            "status": getattr(user.status, "value", str(user.status)),
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        "organization_memberships": memberships,
        "recent_audit_history": audit_logs,
        "export_timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.delete("/me", status_code=status.HTTP_200_OK)
async def delete_my_account(
    current_user: CurrentUser,
    db: TenantDB,
):
    """GDPR Article 17: Right to be forgotten - anonymize and deactivate user account."""
    user_res = await db.execute(select(User).where(User.id == current_user.user_id))
    user = user_res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Guard: Check if user is sole owner of any organization
    mem_res = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.user_id == current_user.user_id,
            OrganizationMember.role == "owner",
        )
    )
    owner_memberships = mem_res.scalars().all()
    for om in owner_memberships:
        owners_count_res = await db.execute(
            select(func.count(OrganizationMember.id)).where(
                OrganizationMember.organization_id == om.organization_id,
                OrganizationMember.role == "owner",
            )
        )
        if (owners_count_res.scalar() or 0) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete account while you are the sole owner of organization {om.organization_id}. Transfer ownership or delete the organization first."
            )

    from packages.security.audit import log_audit_event
    from packages.database.models.audit import AuditEventType
    await log_audit_event(
        db=db,
        organization_id=current_user.org_id,
        user_id=current_user.user_id,
        event_type=AuditEventType.USER_DELETE,
        event_name="GDPR Account Deletion",
        description="User requested self-deletion and PII anonymization",
        user_email=current_user.email,
        user_role=current_user.role,
        resource_type="User",
        resource_id=str(user.id),
    )

    # Anonymize PII
    anonymized_id = str(user.id)[:8]
    user.email = f"anonymized_{anonymized_id}@deleted.local"
    user.first_name = "Anonymized"
    user.last_name = "User"
    user.full_name = "Anonymized User"
    user.is_active = False
    user.status = UserStatus.INACTIVE
    user.password_hash = "DELETED"

    await db.commit()
    return {"message": "Account has been successfully deactivated and personal data anonymized under GDPR Article 17."}


@router.get("/{user_id}")
async def get_user(
    user_id: UUID,
    current_user: CurrentUser,
    db: TenantDB,
):
    """Get member details by ID in the current organization."""
    query = (
        select(User, OrganizationMember.role)
        .join(OrganizationMember, User.id == OrganizationMember.user_id)
        .where(
            OrganizationMember.organization_id == current_user.org_id,
            User.id == user_id,
        )
    )
    res = await db.execute(query)
    row = res.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user, role = row
    return {
        "id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": user.full_name,
        "role": role,
        "is_active": user.is_active,
        "status": getattr(user.status, "value", str(user.status)),
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user_from_org(
    user_id: UUID,
    current_user: CurrentUser,
    db: TenantDB,
    _: None = Depends(require_min_role("admin")),
):
    """
    Remove a member from the organization.
    Restricted to Owner and Admin only.
    Guards against removing the last remaining Owner.
    """
    mem_res = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == current_user.org_id,
            OrganizationMember.user_id == user_id,
        )
    )
    membership = mem_res.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    if membership.role == "owner":
        owners_count_res = await db.execute(
            select(func.count(OrganizationMember.id)).where(
                OrganizationMember.organization_id == current_user.org_id,
                OrganizationMember.role == "owner",
            )
        )
        if (owners_count_res.scalar() or 0) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the last remaining owner of the organization."
            )

    from packages.security.audit import log_audit_event
    from packages.database.models.audit import AuditEventType
    await log_audit_event(
        db=db,
        organization_id=current_user.org_id,
        user_id=current_user.user_id,
        event_type=AuditEventType.USER_ROLE_REMOVE,
        event_name="Member Removed",
        description=f"Member {user_id} removed from organization",
        user_email=current_user.email,
        user_role=current_user.role,
        resource_type="OrganizationMember",
        resource_id=str(user_id),
        action_data={"removed_user_id": str(user_id)},
    )

    await db.delete(membership)
    await db.commit()
    return None
