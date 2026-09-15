"""User routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, or_
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from packages.database import get_db
from packages.database.models import User, UserRole, UserRoleAssignment
from ..schemas.user import UserCreate, UserUpdate, UserResponse, UserRoleResponse, PaginationParams
from ..schemas.base import PaginatedResponse
from packages.security.auth import get_current_user, require_permissions

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=PaginatedResponse[UserResponse])
async def list_users(
    page: int = 1,
    page_size: int = 20,
    organization_id: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List users.

    Args:
        page: Page number
        page_size: Items per page
        organization_id: Filter by organization
        search: Search term
        db: Database session
        current_user: Current authenticated user

    Returns:
        PaginatedResponse: Paginated list of users
    """
    # Build query
    query = select(User).where(User.is_active == True)

    # Filter by organization
    if organization_id:
        query = query.where(User.organization_id == UUID(organization_id))

    # Search
    if search:
        query = query.where(
            (User.first_name.ilike(f"%{search}%")) |
            (User.last_name.ilike(f"%{search}%")) |
            (User.email.ilike(f"%{search}%"))
        )

    # Get total count
    count_query = select(func.count(User.id)).where(User.is_active == True)
    if organization_id:
        count_query = count_query.where(User.organization_id == UUID(organization_id))
    if search:
        count_query = count_query.where(
            (User.first_name.ilike(f"%{search}%")) |
            (User.last_name.ilike(f"%{search}%")) |
            (User.email.ilike(f"%{search}%"))
        )

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

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


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get user by ID.

    Args:
        user_id: User ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        UserResponse: User information

    Raises:
        HTTPException: If user not found
    """
    result = await db.execute(
        select(User).where(User.id == UUID(user_id))
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update user.

    Args:
        user_id: User ID
        user_data: Updated user data
        db: Database session
        current_user: Current authenticated user

    Returns:
        UserResponse: Updated user

    Raises:
        HTTPException: If user not found or update fails
    """
    result = await db.execute(
        select(User).where(User.id == UUID(user_id))
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Update fields
    update_data = user_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    # Update timestamp
    user.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(user)

    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete user.

    Args:
        user_id: User ID
        db: Database session
        current_user: Current authenticated user

    Raises:
        HTTPException: If user not found or deletion fails
    """
    result = await db.execute(
        select(User).where(User.id == UUID(user_id))
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Soft delete
    user.is_active = False
    user.status = "deleted"
    user.deleted_at = datetime.utcnow()
    await db.commit()

    return None


@router.get("/{user_id}/roles", response_model=List[UserRoleResponse])
async def get_user_roles(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get user roles.

    Args:
        user_id: User ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        List[UserRoleResponse]: User roles
    """
    # Get role assignments
    result = await db.execute(
        select(UserRoleAssignment)
        .where(UserRoleAssignment.user_id == UUID(user_id))
    )
    assignments = result.scalars().all()

    # Get roles
    roles = []
    for assignment in assignments:
        if assignment.role:
            roles.append(UserRoleResponse(
                id=assignment.role.id,
                name=assignment.role.name,
                slug=assignment.role.slug,
                description=assignment.role.description,
                display_name=assignment.role.display_name,
                role_type=assignment.role.role_type,
                can_view_dashboard=assignment.role.can_view_dashboard,
                can_access_settings=assignment.role.can_access_settings,
                can_manage_users=assignment.role.can_manage_users,
                can_manage_agents=assignment.role.can_manage_agents,
                can_execute_actions=assignment.role.can_execute_actions,
                can_approve_actions=assignment.role.can_approve_actions,
                can_access_financial_data=assignment.role.can_access_financial_data,
                can_approve_financial_actions=assignment.role.can_approve_financial_actions,
                can_access_inventory_data=assignment.role.can_access_inventory_data,
                can_manage_inventory=assignment.role.can_manage_inventory,
                can_access_procurement=assignment.role.can_access_procurement,
                can_manage_procurement=assignment.role.can_manage_procurement,
                can_access_sales_data=assignment.role.can_access_sales_data,
                can_manage_sales=assignment.role.can_manage_sales,
                can_access_operations=assignment.role.can_access_operations,
                can_manage_operations=assignment.role.can_manage_operations,
            ))

    return roles


@router.post("/{user_id}/roles", status_code=status.HTTP_201_CREATED)
async def assign_role(
    user_id: str,
    role_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Assign role to user.

    Args:
        user_id: User ID
        role_id: Role ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        dict: Success message
    """
    # Check if role exists
    result = await db.execute(
        select(UserRole).where(UserRole.id == UUID(role_id))
    )
    role = result.scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    # Check if assignment already exists
    result = await db.execute(
        select(UserRoleAssignment).where(
            UserRoleAssignment.user_id == UUID(user_id),
            UserRoleAssignment.role_id == UUID(role_id),
            UserRoleAssignment.scope == "organization"
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role already assigned to user"
        )

    # Create assignment
    assignment = UserRoleAssignment(
        user_id=UUID(user_id),
        role_id=UUID(role_id),
        scope="organization"
    )

    db.add(assignment)
    await db.commit()

    return {"message": "Role assigned successfully"}


@router.delete("/{user_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_role(
    user_id: str,
    role_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove role from user.

    Args:
        user_id: User ID
        role_id: Role ID
        db: Database session
        current_user: Current authenticated user

    Raises:
        HTTPException: If removal fails
    """
    # Delete assignment
    result = await db.execute(
        select(UserRoleAssignment).where(
            UserRoleAssignment.user_id == UUID(user_id),
            UserRoleAssignment.role_id == UUID(role_id)
        )
    )
    assignment = result.scalar_one_or_none()

    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role assignment not found"
        )

    await db.delete(assignment)
    await db.commit()

    return None
