"""
Security middleware.

Provides security-related middleware for the application.
"""

import uuid
import logging
from typing import Optional, Set
from fastapi import Request, Response, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt

from packages.config import get_settings
from packages.database import get_db
from packages.database.models import User
from packages.security.auth import get_current_user

settings = get_settings()
logger = logging.getLogger("security")

# Rate limiting
limiter = Limiter(key_func=get_remote_address)


class TokenBlacklistStore:
    """Distributed or in-memory token blacklist store."""
    _memory_blacklist: Set[str] = set()

    @classmethod
    def is_blacklisted(cls, token: str) -> bool:
        if not token:
            return False
        # Check in-memory set
        if token in cls._memory_blacklist:
            return True
        # Try Redis if configured
        try:
            import redis
            r = redis.from_url(settings.redis_url, socket_connect_timeout=0.2)
            return bool(r.exists(f"token_blacklist:{token}"))
        except Exception:
            return token in cls._memory_blacklist

    @classmethod
    def add(cls, token: str, ttl_seconds: int = 86400) -> None:
        if not token:
            return
        cls._memory_blacklist.add(token)
        try:
            import redis
            r = redis.from_url(settings.redis_url, socket_connect_timeout=0.2)
            r.setex(f"token_blacklist:{token}", ttl_seconds, "1")
        except Exception:
            pass

    @classmethod
    def remove(cls, token: str) -> None:
        cls._memory_blacklist.discard(token)
        try:
            import redis
            r = redis.from_url(settings.redis_url, socket_connect_timeout=0.2)
            r.delete(f"token_blacklist:{token}")
        except Exception:
            pass

    @classmethod
    def blacklist_token(cls, token: str, ttl_seconds: int = 86400) -> None:
        cls.add(token, ttl_seconds=ttl_seconds)


token_blacklist_store = TokenBlacklistStore()


class SecurityMiddleware(BaseHTTPMiddleware):
    """Production Security Middleware for HTTP header hardening and token validation."""

    def __init__(self, app=None):
        """Initialize security middleware."""
        if app is not None:
            super().__init__(app)
        self.blacklist_store = token_blacklist_store

    async def dispatch(self, request: Request, call_next):
        """Process request through security middleware."""
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        
        # 1. Check Bearer token blacklist / revocation
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            if self.is_token_blacklisted(token):
                logger.warning(f"Rejected blacklisted token for request to {request.url.path}")
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Token has been revoked or blacklisted."},
                    headers={"WWW-Authenticate": "Bearer", "X-Request-ID": request_id}
                )

        # 2. Process downstream request
        response = await call_next(request)

        # 3. Inject strict security headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if settings.environment == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response

    def is_token_blacklisted(self, token: str) -> bool:
        """Check if token is blacklisted."""
        return TokenBlacklistStore.is_blacklisted(token)

    def blacklist_token(self, token: str) -> None:
        """Add token to blacklist."""
        TokenBlacklistStore.add(token)

    def remove_from_blacklist(self, token: str) -> None:
        """Remove token from blacklist."""
        TokenBlacklistStore.remove(token)


# Global security middleware instance
security_middleware = SecurityMiddleware()


def get_security_middleware() -> SecurityMiddleware:
    """Get security middleware instance.

    Returns:
        SecurityMiddleware: Security middleware instance
    """
    return security_middleware


async def verify_token_middleware(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())
) -> dict:
    """Verify token middleware.

    Args:
        request: FastAPI request
        credentials: JWT token credentials

    Returns:
        dict: Token data

    Raises:
        HTTPException: If token is invalid
    """
    token = credentials.credentials
    
    # Check if token is blacklisted
    if security_middleware.is_token_blacklisted(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been invalidated"
        )

    # Verify token
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm]
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


async def require_tenant_middleware(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Require tenant-aware middleware.

    Args:
        request: FastAPI request
        current_user: Current authenticated user
        db: Database session

    Returns:
        dict: Tenant context
    """
    # Extract tenant ID from request or use user's default tenant
    tenant_id = request.headers.get("X-Tenant-ID")
    
    if tenant_id:
        # Check if user has access to tenant
        user_tenants = getattr(current_user, "tenants", [])
        is_superuser = getattr(current_user, "is_superuser", False)
        
        if not is_superuser and tenant_id not in [str(t.id) for t in user_tenants]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have access to the specified tenant"
            )
            
    return {"tenant_id": tenant_id}


class APIKeyAuth:
    """API key authentication handler."""

    def __init__(self, api_key_header: str = "X-API-Key"):
        """Initialize API key auth.

        Args:
            api_key_header: API key header name
        """
        self.api_key_header = api_key_header
        self.valid_api_keys = set()

    def add_api_key(self, api_key: str) -> None:
        """Add valid API key.

        Args:
            api_key: API key
        """
        self.valid_api_keys.add(api_key)

    async def __call__(self, request: Request) -> str:
        """Verify API key.

        Args:
            request: FastAPI request

        Returns:
            str: API key

        Raises:
            HTTPException: If API key is invalid
        """
        api_key = request.headers.get(self.api_key_header)
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key is missing"
            )
        
        if api_key not in self.valid_api_keys:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )
        
        return api_key


# Global API key auth instance
api_key_auth = APIKeyAuth()


def get_api_key_auth() -> APIKeyAuth:
    """Get API key auth instance.

    Returns:
        APIKeyAuth: API key auth instance
    """
    return api_key_auth


# Security middleware chain
security_middleware_stack = [
    Middleware(SlowAPIMiddleware),
    Middleware(
        limiter,
        key_func=get_remote_address,
        error_callback=_rate_limit_exceeded_handler
    )
]
