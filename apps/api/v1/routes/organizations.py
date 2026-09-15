"""Organization routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Optional
from uuid import UUID

from packages.database import get_db
from packages.database.models import Organization, Workspace, BusinessUnit, Team, User
from packages.security.auth import get_current_user
from ..schemas.user import UserResponse, UserRoleResponse
from ..schemas.base import PaginatedResponse
from ..schemas.organization import OrganizationResponse, WorkspaceResponse, BusinessUnitResponse, TeamResponse

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.get("", response_model=List[OrganizationResponse])
async def list_organizations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List user's organizations.

    Args:
        db: Database session
        current_user: Current authenticated user

    Returns:
        List[OrganizationResponse]: List of organizations
    """
    # Get organizations user belongs to
    result = await db.execute(
        select(Organization).where(
            Organization.tenant_id == current_user.organization_id
        )
    )
    organizations = result.scalars().all()
    return organizations


@router.get("/{organization_id}", response_model=OrganizationResponse)
async def get_organization(
    organization_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get organization by ID.

    Args:
        organization_id: Organization ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Organization: Organization information

    Raises:
        HTTPException: If organization not found
    """
    result = await db.execute(
        select(Organization).where(Organization.id == UUID(organization_id))
    )
    organization = result.scalar_one_or_none()

    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    # Check if user has access to this organization
    if organization.tenant_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this organization"
        )

    return organization


@router.get("/{organization_id}/workspaces", response_model=List[WorkspaceResponse])
async def get_organization_workspaces(
    organization_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get organization workspaces.

    Args:
        organization_id: Organization ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        List[Workspace]: List of workspaces
    """
    result = await db.execute(
        select(Workspace).where(Workspace.organization_id == UUID(organization_id))
    )
    workspaces = result.scalars().all()

    return workspaces


@router.get("/{organization_id}/business-units", response_model=List[BusinessUnitResponse])
async def get_organization_business_units(
    organization_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get organization business units.

    Args:
        organization_id: Organization ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        List[BusinessUnit]: List of business units
    """
    result = await db.execute(
        select(BusinessUnit).where(BusinessUnit.organization_id == UUID(organization_id))
    )
    business_units = result.scalars().all()

    return business_units


@router.get("/{organization_id}/teams", response_model=List[TeamResponse])
async def get_organization_teams(
    organization_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get organization teams.

    Args:
        organization_id: Organization ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        List[Team]: List of teams
    """
    result = await db.execute(
        select(Team).where(Team.organization_id == UUID(organization_id))
    )
    teams = result.scalars().all()

    return teams


@router.get("/{organization_id}/users", response_model=PaginatedResponse[UserResponse])
async def get_organization_users(
    organization_id: str,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get organization users.

    Args:
        organization_id: Organization ID
        page: Page number
        page_size: Items per page
        db: Database session
        current_user: Current authenticated user

    Returns:
        PaginatedResponse: Paginated list of users
    """
    # Build query
    query = select(User).where(User.organization_id == UUID(organization_id))

    # Get total count
    count_query = select(User).where(User.organization_id == UUID(organization_id))
    total_result = await db.execute(count_query)
    total = len(total_result.all())

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Execute
    result = await db.execute(query)
    users = result.scalars().all()

    return {
        "items": users,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }
