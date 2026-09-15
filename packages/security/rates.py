"""
Rate limiting utilities.

Handles rate limiting for different endpoints and user types.
"""

from typing import Dict, Optional
from datetime import datetime, timedelta
from fastapi import Request, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from packages.config import get_settings

settings = get_settings()


class RateLimiter:
    """Rate limiter for different endpoints and user types."""

    def __init__(self):
        """Initialize rate limiter."""
        self.limiter = Limiter(key_func=get_remote_address)
        self.user_requests: Dict[str, Dict[str, datetime]] = {}
        self.endpoint_limits: Dict[str, tuple] = {
            # Format: (requests, minutes, endpoint_name)
            "/api/v1/auth/login": (5, 15, "login"),
            "/api/v1/auth/register": (3, 60, "register"),
            "/api/v1/auth/reset-password": (2, 60, "password_reset"),
            "/api/v1/users/me/password": (1, 30, "password_change"),
            "/api/v1/agents": (100, 60, "agents"),
            "/api/v1/agents/execute": (20, 60, "agent_execution"),
            "/api/v1/actions": (50, 60, "actions"),
            "/api/v1/tools": (100, 60, "tools"),
            "/api/v1/workflows": (50, 60, "workflows"),
            "/api/v1/organizations": (20, 60, "organizations"),
            "/api/v1/data/query": (100, 60, "data_query"),
            "/api/v1/data/import": (10, 60, "data_import"),
            "/api/v1/data/export": (5, 60, "data_export"),
            "/api/v1/reports": (20, 60, "reports"),
            "/api/v1/documents": (50, 60, "documents"),
            "/api/v1/documents/upload": (10, 60, "document_upload"),
            "/api/v1/chats": (100, 60, "chats"),
            "/api/v1/notifications": (50, 60, "notifications"),
            "/api/v1/webhooks": (10, 60, "webhooks"),
            "/api/v1/logs": (1, 60, "logs"),  # Security log
            "/api/v1/security/audit": (5, 60, "security_audit"),
            "/api/v1/admin/users": (10, 60, "admin_users"),
            "/api/v1/admin/organizations": (5, 60, "admin_organizations"),
            "/api/v1/admin/system": (1, 60, "admin_system"),
        }

    def check_rate_limit(self, request: Request, endpoint: str) -> bool:
        """Check rate limit for request.

        Args:
            request: FastAPI request
            endpoint: API endpoint

        Returns:
            bool: True if rate limit check passes

        Raises:
            HTTPException: If rate limit exceeded
        """
        # Get client identifier (IP for anonymous, user ID for authenticated)
        client_id = self._get_client_id(request)
        
        # Get endpoint-specific limit
        limit = self.endpoint_limits.get(endpoint, (100, 60, "default"))
        max_requests, time_window, _ = limit
        
        # Get current requests count
        now = datetime.utcnow()
        if client_id not in self.user_requests:
            self.user_requests[client_id] = {}
        
        if endpoint not in self.user_requests[client_id]:
            self.user_requests[client_id][endpoint] = []
        
        # Clean old requests
        cutoff_time = now - timedelta(minutes=time_window)
        self.user_requests[client_id][endpoint] = [
            req_time for req_time in self.user_requests[client_id][endpoint]
            if req_time > cutoff_time
        ]
        
        # Check if limit exceeded
        if len(self.user_requests[client_id][endpoint]) >= max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for {endpoint}. Maximum {max_requests} requests per {time_window} minutes.",
                headers={"X-RateLimit-Limit": str(max_requests), "X-RateLimit-Reset": str(int(cutoff_time.timestamp()))}
            )
        
        # Record request
        self.user_requests[client_id][endpoint].append(now)
        
        return True

    def _get_client_id(self, request: Request) -> str:
        """Get client identifier from request.

        Args:
            request: FastAPI request

        Returns:
            str: Client identifier
        """
        # Try to get user from state, otherwise fallback to IP
        if hasattr(request.state, "user") and request.state.user:
            return str(request.state.user.id)
        return get_remote_address(request)

    def get_rate_limit_info(self, request: Request, endpoint: str) -> dict:
        """Get rate limit information for request.

        Args:
            request: FastAPI request
            endpoint: API endpoint

        Returns:
            dict: Rate limit information
        """
        client_id = self._get_client_id(request)
        limit = self.endpoint_limits.get(endpoint, (100, 60, "default"))
        max_requests, time_window, _ = limit
        
        # Get current requests count
        now = datetime.utcnow()
        if client_id in self.user_requests and endpoint in self.user_requests[client_id]:
            recent_requests = [
                req_time for req_time in self.user_requests[client_id][endpoint]
                if req_time > now - timedelta(minutes=time_window)
            ]
            remaining = max_requests - len(recent_requests)
            reset_time = now + timedelta(minutes=time_window)
        else:
            remaining = max_requests
            reset_time = now + timedelta(minutes=time_window)
        
        return {
            "limit": max_requests,
            "remaining": remaining,
            "reset": int(reset_time.timestamp()),
            "window": time_window
        }

    def get_user_rate_limits(self, user_id: str) -> dict:
        """Get rate limits for specific user.

        Args:
            user_id: User ID

        Returns:
            dict: User rate limits
        """
        # Implement user-specific logic (e.g. check DB for premium status)
        is_premium = False # Replace with actual DB check if needed
        return {
            "is_premium": False,
            "limits": {
                "agents": {"limit": 100, "window": 60},
                "agent_execution": {"limit": 20, "window": 60},
                "actions": {"limit": 50, "window": 60},
                "documents": {"limit": 50, "window": 60},
                "data_export": {"limit": 5, "window": 60},
            }
        }

    def increase_rate_limit(self, user_id: str, endpoint: str, factor: float = 1.5) -> None:
        """Increase rate limit for user.

        Args:
            user_id: User ID
            endpoint: API endpoint
            factor: Factor by which to increase limit
        """
        if user_id not in self.user_requests:
            return
        
        # We can increase limits by manipulating the endpoint limits or clearing history
        # For simplicity, we clear some history for the user's endpoint
        if endpoint in self.user_requests[user_id]:
            cutoff = len(self.user_requests[user_id][endpoint]) // int(factor)
            self.user_requests[user_id][endpoint] = self.user_requests[user_id][endpoint][cutoff:]

    def reset_rate_limit(self, user_id: str, endpoint: str) -> None:
        """Reset rate limit for user.

        Args:
            user_id: User ID
            endpoint: API endpoint
        """
        if user_id in self.user_requests and endpoint in self.user_requests[user_id]:
            self.user_requests[user_id][endpoint] = []

    def cleanup_old_requests(self) -> None:
        """Clean up old request data to prevent memory leaks."""
        now = datetime.utcnow()
        cutoff_time = now - timedelta(days=7)  # Keep requests for 7 days
        
        for user_id in list(self.user_requests.keys()):
            for endpoint in list(self.user_requests[user_id].keys()):
                self.user_requests[user_id][endpoint] = [
                    req_time for req_time in self.user_requests[user_id][endpoint]
                    if req_time > cutoff_time
                ]
                
                # Remove empty endpoints
                if not self.user_requests[user_id][endpoint]:
                    del self.user_requests[user_id][endpoint]
            
            # Remove empty user records
            if not self.user_requests[user_id]:
                del self.user_requests[user_id]


# Global rate limiter instance
rate_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    """Get rate limiter instance.

    Returns:
        RateLimiter: Rate limiter instance
    """
    return rate_limiter


class SecurityRateLimits:
    """Security-related rate limits."""

    @staticmethod
    def check_security_rate_limit(request: Request) -> bool:
        """Check security-related rate limits.

        Args:
            request: FastAPI request

        Returns:
            bool: True if rate limit check passes

        Raises:
            HTTPException: If rate limit exceeded
        """
        # For basic security rate limiting, we check against a strict endpoint limit
        return rate_limiter.check_rate_limit(request, "/api/v1/auth/login")

    @staticmethod
    def check_admin_rate_limit(request: Request) -> bool:
        """Check admin-specific rate limits.

        Args:
            request: FastAPI request

        Returns:
            bool: True if rate limit check passes

        Raises:
            HTTPException: If rate limit exceeded
        """
        # Limit admin operations to prevent abuse
        return rate_limiter.check_rate_limit(request, "/api/v1/admin/system")

    @staticmethod
    def check_data_access_rate_limit(request: Request, data_type: str) -> bool:
        """Check data access rate limits.

        Args:
            request: FastAPI request
            data_type: Type of data being accessed

        Returns:
            bool: True if rate limit check passes

        Raises:
            HTTPException: If rate limit exceeded
        """
        # General limit for data queries
        return rate_limiter.check_rate_limit(request, "/api/v1/data/query")


# Helper functions for rate limiting in endpoints
def check_endpoint_rate_limit(request: Request, endpoint: Optional[str] = None) -> bool:
    """Check rate limit for endpoint.

    Args:
        request: FastAPI request
        endpoint: API endpoint (optional, defaults to request.url.path)

    Returns:
        bool: True if rate limit check passes

    Raises:
        HTTPException: If rate limit exceeded
    """
    path = endpoint or request.url.path
    return rate_limiter.check_rate_limit(request, path)


def get_rate_limit_headers(request: Request, endpoint: str) -> dict:
    """Get rate limit headers for response.

    Args:
        request: FastAPI request
        endpoint: API endpoint

    Returns:
        dict: Rate limit headers
    """
    return rate_limiter.get_rate_limit_info(request, endpoint)


def cleanup_rate_limit_data() -> None:
    """Clean up rate limit data."""
    rate_limiter.cleanup_old_requests()
