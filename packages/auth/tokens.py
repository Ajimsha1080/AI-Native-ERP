"""
JWT token creation, validation, rotation, and revocation.

Hardened Enterprise Token Management:
  - Access token: short-lived (15-30 min), carries sub, org_id, role, jti
  - Refresh token: long-lived, carries sub, jti, family_id for true rotation and reuse detection
  - Token blacklist: async Redis backed with thread-safe in-memory fallback
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Set
from uuid import UUID

from jose import JWTError, jwt
from pydantic import BaseModel, Field

from packages.config.settings import settings


class TokenPayload(BaseModel):
    """Decoded JWT claims."""
    sub: str                              # user_id (UUID string)
    org_id: Optional[str] = ""            # organization_id (UUID string)
    role: Optional[str] = ""              # user role slug
    email: Optional[str] = ""             # user email
    token_type: str                       # "access", "refresh", "verify_email", "reset_password"
    exp: int                              # Unix expiry timestamp
    jti: Optional[str] = None             # Unique Token ID for revocation
    family_id: Optional[str] = None       # Refresh token family ID for reuse detection


class TokenBlacklist:
    """Enterprise Token Revocation & Blacklist Engine with Shared Async Redis Pool."""
    _memory_blacklist: Set[str] = set()
    _redis_pool = None

    @classmethod
    def _get_redis_pool(cls):
        if cls._redis_pool is None:
            import redis.asyncio as aioredis
            cls._redis_pool = aioredis.ConnectionPool.from_url(
                settings.redis_url,
                socket_connect_timeout=0.5,
                max_connections=50,
                decode_responses=True
            )
        return cls._redis_pool

    @classmethod
    async def is_blacklisted_async(cls, jti_or_token: str) -> bool:
        if not jti_or_token:
            return False

        # In test environments, check in-memory set first
        is_test = settings.environment.lower() in ("test", "testing")
        if is_test and jti_or_token in cls._memory_blacklist:
            return True

        try:
            import redis.asyncio as aioredis
            pool = cls._get_redis_pool()
            r = aioredis.Redis(connection_pool=pool)
            val = await r.exists(f"token_bl:{jti_or_token}")
            return bool(val)
        except Exception as e:
            # Outside of test environment, fail closed (raise 503)
            if not is_test:
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Security Service Unavailable: Unable to reach token revocation service (failing closed)."
                ) from e
            return jti_or_token in cls._memory_blacklist

    @classmethod
    async def blacklist_async(cls, jti_or_token: str, ttl_seconds: int = 86400) -> None:
        if not jti_or_token:
            return
        cls._memory_blacklist.add(jti_or_token)
        try:
            import redis.asyncio as aioredis
            pool = cls._get_redis_pool()
            r = aioredis.Redis(connection_pool=pool)
            await r.set(f"token_bl:{jti_or_token}", "1", ex=ttl_seconds)
        except Exception:
            pass

    @classmethod
    def is_blacklisted(cls, jti_or_token: str) -> bool:
        """Sync fallback check for compatibility."""
        if not jti_or_token:
            return False
        if jti_or_token in cls._memory_blacklist:
            return True
        try:
            import redis
            r = redis.from_url(settings.redis_url, socket_connect_timeout=0.2)
            return bool(r.exists(f"token_bl:{jti_or_token}"))
        except Exception:
            if settings.environment.lower() not in ("test", "testing"):
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Security Service Unavailable: Unable to reach token revocation service (failing closed)."
                )
            return jti_or_token in cls._memory_blacklist

    @classmethod
    def blacklist(cls, jti_or_token: str, ttl_seconds: int = 86400) -> None:
        if not jti_or_token:
            return
        cls._memory_blacklist.add(jti_or_token)
        try:
            import redis
            r = redis.from_url(settings.redis_url, socket_connect_timeout=0.2)
            r.set(f"token_bl:{jti_or_token}", "1", ex=ttl_seconds)
        except Exception:
            pass


def create_access_token(
    user_id: UUID,
    org_id: UUID,
    role: str,
    email: Optional[str] = None,
    jti: Optional[str] = None,
    ttl_minutes: Optional[int] = None,
) -> str:
    """
    Create a short-lived JWT access token with unique JTI.
    """
    minutes = ttl_minutes or settings.access_token_expire_minutes or 15
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {
        "sub": str(user_id),
        "org_id": str(org_id),
        "role": role,
        "email": email or "",
        "token_type": "access",
        "jti": jti or str(uuid.uuid4()),
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(
    user_id: UUID,
    family_id: Optional[UUID] = None,
    jti: Optional[str] = None,
) -> tuple[str, str, UUID]:
    """
    Create a long-lived JWT refresh token with unique JTI and Family ID.

    Returns:
        tuple[token_string, jti_string, family_id_uuid]
    """
    token_jti = jti or str(uuid.uuid4())
    token_family = family_id or uuid.uuid4()
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    payload = {
        "sub": str(user_id),
        "org_id": "",
        "role": "",
        "token_type": "refresh",
        "jti": token_jti,
        "family_id": str(token_family),
        "exp": expire,
    }
    token_str = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    return token_str, token_jti, token_family


def create_email_token(user_id: UUID, purpose: str, ttl_hours: int = 24) -> str:
    """
    Create a short-lived token for email verification or password reset.
    """
    expire = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
    token_jti = str(uuid.uuid4())
    payload = {
        "sub": str(user_id),
        "org_id": "",
        "role": "",
        "token_type": purpose,
        "jti": token_jti,
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> TokenPayload:
    """
    Decode and validate a JWT token, checking expiration and signature.
    """
    raw = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    return TokenPayload(**raw)
