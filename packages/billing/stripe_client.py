"""
Stripe payment processing and webhook handler for tenant subscriptions.
"""

from typing import Dict, Any, Optional
from uuid import UUID

import stripe
from sqlalchemy import select

from packages.config.settings import settings
from packages.database.core import AsyncSessionLocal
from packages.database.models.organization import Organization

if settings.stripe_secret_key:
    stripe.api_key = settings.stripe_secret_key


class StripeBillingClient:

    @staticmethod
    def create_checkout_session(
        organization_id: UUID,
        plan: str,  # "pro" or "enterprise"
        success_url: str = "http://localhost:3000/billing/success",
        cancel_url: str = "http://localhost:3000/billing/cancel",
    ) -> Dict[str, Any]:
        """Creates a Stripe Checkout Session for subscription upgrading."""
        if not settings.stripe_secret_key:
            return {
                "session_id": f"mock_session_{organization_id}",
                "url": f"{success_url}?session_id=mock_session_{organization_id}",
            }

        price_id = (
            settings.stripe_price_id_pro if plan == "pro" else settings.stripe_price_id_enterprise
        )

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            client_reference_id=str(organization_id),
            metadata={"organization_id": str(organization_id), "plan": plan},
        )
        return {"session_id": session.id, "url": session.url}

    @staticmethod
    async def handle_webhook(payload: bytes, sig_header: str) -> Dict[str, Any]:
        """
        Idempotent Stripe webhook event handler.
        Verifies signature and updates tenant organization plan.
        """
        event = None

        if settings.stripe_webhook_secret:
            try:
                event = stripe.Webhook.construct_event(
                    payload, sig_header, settings.stripe_webhook_secret
                )
            except (ValueError, stripe.error.SignatureVerificationError) as e:
                raise ValueError(f"Invalid webhook signature: {e}")
        else:
            # Fallback for dev / tests
            import json
            event = json.loads(payload.decode("utf-8"))

        event_type = event.get("type")
        data_object = event.get("data", {}).get("object", {})

        if event_type in ["checkout.session.completed", "customer.subscription.updated"]:
            org_id_str = data_object.get("metadata", {}).get("organization_id") or data_object.get("client_reference_id")
            plan = data_object.get("metadata", {}).get("plan", "pro")

            if org_id_str:
                async with AsyncSessionLocal() as session:
                    res = await session.execute(
                        select(Organization).where(Organization.id == UUID(org_id_str))
                    )
                    org = res.scalar_one_or_none()
                    if org:
                        org.plan = plan
                        await session.commit()

        return {"status": "processed", "event_type": event_type}
