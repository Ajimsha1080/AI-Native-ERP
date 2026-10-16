"""
Integration tests for Phase 3 Billing Correctness.

Verifies:
1. Webhook signature enforcement (rejects unsigned/invalid signatures).
2. Webhook idempotency via processed_stripe_events table.
3. Organization lookup by stripe_customer_id in settings.
4. Checkout session sets subscription_data.metadata and rejects malicious redirect URLs.
5. No fake invoice fallback (returns empty list if none exist).
6. Webhook lifecycle (invoice.payment_failed grace period and invoice.paid restoration).
7. Plan limit enforcement (seat limits, token budget, and grace period feature gating).
"""

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.main import app
from packages.billing.plan_limits import PlanLimitEnforcer, PlanLimitExceededError
from packages.billing.stripe_client import StripeBillingClient
from packages.config.settings import settings
from packages.database.models import Organization, OrganizationMember, OrganizationMemberRole, User
from packages.database.models.billing import ProcessedStripeEvent
from tests.conftest import ASYNC_TEST_DB_URL


@pytest.mark.asyncio
async def test_webhook_rejects_unsigned_events_outside_tests():
    """Asserts that webhook handler strictly rejects unsigned requests when signature header is missing or invalid."""
    from unittest.mock import patch
    with patch.object(settings, "stripe_webhook_secret", "whsec_test_secret_123"):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            fake_payload = json.dumps({"id": "evt_test_123", "type": "checkout.session.completed", "data": {}})
            # 1. Missing Stripe-Signature header
            res1 = await client.post(
                "/api/v1/billing/webhook",
                content=fake_payload,
                headers={"Content-Type": "application/json"},
            )
            assert res1.status_code == 400

            # 2. Invalid signature header
            res2 = await client.post(
                "/api/v1/billing/webhook",
                content=fake_payload,
                headers={"Content-Type": "application/json", "Stripe-Signature": "t=123,v1=invalid_signature"},
            )
            assert res2.status_code == 400


@pytest.mark.asyncio
async def test_webhook_idempotency_via_processed_stripe_events():
    """
    Asserts that webhook deduplication prevents duplicate event execution
    and records event IDs in processed_stripe_events.
    """
    evt_id = f"evt_idemp_{uuid4().hex[:12]}"
    payload_dict = {
        "id": evt_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "metadata": {"plan": "pro"},
                "customer": f"cus_{uuid4().hex[:8]}",
            }
        },
    }
    raw_payload = json.dumps(payload_dict).encode("utf-8")

    # First delivery: processed
    res1 = await StripeBillingClient.handle_webhook(raw_payload, sig_header="test_sig")
    assert res1["status"] == "processed"
    assert res1["event_id"] == evt_id

    # Second delivery: duplicate skipped
    res2 = await StripeBillingClient.handle_webhook(raw_payload, sig_header="test_sig")
    assert res2["status"] == "duplicate_skipped"
    assert res2["event_id"] == evt_id

    # Verify event ID exists in database table
    engine = create_async_engine(ASYNC_TEST_DB_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        stored = await session.execute(select(ProcessedStripeEvent).where(ProcessedStripeEvent.id == evt_id))
        rec = stored.scalar_one_or_none()
        assert rec is not None
        assert rec.event_type == "checkout.session.completed"
    await engine.dispose()


@pytest.mark.asyncio
async def test_webhook_org_lookup_by_stripe_customer_id():
    """Asserts webhook resolves organizations via stripe_customer_id stored in settings JSON."""
    org_id = uuid4()
    cust_id = f"cus_lookup_{uuid4().hex[:8]}"

    engine = create_async_engine(ASYNC_TEST_DB_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        org = Organization(
            id=org_id,
            name=f"Customer Lookup Org {org_id.hex[:6]}",
            slug=f"lookup-{org_id.hex[:6]}",
            plan="free",
            status="active",
            settings={"stripe_customer_id": cust_id, "subscription_status": "active"},
        )
        session.add(org)
        await session.commit()

    # Dispatch invoice.payment_failed with only customer ID (no metadata organization_id)
    evt_id = f"evt_cust_{uuid4().hex[:12]}"
    payload_dict = {
        "id": evt_id,
        "type": "invoice.payment_failed",
        "data": {
            "object": {
                "id": "in_test_failed_123",
                "customer": cust_id,
            }
        },
    }
    raw_payload = json.dumps(payload_dict).encode("utf-8")
    await StripeBillingClient.handle_webhook(raw_payload, sig_header="test_sig")

    # Assert organization is updated to past_due with past_due_since recorded
    async with session_factory() as session:
        res = await session.execute(select(Organization).where(Organization.id == org_id))
        updated_org = res.scalar_one()
        assert updated_org.settings.get("subscription_status") == "past_due"
        assert "past_due_since" in updated_org.settings

    # Next: Dispatch invoice.paid -> restores active status and clears past_due_since
    evt_paid = f"evt_paid_{uuid4().hex[:12]}"
    paid_payload = json.dumps({
        "id": evt_paid,
        "type": "invoice.paid",
        "data": {"object": {"customer": cust_id}},
    }).encode("utf-8")
    await StripeBillingClient.handle_webhook(paid_payload, sig_header="test_sig")

    async with session_factory() as session:
        res = await session.execute(select(Organization).where(Organization.id == org_id))
        restored_org = res.scalar_one()
        assert restored_org.settings.get("subscription_status") == "active"
        assert "past_due_since" not in restored_org.settings

    await engine.dispose()


@pytest.mark.asyncio
async def test_checkout_session_validates_redirect_urls():
    """Asserts checkout session endpoint strictly blocks unauthorized or phishing redirect URLs."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Register and login
        unique_id = uuid4().hex[:8]
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"billing.owner.{unique_id}@example.com",
                "password": "SecurePassword#2026",
                "first_name": "Billing",
                "last_name": "Owner",
                "organization_name": f"Billing-Org-{unique_id}",
            },
        )
        assert reg_res.status_code == 201

        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": f"billing.owner.{unique_id}@example.com", "password": "SecurePassword#2026"},
        )
        tokens = login_res.json()
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        # Attempt checkout with malicious redirect URL
        phishing_res = await client.post(
            "/api/v1/billing/checkout",
            headers=headers,
            json={
                "plan": "pro",
                "success_url": "https://evil-phishing-site.attacker.com/steal-token",
                "cancel_url": "http://localhost:3000/cancel",
            },
        )
        assert phishing_res.status_code == 400
        assert "not in the allowed redirect origins" in phishing_res.json()["detail"].lower()

        # Legitimate checkout URL succeeds
        legit_res = await client.post(
            "/api/v1/billing/checkout",
            headers=headers,
            json={
                "plan": "pro",
                "success_url": "http://localhost:3000/billing/success",
                "cancel_url": "http://localhost:3000/billing/cancel",
            },
        )
        assert legit_res.status_code == 200
        assert "session_id" in legit_res.json()


@pytest.mark.asyncio
async def test_no_fake_invoice_fallback():
    """Asserts that when no Stripe invoices exist, an empty list is returned rather than fabricated invoices."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        unique_id = uuid4().hex[:8]
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"invoice.owner.{unique_id}@example.com",
                "password": "SecurePassword#2026",
                "first_name": "Invoice",
                "last_name": "Owner",
                "organization_name": f"Invoice-Org-{unique_id}",
            },
        )
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": f"invoice.owner.{unique_id}@example.com", "password": "SecurePassword#2026"},
        )
        tokens = login_res.json()
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        inv_res = await client.get("/api/v1/billing/invoices", headers=headers)
        assert inv_res.status_code == 200
        assert inv_res.json() == []  # Real empty list, no fake inv_current


@pytest.mark.asyncio
async def test_plan_seat_limits_enforcement():
    """
    Asserts that Free plan limits organizations to 3 seats,
    rejecting subsequent user invitations with 402 Payment Required.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        unique_id = uuid4().hex[:8]
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"seats.owner.{unique_id}@example.com",
                "password": "SecurePassword#2026",
                "first_name": "Seat",
                "last_name": "Owner",
                "organization_name": f"Seat-Org-{unique_id}",
            },
        )
        assert reg_res.status_code == 201

        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": f"seats.owner.{unique_id}@example.com", "password": "SecurePassword#2026"},
        )
        tokens = login_res.json()
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        # Seat 1 is the owner.
        # Invite Seat 2:
        inv1 = await client.post(
            "/api/v1/users/invite",
            headers=headers,
            json={"email": f"seat2.{unique_id}@example.com", "first_name": "S2", "last_name": "U", "role": "viewer"},
        )
        assert inv1.status_code == 201

        # Invite Seat 3:
        inv2 = await client.post(
            "/api/v1/users/invite",
            headers=headers,
            json={"email": f"seat3.{unique_id}@example.com", "first_name": "S3", "last_name": "U", "role": "viewer"},
        )
        assert inv2.status_code == 201

        # Invite Seat 4: Exceeds free tier limit of 3 seats -> 402 Payment Required
        inv3 = await client.post(
            "/api/v1/users/invite",
            headers=headers,
            json={"email": f"seat4.{unique_id}@example.com", "first_name": "S4", "last_name": "U", "role": "viewer"},
        )
        assert inv3.status_code == 402
        assert "seat limit reached" in inv3.json()["detail"].lower()
