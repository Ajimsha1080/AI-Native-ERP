"""
JWT token creation and validation.

Two token types:
  - Access token:  short-lived (30 min), carries sub/org_id/role
  - Refresh token: long-lived (7 days), carries only sub for rotation

HS256 is used for simplicity. For RS256 (asymmetric, suitable for
multi-service setups), swap the algorithm and provide public/private keys.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from jose import JWTError, jwt
from pydantic import BaseModel

from packages.config.settings import settings


class TokenPayload(BaseModel):
    """Decoded JWT claims."""
    sub: str          # user_id (UUID string)
    org_id: str       # organization_id (UUID string)
    role: str         # user role slug
    token_type: str   # "access" or "refresh"
    exp: int          # Unix expiry timestamp


def create_access_token(
    user_id: UUID,
    org_id: UUID,
    role: str,
) -> str:
    """
    Create a short-lived JWT access token.

    The token carries the user's id, organisation id, and role.
    These three fields are embedded so that every authenticated route can
    perform RBAC and tenant-scoping without an extra DB lookup.

    Args:
        user_id: The authenticated user's UUID.
        org_id: The organisation the user belongs to.
        role: The user's effective role slug (e.g., "owner", "viewer").

    Returns:
        Signed JWT string.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": str(user_id),
        "org_id": str(org_id),
        "role": role,
        "token_type": "access",
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(user_id: UUID) -> str:
    """
    Create a long-lived JWT refresh token.

    Refresh tokens carry only the user id — no org/role — so that
    a stolen refresh token cannot directly authorise API calls.
    The access token must be re-issued via the /auth/refresh endpoint,
    which re-reads the role from the database.

    Args:
        user_id: The authenticated user's UUID.

    Returns:
        Signed JWT string.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    payload = {
        "sub": str(user_id),
        "org_id": "",          # not present in refresh tokens
        "role": "",            # not present in refresh tokens
        "token_type": "refresh",
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_email_token(user_id: UUID, purpose: str, ttl_hours: int = 24) -> str:
    """
    Create a short-lived token for email verification or password reset.

    Args:
        user_id: User UUID the token belongs to.
        purpose: "verify_email" or "reset_password"
        ttl_hours: How long the token is valid.

    Returns:
        Signed JWT string.
    """
    expire = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
    payload = {
        "sub": str(user_id),
        "org_id": "",
        "role": "",
        "token_type": purpose,
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> TokenPayload:
    """
    Decode and validate a JWT token.

    Args:
        token: Raw JWT string from the Authorization header.

    Returns:
        TokenPayload with decoded claims.

    Raises:
        JWTError: If the token is expired, malformed, or the signature is invalid.
    """
    raw = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    return TokenPayload(**raw)
