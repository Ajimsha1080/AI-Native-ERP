"""
Billing REST API routes for Stripe Checkout, idempotent webhooks, and subscription status.
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from pydantic import BaseModel
from sqlalchemy import select

from packages.database.tenant_context import TenantDB
from packages.auth.dependencies import CurrentUser, require_role
from packages.database.models.organization import Organization
from packages.billing.stripe_client import StripeBillingClient

router = APIRouter(prefix="/billing", tags=["Billing & Quotas"])


class CheckoutRequest(BaseModel):
    plan: str  # "pro" or "enterprise"
    success_url: Optional[str] = "http://localhost:3000/billing/success"
    cancel_url: Optional[str] = "http://localhost:3000/billing/cancel"


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

    return StripeBillingClient.create_checkout_session(
        organization_id=current_user.org_id,
        plan=body.plan,
        success_url=body.success_url or "http://localhost:3000/billing/success",
        cancel_url=body.cancel_url or "http://localhost:3000/billing/cancel",
    )


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature"),
):
    """
    Stripe Webhook endpoint. Idempotently processes events with signature verification.
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


@router.get("/invoices")
async def list_invoices(
    current_user: CurrentUser,
    _: None = Depends(require_role("owner", "admin")),
):
    """List billing invoices and payment receipts for current tenant."""
    return await StripeBillingClient.get_invoices(organization_id=current_user.org_id)


@router.post("/cancel")
async def cancel_subscription(
    current_user: CurrentUser,
    db: TenantDB,
    _: None = Depends(require_role("owner", "admin")),
):
    """Cancels active subscription and downgrades tenant to free tier."""
    res = await db.execute(select(Organization).where(Organization.id == current_user.org_id))
    org = res.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    org.plan = "free"
    org_settings = dict(org.settings or {})
    org_settings["subscription_status"] = "canceled"
    org.settings = org_settings
    await db.commit()

    return {"status": "success", "message": "Subscription canceled. Organization is now on Free tier."}

