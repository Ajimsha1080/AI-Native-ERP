"""Organization routes with tenant isolation and RBAC."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Optional
from uuid import UUID

from packages.database.models import Organization, Workspace, BusinessUnit, Team, User
from packages.database.tenant_context import TenantDB
from packages.auth.dependencies import CurrentUser, require_min_role
from ..schemas.user import UserResponse, UserRoleResponse
from ..schemas.base import PaginatedResponse
from ..schemas.organization import OrganizationResponse, WorkspaceResponse, BusinessUnitResponse, TeamResponse

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.get("", response_model=List[OrganizationResponse])
async def list_organizations(
    db: AsyncSession = Depends(TenantDB),
    current_user: User = Depends(CurrentUser)
):
    """List current user's organization."""
    if current_user.organization_id:
        result = await db.execute(
            select(Organization).where(Organization.id == current_user.organization_id)
        )
        organizations = result.scalars().all()
    else:
        organizations = []
    return organizations


@router.get("/{organization_id}", response_model=OrganizationResponse)
async def get_organization(
    organization_id: str,
    db: AsyncSession = Depends(TenantDB),
    current_user: User = Depends(CurrentUser)
):
    """Get organization by ID."""
    try:
        org_uuid = UUID(organization_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization UUID")

    if current_user.organization_id and org_uuid != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this organization"
        )

    result = await db.execute(
        select(Organization).where(Organization.id == org_uuid)
    )
    organization = result.scalar_one_or_none()

    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    return organization


@router.get("/{organization_id}/workspaces", response_model=List[WorkspaceResponse])
async def get_organization_workspaces(
    organization_id: str,
    db: AsyncSession = Depends(TenantDB),
    current_user: User = Depends(CurrentUser)
):
    """Get organization workspaces."""
    try:
        org_uuid = UUID(organization_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization UUID")

    if current_user.organization_id and org_uuid != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Access denied to this organization")

    result = await db.execute(
        select(Workspace).where(Workspace.organization_id == org_uuid)
    )
    return result.scalars().all()


@router.get("/{organization_id}/business-units", response_model=List[BusinessUnitResponse])
async def get_organization_business_units(
    organization_id: str,
    db: AsyncSession = Depends(TenantDB),
    current_user: User = Depends(CurrentUser)
):
    """Get organization business units."""
    try:
        org_uuid = UUID(organization_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization UUID")

    if current_user.organization_id and org_uuid != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Access denied to this organization")

    result = await db.execute(
        select(BusinessUnit).where(BusinessUnit.organization_id == org_uuid)
    )
    return result.scalars().all()


@router.get("/{organization_id}/teams", response_model=List[TeamResponse])
async def get_organization_teams(
    organization_id: str,
    db: AsyncSession = Depends(TenantDB),
    current_user: User = Depends(CurrentUser)
):
    """Get organization teams."""
    try:
        org_uuid = UUID(organization_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization UUID")

    if current_user.organization_id and org_uuid != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Access denied to this organization")

    result = await db.execute(
        select(Team).where(Team.organization_id == org_uuid)
    )
    return result.scalars().all()


@router.get("/{organization_id}/users", response_model=PaginatedResponse[UserResponse])
async def get_organization_users(
    organization_id: str,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(TenantDB),
    current_user: User = Depends(CurrentUser)
):
    """Get organization users."""
    try:
        org_uuid = UUID(organization_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization UUID")

    if current_user.organization_id and org_uuid != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Access denied to this organization")

    query = select(User).where(User.organization_id == org_uuid)
    count_query = select(User).where(User.organization_id == org_uuid)
    total_result = await db.execute(count_query)
    total = len(total_result.all())

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    users = result.scalars().all()

    return {
        "items": users,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 1
    }


# ------------------------------------------------------------------------------
# GDPR Tenant Export & Deletion Endpoints
# ------------------------------------------------------------------------------

@router.get("/{organization_id}/export")
async def export_organization_data(
    organization_id: str,
    current_user: CurrentUser,
    db: TenantDB,
    _: None = Depends(require_min_role("admin")),
):
    """GDPR Article 20: Export full tenant data schema for compliance and data portability."""
    try:
        org_uuid = UUID(organization_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization UUID")

    if current_user.org_id and org_uuid != current_user.org_id:
        raise HTTPException(status_code=403, detail="Access denied to this organization")

    org_res = await db.execute(select(Organization).where(Organization.id == org_uuid))
    organization = org_res.scalar_one_or_none()
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    ws_res = await db.execute(select(Workspace).where(Workspace.organization_id == org_uuid))
    workspaces = [{"id": str(w.id), "name": w.name} for w in ws_res.scalars().all()]

    bu_res = await db.execute(select(BusinessUnit).where(BusinessUnit.organization_id == org_uuid))
    business_units = [{"id": str(b.id), "name": b.name} for b in bu_res.scalars().all()]

    team_res = await db.execute(select(Team).where(Team.organization_id == org_uuid))
    teams = [{"id": str(t.id), "name": t.name} for t in team_res.scalars().all()]

    from datetime import datetime, timezone
    return {
        "organization": {
            "id": str(organization.id),
            "name": organization.name,
            "slug": organization.slug,
            "plan": organization.plan,
            "status": organization.status,
            "created_at": organization.created_at.isoformat() if organization.created_at else None,
        },
        "workspaces": workspaces,
        "business_units": business_units,
        "teams": teams,
        "export_timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.delete("/{organization_id}", status_code=status.HTTP_200_OK)
async def delete_organization(
    organization_id: str,
    current_user: CurrentUser,
    db: TenantDB,
    _: None = Depends(require_min_role("owner")),
):
    """GDPR / Tenant Offboarding: Deactivate organization and revoke access. Owner only."""
    try:
        org_uuid = UUID(organization_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization UUID")

    if current_user.org_id and org_uuid != current_user.org_id:
        raise HTTPException(status_code=403, detail="Access denied to this organization")

    org_res = await db.execute(select(Organization).where(Organization.id == org_uuid))
    organization = org_res.scalar_one_or_none()
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    organization.status = "suspended"

    from packages.security.audit import log_audit_event
    from packages.database.models.audit import AuditEventType
    await log_audit_event(
        db=db,
        organization_id=org_uuid,
        user_id=current_user.user_id,
        event_type=AuditEventType.SETTINGS_UPDATE,
        event_name="Organization Deactivated",
        description=f"Organization {organization.name} was deactivated by owner under tenant termination / GDPR request",
        user_email=current_user.email,
        user_role="owner",
        resource_type="Organization",
        resource_id=str(org_uuid),
    )

    await db.commit()
    return {"message": f"Organization '{organization.name}' has been deactivated successfully."}
