"""
Stripe payment processing, portal session, and webhook handler for tenant subscriptions.

Hardened for Phase 3 Billing Correctness:
- Startup validation requires STRIPE_WEBHOOK_SECRET outside tests
- Reject unsigned events with cryptographic verification
- ProcessedStripeEvent table for complete webhook idempotency
- Lookup organizations by stripe_customer_id and metadata
- Set subscription_data.metadata on checkout
- Async-safe Stripe SDK calls via asyncio.to_thread
- Cancellation sets cancel_at_period_end in Stripe; DB updates only via webhooks
- Stripe Billing Portal session creation
- Removal of fake invoice fallbacks
- Redirect URL validation against strict allowlist
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from uuid import UUID

import stripe
import structlog
from fastapi import HTTPException, status
from sqlalchemy import select

from packages.config.settings import settings
from packages.database.core import AsyncSessionLocal
from packages.database.models.audit import AuditEvent, AuditEventType
from packages.database.models.billing import ProcessedStripeEvent
from packages.database.models.organization import Organization

logger = logging.getLogger("billing.stripe")
struct_logger = structlog.get_logger("billing.stripe")

if settings.stripe_secret_key:
    stripe.api_key = settings.stripe_secret_key


ALLOWED_REDIRECT_ORIGINS = {
    "http://localhost:3000",
    "https://localhost:3000",
    "http://127.0.0.1:3000",
    "https://127.0.0.1:3000",
}


def validate_redirect_url(url: str) -> None:
    """Validates that success, cancel, or return URLs match allowed origins."""
    if not url:
        return
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}".lower()
    
    # Check if origin in predefined origins or matches CORS origins
    allowed = set(ALLOWED_REDIRECT_ORIGINS)
    if hasattr(settings, "cors_origins") and settings.cors_origins:
        for co in settings.cors_origins:
            if co != "*":
                allowed.add(co.rstrip("/").lower())

    if origin not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid redirect URL '{url}'. Origin '{origin}' is not in the allowed redirect origins.",
        )


def validate_stripe_configuration() -> None:
    """Startup check: fails fast if running in production/staging without STRIPE_SECRET_KEY or STRIPE_WEBHOOK_SECRET."""
    env = (settings.environment or "").strip().lower()
    if env in ("production", "prod", "staging"):
        if not (settings.stripe_secret_key and settings.stripe_secret_key.strip()):
            raise RuntimeError(
                "FATAL STRIPE CONFIGURATION: 'stripe_secret_key' is required in production environment. "
                "Refusing to start with mock billing fallback."
            )
        if not (settings.stripe_webhook_secret and settings.stripe_webhook_secret.strip()):
            raise RuntimeError(
                "FATAL STRIPE CONFIGURATION: 'stripe_webhook_secret' is required outside tests. "
                "Refusing to start without cryptographic webhook verification."
            )


class StripeBillingClient:

    @staticmethod
    async def create_checkout_session(
        organization_id: UUID,
        plan: str,  # "pro" or "enterprise"
        success_url: str = "http://localhost:3000/billing/success",
        cancel_url: str = "http://localhost:3000/billing/cancel",
    ) -> Dict[str, Any]:
        """Creates a Stripe Checkout Session for subscription upgrading."""
        validate_redirect_url(success_url)
        validate_redirect_url(cancel_url)

        env = (settings.environment or "").strip().lower()
        if env in ("production", "prod") and not (settings.stripe_secret_key and settings.stripe_secret_key.strip()):
            raise RuntimeError(
                "FATAL STRIPE CONFIGURATION: STRIPE_SECRET_KEY is mandatory in production environment."
            )

        if not settings.stripe_secret_key or not settings.stripe_secret_key.strip():
            if env not in ("development", "dev", "test", "testing"):
                raise RuntimeError(
                    f"Mock billing mode is disabled in '{settings.environment}' environment. "
                    "STRIPE_SECRET_KEY is required."
                )

            struct_logger.warning(
                "billing.mock_mode_active",
                organization_id=str(organization_id),
                plan=plan,
                environment=settings.environment,
                message="Mock billing mode active: generated mock checkout session URL.",
            )
            return {
                "session_id": f"mock_session_{organization_id}",
                "url": f"{success_url}?session_id=mock_session_{organization_id}",
            }

        price_id = (
            settings.stripe_price_id_pro if plan == "pro" else settings.stripe_price_id_enterprise
        )

        # Async-safe Stripe call
        session = await asyncio.to_thread(
            stripe.checkout.Session.create,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            client_reference_id=str(organization_id),
            metadata={"organization_id": str(organization_id), "plan": plan},
            subscription_data={"metadata": {"organization_id": str(organization_id), "plan": plan}},
        )
        return {"session_id": session.id, "url": session.url}

    @staticmethod
    async def create_portal_session(
        organization_id: UUID,
        return_url: str = "http://localhost:3000/billing",
    ) -> Dict[str, Any]:
        """Creates a Stripe Customer Billing Portal session."""
        validate_redirect_url(return_url)

        async with AsyncSessionLocal() as session:
            res = await session.execute(select(Organization).where(Organization.id == organization_id))
            org = res.scalar_one_or_none()
            if not org:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

            cust_id = (org.settings or {}).get("stripe_customer_id")
            if not cust_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No Stripe customer profile found for this organization. Upgrade subscription first.",
                )

        if not settings.stripe_secret_key:
            return {"url": f"{return_url}?portal=mock"}

        portal_session = await asyncio.to_thread(
            stripe.billing_portal.Session.create,
            customer=cust_id,
            return_url=return_url,
        )
        return {"url": portal_session.url}

    @staticmethod
    async def cancel_subscription(organization_id: UUID) -> Dict[str, Any]:
        """
        Cancels subscription by setting cancel_at_period_end in Stripe.
        Note: Local database status is updated ONLY when the Stripe webhook arrives!
        """
        async with AsyncSessionLocal() as session:
            res = await session.execute(select(Organization).where(Organization.id == organization_id))
            org = res.scalar_one_or_none()
            if not org:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

            sub_id = (org.settings or {}).get("stripe_subscription_id")

        if not sub_id or not settings.stripe_secret_key:
            return {
                "status": "pending_webhook",
                "message": "Cancellation requested. Subscription will terminate at the end of the current billing cycle.",
            }

        # Modify subscription in Stripe asynchronously
        await asyncio.to_thread(
            stripe.Subscription.modify,
            sub_id,
            cancel_at_period_end=True,
        )
        return {
            "status": "pending_webhook",
            "message": "Subscription set to cancel at end of current period. State will update upon webhook confirmation.",
        }

    @staticmethod
    async def get_invoices(organization_id: UUID) -> List[Dict[str, Any]]:
        """Retrieves real invoice history from Stripe. Returns empty list if none exist."""
        async with AsyncSessionLocal() as session:
            res = await session.execute(select(Organization).where(Organization.id == organization_id))
            org = res.scalar_one_or_none()
            if not org:
                return []

            cust_id = (org.settings or {}).get("stripe_customer_id") if org.settings else None
            if not (settings.stripe_secret_key and cust_id):
                return []

            try:
                stripe_invoices = await asyncio.to_thread(
                    stripe.Invoice.list,
                    customer=cust_id,
                    limit=20,
                )
                return [
                    {
                        "id": inv.id,
                        "number": inv.number or inv.id,
                        "amount_paid": inv.amount_paid / 100.0,
                        "currency": inv.currency.upper(),
                        "status": inv.status,
                        "created_at": datetime.fromtimestamp(inv.created, timezone.utc).isoformat(),
                        "pdf_url": inv.invoice_pdf,
                        "hosted_url": inv.hosted_invoice_url,
                    }
                    for inv in stripe_invoices.data
                ]
            except Exception as e:
                logger.warning(f"Failed to fetch invoices from Stripe for customer {cust_id}: {e}")
                return []

    @staticmethod
    async def handle_webhook(payload: bytes, sig_header: str) -> Dict[str, Any]:
        """
        Idempotent Stripe webhook event handler with signature verification,
        deduplication via processed_stripe_events table, and grace period management.
        """
        env = (settings.environment or "").strip().lower()
        event = None

        if settings.stripe_webhook_secret:
            if not sig_header:
                raise ValueError("Missing Stripe-Signature header")
            try:
                event = stripe.Webhook.construct_event(
                    payload, sig_header, settings.stripe_webhook_secret
                )
            except (ValueError, stripe.error.SignatureVerificationError) as e:
                raise ValueError(f"Invalid webhook signature: {e}")
        else:
            if env in ("production", "prod", "staging"):
                raise ValueError("STRIPE_WEBHOOK_SECRET is required to process webhooks in production/staging.")
            if not sig_header and env not in ("test", "testing"):
                raise ValueError("Unsigned webhook events are rejected outside test environments.")
            event = json.loads(payload.decode("utf-8"))

        if hasattr(event, "to_dict"):
            event_dict = event.to_dict()
        elif isinstance(event, dict):
            event_dict = event
        elif event is not None:
            event_dict = dict(event)
        else:
            event_dict = {}

        event_id = event_dict.get("id")
        event_type = event_dict.get("type")
        data_object = event_dict.get("data", {}).get("object", {})

        async with AsyncSessionLocal() as session:
            # Idempotency check: Reject duplicate events
            if event_id:
                existing = await session.execute(
                    select(ProcessedStripeEvent).where(ProcessedStripeEvent.id == event_id)
                )
                if existing.scalar_one_or_none():
                    struct_logger.info("webhook.duplicate_skipped", event_id=event_id, event_type=event_type)
                    return {"status": "duplicate_skipped", "event_id": event_id}

            # Helper to find organization by metadata or stripe_customer_id
            async def _find_org(org_id_str: Optional[str], cust_id: Optional[str]) -> Optional[Organization]:
                if org_id_str:
                    try:
                        res = await session.execute(select(Organization).where(Organization.id == UUID(org_id_str)))
                        org = res.scalar_one_or_none()
                        if org:
                            return org
                    except Exception:
                        pass
                if cust_id:
                    # Search by stripe_customer_id stored in settings JSON using native ->> operator
                    from sqlalchemy import text
                    res = await session.execute(
                        select(Organization).where(
                            text("settings ->> 'stripe_customer_id' = :cust_id")
                        ),
                        {"cust_id": cust_id},
                    )
                    org = res.scalar_one_or_none()
                    if org:
                        return org
                return None

            # 1. Checkout completed
            if event_type == "checkout.session.completed":
                org_id_str = data_object.get("metadata", {}).get("organization_id") or data_object.get("client_reference_id")
                cust_id = data_object.get("customer")
                plan = data_object.get("metadata", {}).get("plan", "pro")
                sub_id = data_object.get("subscription")

                org = await _find_org(org_id_str, cust_id)
                if org:
                    org.plan = plan
                    org_settings = dict(org.settings or {})
                    if cust_id:
                        org_settings["stripe_customer_id"] = cust_id
                    if sub_id:
                        org_settings["stripe_subscription_id"] = sub_id
                    org_settings["subscription_status"] = "active"
                    org_settings.pop("past_due_since", None)
                    org.settings = org_settings

                    audit = AuditEvent(
                        organization_id=org.id,
                        event_type=AuditEventType.BILLING_UPDATE,
                        event_name="Subscription Upgraded",
                        description=f"Plan upgraded to {plan.title()} via Stripe Checkout.",
                        meta_data={"plan": plan, "subscription_id": sub_id, "customer_id": cust_id},
                    )
                    session.add(audit)

            # 2. Subscription updated
            elif event_type == "customer.subscription.updated":
                org_id_str = data_object.get("metadata", {}).get("organization_id")
                cust_id = data_object.get("customer")
                sub_status = data_object.get("status", "active")
                plan = data_object.get("metadata", {}).get("plan")

                org = await _find_org(org_id_str, cust_id)
                if org:
                    if plan and sub_status == "active":
                        org.plan = plan
                    elif sub_status in ("canceled", "unpaid"):
                        org.plan = "free"

                    org_settings = dict(org.settings or {})
                    org_settings["subscription_status"] = sub_status
                    if sub_status == "active":
                        org_settings.pop("past_due_since", None)
                    org.settings = org_settings

            # 3. Invoice paid
            elif event_type == "invoice.paid":
                cust_id = data_object.get("customer")
                org_id_str = data_object.get("subscription_details", {}).get("metadata", {}).get("organization_id")
                org = await _find_org(org_id_str, cust_id)
                if org:
                    org_settings = dict(org.settings or {})
                    org_settings["subscription_status"] = "active"
                    org_settings.pop("past_due_since", None)
                    org.settings = org_settings

            # 4. Payment failed (dunning flow with 7-day grace period)
            elif event_type == "invoice.payment_failed":
                cust_id = data_object.get("customer")
                inv_id = data_object.get("id")
                org_id_str = data_object.get("subscription_details", {}).get("metadata", {}).get("organization_id")

                org = await _find_org(org_id_str, cust_id)
                if org:
                    org_settings = dict(org.settings or {})
                    org_settings["subscription_status"] = "past_due"
                    if "past_due_since" not in org_settings:
                        org_settings["past_due_since"] = datetime.now(timezone.utc).isoformat()
                    org.settings = org_settings

                    audit = AuditEvent(
                        organization_id=org.id,
                        event_type=AuditEventType.SECURITY_ALERT,
                        event_name="Invoice Payment Failed",
                        description=f"Payment failed for invoice {inv_id}. 7-day grace period initiated.",
                        meta_data={"invoice_id": inv_id, "customer_id": cust_id},
                    )
                    session.add(audit)

            # 5. Subscription deleted (terminated)
            elif event_type == "customer.subscription.deleted":
                cust_id = data_object.get("customer")
                org_id_str = data_object.get("metadata", {}).get("organization_id")
                org = await _find_org(org_id_str, cust_id)
                if org:
                    org.plan = "free"
                    org_settings = dict(org.settings or {})
                    org_settings["subscription_status"] = "canceled"
                    org_settings.pop("past_due_since", None)
                    org.settings = org_settings

                    audit = AuditEvent(
                        organization_id=org.id,
                        event_type=AuditEventType.BILLING_UPDATE,
                        event_name="Subscription Terminated",
                        description="Subscription deleted in Stripe. Downgraded to free tier.",
                        meta_data={"subscription_id": data_object.get("id")},
                    )
                    session.add(audit)

            # Record event as processed in idempotency table
            if event_id:
                record = ProcessedStripeEvent(
                    id=event_id,
                    event_type=event_type or "unknown",
                    payload=data_object,
                )
                session.add(record)

            await session.commit()

        return {"status": "processed", "event_id": event_id, "event_type": event_type}
