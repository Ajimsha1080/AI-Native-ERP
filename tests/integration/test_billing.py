"""
Integration tests for Stripe billing and webhook processing.
"""

import pytest
import json
from uuid import uuid4

from packages.database.core import async_session_scope, create_db_and_tables
from packages.database.models.organization import Organization
from packages.billing.stripe_client import StripeBillingClient


@pytest.mark.asyncio
async def test_stripe_checkout_and_webhook_processing():
    await create_db_and_tables()

    # 1. Create Organization on Free plan
    org_id = uuid4()
    async with async_session_scope() as session:
        org = Organization(
            id=org_id,
            name="Test Org",
            slug=f"test-org-{uuid4().hex[:6]}",
            plan="free",
            status="active",
        )
        session.add(org)
        await session.commit()

    # 2. Generate Checkout Session
    checkout = StripeBillingClient.create_checkout_session(
        organization_id=org_id,
        plan="enterprise",
    )
    assert "session_id" in checkout
    assert "url" in checkout

    # 3. Simulate Stripe Webhook Event (checkout.session.completed)
    webhook_payload = json.dumps({
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": str(org_id),
                "metadata": {
                    "organization_id": str(org_id),
                    "plan": "enterprise",
                }
            }
        }
    }).encode("utf-8")

    result = await StripeBillingClient.handle_webhook(webhook_payload, sig_header="")
    assert result["status"] == "processed"

    # 4. Verify Organization upgraded to Enterprise
    async with async_session_scope() as session:
        from sqlalchemy import select
        res = await session.execute(select(Organization).where(Organization.id == org_id))
        updated_org = res.scalar_one_or_none()
        assert updated_org is not None
        assert updated_org.plan == "enterprise"
        assert updated_org.settings.get("subscription_status") == "active"

    # 5. Test Invoices listing
    invoices = await StripeBillingClient.get_invoices(organization_id=org_id)
    assert len(invoices) >= 1
    assert invoices[0]["status"] in ["paid", "free_tier"]
    assert invoices[0]["amount_paid"] == 299.0

    # 6. Simulate Payment Failure Webhook (invoice.payment_failed)
    fail_payload = json.dumps({
        "type": "invoice.payment_failed",
        "data": {
            "object": {
                "id": "in_test_fail_123",
                "customer": "cus_test_123",
                "metadata": {"organization_id": str(org_id)}
            }
        }
    }).encode("utf-8")
    await StripeBillingClient.handle_webhook(fail_payload, sig_header="")

    async with async_session_scope() as session:
        res = await session.execute(select(Organization).where(Organization.id == org_id))
        org_past_due = res.scalar_one_or_none()
        assert org_past_due.settings.get("subscription_status") == "past_due"

    # 7. Simulate Subscription Deletion (customer.subscription.deleted)
    del_payload = json.dumps({
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_test_123",
                "metadata": {"organization_id": str(org_id)}
            }
        }
    }).encode("utf-8")
    await StripeBillingClient.handle_webhook(del_payload, sig_header="")

    async with async_session_scope() as session:
        res = await session.execute(select(Organization).where(Organization.id == org_id))
        org_canceled = res.scalar_one_or_none()
        assert org_canceled.plan == "free"
        assert org_canceled.settings.get("subscription_status") == "canceled"

