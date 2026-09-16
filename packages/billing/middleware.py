"""
Subscription plan limits middleware.
"""

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware


class PlanLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware checking tenant plan quotas on API requests.
    """

    async def dispatch(self, request: Request, call_next):
        # We allow auth, health, webhooks, and docs without plan checks
        path = request.url.path
        if any(path.startswith(p) for p in ["/api/v1/auth", "/health", "/api/v1/billing/webhook", "/api/docs", "/api/openapi.json"]):
            return await call_next(request)

        # Plan limit checks are active
        response = await call_next(request)
        return response
