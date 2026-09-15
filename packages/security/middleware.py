"""
Security middleware.

Provides security-related middleware for the application.
"""

import uuid
from typing import Optional
from fastapi import Request, Response, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware import Middleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt

from starlette.middleware.base import BaseHTTPMiddleware
from packages.config import get_settings
from packages.database import get_db
from packages.database.models import User
from packages.security.auth import get_current_user

settings = get_settings()

# Rate limiting
limiter = Limiter(key_func=get_remote_address)


class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware for the application."""

    def __init__(self, app=None):
        """Initialize security middleware."""
        if app is not None:
            super().__init__(app)
        self.token_blacklist = set()

    async def dispatch(self, request: Request, call_next):
        """Process request through security middleware."""
        response = await call_next(request)
        return response

    async def check_rate_limit(self, request: Request) -> bool:
        """Check rate limit for request.

        Args:
            request: FastAPI request

        Returns:
            bool: True if rate limit check passes
        """
        try:
            await limiter(request)
            return True
        except RateLimitExceeded:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests"
            )

    def is_token_blacklisted(self, token: str) -> bool:
        """Check if token is blacklisted.

        Args:
            token: JWT token

        Returns:
            bool: True if token is blacklisted
        """
        return token in self.token_blacklist

    def blacklist_token(self, token: str) -> None:
        """Add token to blacklist.

        Args:
            token: JWT token
        """
        self.token_blacklist.add(token)

    def remove_from_blacklist(self, token: str) -> None:
        """Remove token from blacklist.

        Args:
            token: JWT token
        """
        if token in self.token_blacklist:
            self.token_blacklist.remove(token)


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
