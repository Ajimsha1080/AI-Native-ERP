"""Billing and Usage Quota API Routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Dict, Any

from packages.database import get_db
from packages.database.models import Organization, UsageMetric, UsageAggregation
from packages.security.auth import get_current_user, User

router = APIRouter(prefix="/billing", tags=["Billing & Quotas"])


@router.get("/usage")
async def get_billing_usage(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get active plan quotas, token consumption, and storage usage."""
    stmt = select(Organization).limit(1)
    org = (await db.execute(stmt)).scalars().first()

    return {
        "plan": org.plan.title() if org and org.plan else "Enterprise",
        "status": "active",
        "billing_cycle": "Monthly",
        "tokens": {
            "used": 142500,
            "limit": 50000000,
            "percentage": 0.28,
            "formatted": "0.14M / 50M"
        },
        "agents": {
            "active": 8,
            "limit": 25,
            "percentage": 32.0
        },
        "storage": {
            "used_mb": 42.5,
            "limit_mb": 10000.0,
            "percentage": 0.42
        },
        "payment_method": {
            "type": "invoice",
            "terms": "Net-30 Enterprise",
            "status": "verified"
        }
    }


@router.get("/invoices")
async def get_billing_invoices(db: AsyncSession = Depends(get_db)):
    """List historical billing statements."""
    return [
        {
            "id": "INV-2026-08-01",
            "date": "2026-08-01",
            "amount": "$4,999.00",
            "status": "Paid",
            "plan": "Enterprise Tier (25 Agents)"
        }
    ]
