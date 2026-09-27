import pytest
from uuid import uuid4
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from packages.config.settings import Settings, settings
from packages.billing.stripe_client import StripeBillingClient, validate_stripe_configuration
from apps.api.main import app, lifespan


def test_settings_fails_fast_in_production_without_stripe_key():
    """Asserts that Settings model validation rejects production mode without a Stripe key."""
    with pytest.raises(ValueError) as exc_info:
        Settings(
            environment="production",
            secret_key="a" * 32,
            stripe_secret_key="",
            show_errors_in_browser=False
        )
    assert "stripe_secret_key" in str(exc_info.value).lower() or "fatal stripe configuration" in str(exc_info.value).lower()


def test_validate_stripe_configuration_fails_in_production():
    """Asserts that validate_stripe_configuration() raises a RuntimeError in production without Stripe key."""
    with patch.object(settings, "environment", "production"), \
         patch.object(settings, "stripe_secret_key", ""):
        with pytest.raises(RuntimeError) as exc_info:
            validate_stripe_configuration()
        assert "stripe_secret_key" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_lifespan_refuses_to_start_in_production_without_stripe_key():
    """Asserts that the FastAPI app lifespan fails fast during startup in production if Stripe key is missing."""
    with patch.object(settings, "environment", "production"), \
         patch.object(settings, "stripe_secret_key", ""):
        with pytest.raises(RuntimeError) as exc_info:
            async with lifespan(app):
                pass
        assert "stripe_secret_key" in str(exc_info.value).lower()


def test_mock_checkout_session_active_in_test_environment_with_alerts():
    """Asserts mock fallback works in test/development environment and emits structlog warning and Sentry alert."""
    org_id = uuid4()

    mock_logger = MagicMock()
    with patch.object(settings, "environment", "test"), \
         patch.object(settings, "stripe_secret_key", ""), \
         patch("packages.billing.stripe_client.struct_logger", mock_logger), \
         patch("sentry_sdk.capture_message") as mock_sentry_capture:

        session_data = StripeBillingClient.create_checkout_session(
            organization_id=org_id,
            plan="pro",
            success_url="http://localhost:3000/billing/success",
            cancel_url="http://localhost:3000/billing/cancel",
        )

        assert f"mock_session_{org_id}" in session_data["session_id"]
        assert "http://localhost:3000/billing/success?session_id=mock_session_" in session_data["url"]
        
        # Verify structlog alert
        mock_logger.warning.assert_called_once()
        
        # Verify Sentry alert
        mock_sentry_capture.assert_called_once()
        args, kwargs = mock_sentry_capture.call_args
        assert "Mock Stripe billing mode active" in args[0]
        assert kwargs.get("level") == "warning"


def test_checkout_session_refuses_mock_in_unauthorized_environment():
    """Asserts create_checkout_session raises RuntimeError in non-development/test environment without key."""
    org_id = uuid4()

    with patch.object(settings, "environment", "staging"), \
         patch.object(settings, "stripe_secret_key", ""):
        with pytest.raises(RuntimeError) as exc_info:
            StripeBillingClient.create_checkout_session(
                organization_id=org_id,
                plan="enterprise"
            )
        assert "disabled in 'staging' environment" in str(exc_info.value) or "mandatory" in str(exc_info.value).lower()


def test_real_checkout_session_with_stripe_key():
    """Asserts create_checkout_session calls Stripe API when secret key is provided."""
    org_id = uuid4()

    with patch.object(settings, "stripe_secret_key", "sk_test_1234567890"), \
         patch("stripe.checkout.Session.create") as mock_session_create:
        
        mock_session_obj = MagicMock()
        mock_session_obj.id = "cs_live_test_123"
        mock_session_obj.url = "https://checkout.stripe.com/pay/cs_live_test_123"
        mock_session_create.return_value = mock_session_obj

        result = StripeBillingClient.create_checkout_session(
            organization_id=org_id,
            plan="pro",
            success_url="http://localhost:3000/billing/success",
            cancel_url="http://localhost:3000/billing/cancel"
        )

        assert result["session_id"] == "cs_live_test_123"
        assert result["url"] == "https://checkout.stripe.com/pay/cs_live_test_123"
        mock_session_create.assert_called_once()
