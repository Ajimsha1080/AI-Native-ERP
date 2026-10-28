"""
Phase 7 Integration Tests: Billing Hardening and Worker Health Diagnostics.

Verifies:
1. Removal of mock billing fallback URLs (including `?portal=mock`) in non-test environments;
   behaving identically across dev, staging, and production when keys are missing (503 Service Unavailable).
2. Health check task: real DB check with failure path verification.
3. Health check task: real Redis and Celery queue depth checks with failure path verification.
4. Health check task: real LLM provider probe with failure path verification.
5. Health check task: real Stripe probe with failure path verification.
"""

import pytest
import uuid
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from httpx import AsyncClient, ASGITransport

from packages.config.settings import settings
from packages.billing.stripe_client import StripeBillingClient
from apps.worker.tasks.health import (
    check_system_health_task,
    _check_database_health,
    _check_external_services
)
from apps.api.main import app


@pytest.mark.asyncio
async def test_billing_checkout_fails_fast_outside_test_environment_without_key():
    """Verifies that checkout refuses mock session creation outside testing and raises 503."""
    org_id = uuid.uuid4()

    # In production/staging/dev without stripe_secret_key: must fail clearly with 503
    for env in ("production", "staging", "development"):
        with patch.object(settings, "environment", env):
            with patch.object(settings, "stripe_secret_key", ""):
                with pytest.raises(HTTPException) as exc_info:
                    await StripeBillingClient.create_checkout_session(
                        organization_id=org_id,
                        plan="pro",
                        success_url="http://localhost:3000/billing/success",
                        cancel_url="http://localhost:3000/billing/cancel",
                    )
                assert exc_info.value.status_code == 503
                assert "STRIPE_SECRET_KEY is required" in exc_info.value.detail


@pytest.mark.asyncio
async def test_billing_portal_fails_fast_outside_test_environment_without_key():
    """Verifies that portal refuses mock URL (?portal=mock) outside testing and raises 503."""
    org_id = uuid.uuid4()

    for env in ("production", "staging", "development"):
        with patch.object(settings, "environment", env):
            with patch.object(settings, "stripe_secret_key", ""):
                with pytest.raises(HTTPException) as exc_info:
                    await StripeBillingClient.create_portal_session(
                        organization_id=org_id,
                        return_url="http://localhost:3000/billing",
                    )
                assert exc_info.value.status_code == 503
                assert "STRIPE_SECRET_KEY is required" in exc_info.value.detail


@pytest.mark.asyncio
async def test_worker_database_health_failure_path():
    """Verifies real database health check failure handling."""
    # Simulate DB session connection failure
    with patch("packages.database.core.AsyncSessionLocal") as mock_session_cls:
        mock_session_cls.side_effect = ConnectionRefusedError("PostgreSQL connection refused on port 5432")
        result = await _check_database_health()
        assert result["status"] == "unhealthy"
        assert "Database connection failed" in result["issues"][0]
        assert "checks" in result


@pytest.mark.asyncio
async def test_worker_redis_and_queue_depth_failure_path():
    """Verifies real Redis failure path in worker health diagnostics."""
    with patch("redis.from_url") as mock_redis_from_url:
        mock_r = MagicMock()
        mock_r.ping.side_effect = ConnectionError("Redis host unreachable at redis://localhost:6379")
        mock_redis_from_url.return_value = mock_r

        result = await _check_external_services()
        assert result["services"]["redis"]["status"] == "unhealthy"
        assert result["services"]["queue_depth"]["status"] == "unhealthy"
        assert any("Redis connection failed" in issue for issue in result["issues"])


@pytest.mark.asyncio
async def test_worker_queue_depth_real_check():
    """Verifies real queue depth inspection when Redis is reachable."""
    with patch("redis.from_url") as mock_redis_from_url:
        mock_r = MagicMock()
        mock_r.ping.return_value = True
        mock_r.llen.return_value = 42
        mock_redis_from_url.return_value = mock_r

        result = await _check_external_services()
        assert result["services"]["redis"]["status"] == "healthy"
        assert result["services"]["queue_depth"]["status"] == "healthy"
        assert result["services"]["queue_depth"]["depth"] == 42


@pytest.mark.asyncio
async def test_worker_llm_provider_reachability_failure_path():
    """Verifies real failure path when LLM provider returns error response."""
    with patch.object(settings, "openai_api_key", "sk-proj-test-key"):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized: Invalid API key"

        with patch("requests.get", return_value=mock_resp):
            result = await _check_external_services()
            assert result["services"]["llm_provider"]["status"] == "unhealthy"
            assert "HTTP 401" in result["services"]["llm_provider"]["error"]
            assert any("LLM provider check failed" in issue for issue in result["issues"])


@pytest.mark.asyncio
async def test_worker_stripe_reachability_failure_path():
    """Verifies real failure path when Stripe API returns error response."""
    with patch.object(settings, "stripe_secret_key", "rk_live_testsecretkey"):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Invalid API Key provided"

        with patch("requests.get", return_value=mock_resp):
            result = await _check_external_services()
            assert result["services"]["stripe"]["status"] == "unhealthy"
            assert "HTTP 401" in result["services"]["stripe"]["error"]
            assert any("Stripe API authentication failed" in issue for issue in result["issues"])
