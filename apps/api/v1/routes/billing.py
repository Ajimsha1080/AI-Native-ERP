"""
Billing REST API routes for Stripe Checkout, Customer Portal, idempotent webhooks, and subscription status.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select

from packages.auth.dependencies import CurrentUser, require_role
from packages.billing.plan_limits import PlanLimitEnforcer
from packages.billing.stripe_client import StripeBillingClient
from packages.database.models.organization import Organization
from packages.database.tenant_context import TenantDB

router = APIRouter(prefix="/billing", tags=["Billing & Quotas"])


class CheckoutRequest(BaseModel):
    plan: str  # "pro" or "enterprise"
    success_url: Optional[str] = "http://localhost:3000/billing/success"
    cancel_url: Optional[str] = "http://localhost:3000/billing/cancel"


class PortalRequest(BaseModel):
    return_url: Optional[str] = "http://localhost:3000/billing"


class SubscriptionResponse(BaseModel):
    organization_id: str
    plan: str
    status: str


@router.post("/checkout")
async def create_checkout_session(
    body: CheckoutRequest,
    current_user: CurrentUser,
    _: None = Depends(require_role("owner", "admin")),
):
    """Initiates a Stripe Checkout session to upgrade the tenant's subscription tier."""
    if body.plan not in ["pro", "enterprise"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Plan must be 'pro' or 'enterprise'")

    return await StripeBillingClient.create_checkout_session(
        organization_id=current_user.org_id,
        plan=body.plan,
        success_url=body.success_url or "http://localhost:3000/billing/success",
        cancel_url=body.cancel_url or "http://localhost:3000/billing/cancel",
    )


@router.post("/portal")
async def create_portal_session(
    body: PortalRequest,
    current_user: CurrentUser,
    _: None = Depends(require_role("owner", "admin")),
):
    """Creates a Stripe Billing Customer Portal session for the tenant."""
    return await StripeBillingClient.create_portal_session(
        organization_id=current_user.org_id,
        return_url=body.return_url or "http://localhost:3000/billing",
    )


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature"),
):
    """
    Stripe Webhook endpoint. Idempotently processes events with signature verification
    and updates subscription state from cryptographic webhooks only.
    """
    payload = await request.body()
    try:
        return await StripeBillingClient.handle_webhook(payload, stripe_signature or "")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    current_user: CurrentUser,
    db: TenantDB,
):
    """Get active subscription plan status for current tenant."""
    res = await db.execute(select(Organization).where(Organization.id == current_user.org_id))
    org = res.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    sub_status = (org.settings or {}).get("subscription_status", org.status or "active")

    return SubscriptionResponse(
        organization_id=str(org.id),
        plan=org.plan or "free",
        status=sub_status,
    )


@router.get("/quotas")
async def get_plan_quotas(
    current_user: CurrentUser,
    db: TenantDB,
):
    """Get current tenant's plan quotas, seat limits, and grace period status."""
    details = await PlanLimitEnforcer.get_org_plan_details(db, current_user.org_id)
    return {
        "organization_id": str(current_user.org_id),
        "plan": details["plan"],
        "limits": details["limits"],
        "subscription_status": details["subscription_status"],
        "in_grace_period": details["in_grace_period"],
        "is_gated": details["is_gated"],
    }


@router.get("/invoices")
async def list_invoices(
    current_user: CurrentUser,
    _: None = Depends(require_role("owner", "admin")),
):
    """List billing invoices and payment receipts for current tenant from Stripe."""
    return await StripeBillingClient.get_invoices(organization_id=current_user.org_id)


@router.post("/cancel")
async def cancel_subscription(
    current_user: CurrentUser,
    _: None = Depends(require_role("owner", "admin")),
):
    """
    Cancels active subscription in Stripe with cancel_at_period_end.
    State is updated exclusively when the Stripe webhook arrives.
    """
    return await StripeBillingClient.cancel_subscription(organization_id=current_user.org_id)
