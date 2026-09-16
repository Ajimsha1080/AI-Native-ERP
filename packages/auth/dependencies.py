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

from typing import Annotated, List
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from pydantic import BaseModel

from packages.auth.tokens import decode_token, TokenPayload

# Role ordering for hierarchy checks (index = rank, higher = more privileged)
ROLE_HIERARCHY = ["viewer", "manager", "admin", "owner"]

_bearer = HTTPBearer(auto_error=True)


class UserTokenPayload(BaseModel):
    """
    Decoded, validated user identity extracted from the JWT.

    Available in every authenticated route via the `CurrentUser` dependency.
    """
    user_id: UUID
    org_id: UUID
    role: str


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

    return UserTokenPayload(
        user_id=UUID(payload.sub),
        org_id=UUID(payload.org_id),
        role=payload.role,
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
