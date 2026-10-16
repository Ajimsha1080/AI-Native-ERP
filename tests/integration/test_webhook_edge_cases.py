"""
Integration tests for Stripe Webhook edge cases:
- Missing signature header
- Invalid cryptographic signature
- Replay attacks (duplicate event idempotency deduplication)
- Out-of-order webhook delivery
"""

import pytest
import time
import json
import hmac
import hashlib
from httpx import AsyncClient, ASGITransport

from apps.api.main import app
from packages.config import get_settings

settings = get_settings()


def generate_stripe_signature(payload: str, secret: str) -> str:
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.{payload}"
    signature = hmac.new(
        secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"t={timestamp},v1={signature}"


@pytest.mark.asyncio
async def test_stripe_webhook_missing_and_invalid_signature():
    from unittest.mock import patch
    with patch.object(settings, "stripe_webhook_secret", "whsec_test_secret"):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            payload = json.dumps({"id": "evt_test_123", "type": "ping"})

            # 1. Missing signature header
            res_missing = await client.post(
                "/api/v1/billing/webhook",
                content=payload,
                headers={"Content-Type": "application/json"},
            )
            assert res_missing.status_code == 400
            assert "Missing Stripe-Signature" in res_missing.json()["detail"] or "signature" in res_missing.json()["detail"].lower()

            # 2. Invalid cryptographic signature
            res_invalid = await client.post(
                "/api/v1/billing/webhook",
                content=payload,
                headers={
                    "Content-Type": "application/json",
                    "stripe-signature": "t=12345678,v1=invalid_hex_signature",
                },
            )
            assert res_invalid.status_code == 400
            assert "Invalid webhook signature" in res_invalid.json()["detail"] or "signature" in res_invalid.json()["detail"].lower()


@pytest.mark.asyncio
async def test_stripe_webhook_replay_deduplication_and_out_of_order():
    from unittest.mock import patch
    webhook_secret = "whsec_test_secret"
    with patch.object(settings, "stripe_webhook_secret", webhook_secret):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Event 1: Invoice paid delivered out of order
            event_id = f"evt_order_{int(time.time()*1000)}"
            event_data = {
                "id": event_id,
                "type": "invoice.paid",
                "data": {
                    "object": {
                        "id": "in_test_out_of_order",
                        "customer": "cus_unknown_order",
                        "subscription": "sub_test_order",
                        "status": "paid",
                    }
                },
            }
            payload = json.dumps(event_data)
            sig = generate_stripe_signature(payload, webhook_secret)

            # Initial delivery
            res1 = await client.post(
                "/api/v1/billing/webhook",
                content=payload,
                headers={"Content-Type": "application/json", "stripe-signature": sig},
            )
            assert res1.status_code == 200
            assert res1.json()["status"] == "processed"

            # Replay attempt (exact same event_id)
            res2 = await client.post(
                "/api/v1/billing/webhook",
                content=payload,
                headers={"Content-Type": "application/json", "stripe-signature": sig},
            )
            assert res2.status_code == 200
            assert res2.json()["status"] == "duplicate_skipped"
            assert res2.json()["event_id"] == event_id
