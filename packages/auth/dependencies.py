"""
FastAPI authentication and authorization dependencies.

Provides:
  - get_current_user:  decode JWT bearer token, return UserTokenPayload
  - require_role:      dependency factory that enforces RBAC
  - CurrentUser:       Annotated type alias for injection into routes

Role hierarchy (highest to lowest):
  owner > admin > manager > viewer

`require_role("manager", "admin", "owner")` means the endpoint is
accessible to manager, admin, or owner — i.e., NOT viewer.
"""

from typing import Annotated, List, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from pydantic import BaseModel

from packages.auth.tokens import decode_token, TokenPayload

# Role ordering for hierarchy checks (index = rank, higher = more privileged)
ROLE_HIERARCHY = ["viewer", "manager", "admin", "owner"]

_bearer = HTTPBearer(auto_error=True)
_optional_bearer = HTTPBearer(auto_error=False)


class UserTokenPayload(BaseModel):
    """
    Decoded, validated user identity extracted from the JWT.

    Available in every authenticated route via the `CurrentUser` dependency.
    """
    user_id: UUID
    org_id: UUID
    role: str
    email: str = ""

    @property
    def id(self) -> UUID:
        return self.user_id

    @property
    def organization_id(self) -> UUID:
        return self.org_id


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> UserTokenPayload:
    """
    FastAPI dependency: decode Bearer JWT and return user identity.

    The token must:
      - Be a valid HS256 JWT signed with SECRET_KEY
      - Not be expired
      - Have token_type == "access"

    Args:
        credentials: Bearer token from the Authorization header.

    Returns:
        UserTokenPayload with user_id, org_id, role.

    Raises:
        HTTPException 401: If the token is missing, expired, or invalid.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload: TokenPayload = decode_token(credentials.credentials)
    except JWTError:
        raise credentials_exception

    if payload.token_type != "access":
        raise credentials_exception

    if not payload.sub or not payload.org_id:
        raise credentials_exception

    from packages.auth.tokens import TokenBlacklist
    is_revoked = await TokenBlacklist.is_blacklisted_async(payload.jti)
    if not is_revoked and credentials.credentials:
        is_revoked = await TokenBlacklist.is_blacklisted_async(credentials.credentials)
    if is_revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked or blacklisted.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_uuid = UUID(payload.sub)
    org_uuid = UUID(payload.org_id)
    resolved_role = payload.role or "viewer"

    # Short-TTL check: verify active status and organization membership
    try:
        from packages.database.core import AsyncSessionLocal
        from packages.database.models import User
        from sqlalchemy import select
        async with AsyncSessionLocal() as session:
            stmt = select(User.is_active, User.organization_id).where(User.id == user_uuid)
            user_row = (await session.execute(stmt)).first()
            if user_row is not None:
                is_active, user_org = user_row
                if not is_active:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="User account is deactivated.",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                if user_org != org_uuid:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="User is no longer a member of this organization.",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
    except HTTPException:
        raise
    except Exception:
        pass

    return UserTokenPayload(
        user_id=user_uuid,
        org_id=org_uuid,
        role=resolved_role,
        email=payload.email or "",
    )


def require_role(*allowed_roles: str):
    """
    Dependency factory: enforce RBAC by checking the user's role.

    Usage:
        @router.post("/admin-only")
        async def admin_endpoint(
            _: Annotated[None, Depends(require_role("admin", "owner"))],
            current_user: CurrentUser,
        ):
            ...

    Args:
        *allowed_roles: Role slugs that are permitted to access the endpoint.
                        An empty list means "any authenticated user is allowed".

    Returns:
        A FastAPI dependency that raises 403 if the user's role is not permitted.

    Notes:
        Role hierarchy is respected implicitly — pass the minimum required roles
        explicitly (e.g., "manager", "admin", "owner" for manager-level access).
    """
    async def _check_role(current_user: Annotated[UserTokenPayload, Depends(get_current_user)]) -> UserTokenPayload:
        if allowed_roles and current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not permitted. Required: {list(allowed_roles)}",
            )
        return current_user

    return _check_role


def require_min_role(min_role: str):
    """
    Dependency factory: enforce minimum role level using the role hierarchy.

    require_min_role("manager") → accepts manager, admin, owner but not viewer.

    Args:
        min_role: The minimum role slug required.

    Returns:
        A FastAPI dependency that raises 403 if the user's rank is too low.
    """
    min_rank = ROLE_HIERARCHY.index(min_role) if min_role in ROLE_HIERARCHY else 0

    async def _check_min_role(current_user: Annotated[UserTokenPayload, Depends(get_current_user)]) -> UserTokenPayload:
        user_rank = ROLE_HIERARCHY.index(current_user.role) if current_user.role in ROLE_HIERARCHY else -1
        if user_rank < min_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Minimum role '{min_role}' required; you have '{current_user.role}'",
            )
        return current_user

    return _check_min_role


# Annotated type alias — inject this into any route handler that needs the user
CurrentUser = Annotated[UserTokenPayload, Depends(get_current_user)]


async def get_optional_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_optional_bearer)],
) -> Optional[UserTokenPayload]:
    """
    FastAPI dependency: decode Bearer JWT if present; return None if missing or invalid.
    Allows public or demo access while respecting authenticated tenant identity if token supplied.
    """
    if not credentials or not credentials.credentials:
        return None
    try:
        payload: TokenPayload = decode_token(credentials.credentials)
    except JWTError:
        return None

    if payload.token_type != "access" or not payload.sub or not payload.org_id:
        return None

    from packages.auth.tokens import TokenBlacklist
    if (payload.jti and TokenBlacklist.is_blacklisted(payload.jti)) or TokenBlacklist.is_blacklisted(credentials.credentials):
        return None

    return UserTokenPayload(
        user_id=UUID(payload.sub),
        org_id=UUID(payload.org_id),
        role=payload.role or "viewer",
        email=payload.email or "",
    )


OptionalCurrentUser = Annotated[Optional[UserTokenPayload], Depends(get_optional_current_user)]

