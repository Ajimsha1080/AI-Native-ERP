"""
Centralized Multi-Tenant Plan Quotas and Limit Enforcement.

Defines tier limits:
- free: 3 seats, 10,000 token budget / day, 20 req/min
- pro: 20 seats, 500,000 token budget / day, 100 req/min
- enterprise: 1,000 seats, 10,000,000 token budget / day, 1,000 req/min

Handles grace period checks (7-day grace period for past_due) and feature gating.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Set
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.models.organization import Organization
from packages.database.models.user import OrganizationMember

TIER_LIMITS: Dict[str, Dict[str, Any]] = {
    "free": {
        "seats": 3,
        "token_budget_daily": 10_000,
        "rate_limit_per_min": 20,
        "allowed_features": {"basic_erp", "single_workspace", "community_support"},
    },
    "pro": {
        "seats": 20,
        "token_budget_daily": 500_000,
        "rate_limit_per_min": 100,
        "allowed_features": {"basic_erp", "advanced_erp", "ai_agents", "multi_workspace", "webhooks"},
    },
    "enterprise": {
        "seats": 1_000,
        "token_budget_daily": 10_000_000,
        "rate_limit_per_min": 1_000,
        "allowed_features": {
            "basic_erp",
            "advanced_erp",
            "ai_agents",
            "multi_workspace",
            "webhooks",
            "custom_connectors",
            "audit_retention",
            "priority_sla",
        },
    },
}

GRACE_PERIOD_DAYS = 7


class PlanLimitExceededError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=detail)


class PlanLimitEnforcer:

    @staticmethod
    async def get_org_plan_details(session: AsyncSession, organization_id: UUID) -> Dict[str, Any]:
        res = await session.execute(select(Organization).where(Organization.id == organization_id))
        org = res.scalar_one_or_none()
        if not org:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

        plan = (org.plan or "free").lower()
        if plan not in TIER_LIMITS:
            plan = "free"

        org_settings = dict(org.settings or {})
        sub_status = org_settings.get("subscription_status", "active")
        past_due_since = org_settings.get("past_due_since")

        # Check grace period
        in_grace_period = False
        is_gated = False

        if sub_status == "past_due":
            if past_due_since:
                try:
                    past_due_dt = datetime.fromisoformat(past_due_since)
                    if past_due_dt.tzinfo is None:
                        past_due_dt = past_due_dt.replace(tzinfo=timezone.utc)
                    if (datetime.now(timezone.utc) - past_due_dt) < timedelta(days=GRACE_PERIOD_DAYS):
                        in_grace_period = True
                    else:
                        is_gated = True
                except Exception:
                    is_gated = True
            else:
                in_grace_period = True
        elif sub_status in ("canceled", "unpaid"):
            plan = "free"
            is_gated = True

        return {
            "org": org,
            "plan": plan,
            "limits": TIER_LIMITS[plan],
            "subscription_status": sub_status,
            "in_grace_period": in_grace_period,
            "is_gated": is_gated,
        }

    @classmethod
    async def check_seat_limit(cls, session: AsyncSession, organization_id: UUID) -> None:
        """Raises 402 Payment Required if adding a seat exceeds the plan limit."""
        details = await cls.get_org_plan_details(session, organization_id)
        max_seats = details["limits"]["seats"]

        res = await session.execute(
            select(func.count(OrganizationMember.id)).where(OrganizationMember.organization_id == organization_id)
        )
        current_members = res.scalar() or 0

        if current_members >= max_seats:
            raise PlanLimitExceededError(
                f"Seat limit reached ({current_members}/{max_seats}) for the '{details['plan']}' plan. "
                "Upgrade your subscription to invite more users."
            )

    @classmethod
    async def check_token_budget(
        cls, session: AsyncSession, organization_id: UUID, tokens_requested: int = 1
    ) -> None:
        """Checks daily token budget and raises 402 if exceeded or gated."""
        details = await cls.get_org_plan_details(session, organization_id)
        if details["is_gated"]:
            raise PlanLimitExceededError(
                "Subscription payment is past due beyond the 7-day grace period. "
                "AI Agent operations are suspended until payment succeeds."
            )

        daily_budget = details["limits"]["token_budget_daily"]
        if tokens_requested > daily_budget:
            raise PlanLimitExceededError(
                f"Requested {tokens_requested} tokens exceeds your daily quota of {daily_budget:,} for '{details['plan']}' plan."
            )

    @classmethod
    async def check_feature_access(cls, session: AsyncSession, organization_id: UUID, feature: str) -> None:
        """Verifies feature access according to tier and grace period."""
        details = await cls.get_org_plan_details(session, organization_id)
        allowed = details["limits"]["allowed_features"]
        if feature not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Feature '{feature}' is not available on the '{details['plan']}' plan. Please upgrade.",
            )
        if details["is_gated"]:
            raise PlanLimitExceededError(
                f"Access to '{feature}' is restricted because subscription is past due beyond the grace period."
            )
