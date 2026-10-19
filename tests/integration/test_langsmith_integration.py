"""
Integration tests for LangSmith connection, agent tracing, multi-tenant tagging, and observability.
"""

import os
import uuid
import pytest
from unittest.mock import MagicMock, patch
from httpx import AsyncClient, ASGITransport

from apps.api.main import app
from packages.config.settings import settings
from packages.observability.langsmith_client import LangSmithManager, langsmith_manager
from packages.agents.graph.graph import run_erp_agent
from packages.auth.tokens import create_access_token
from packages.database.core import async_session_scope
from packages.database.models.user import User, OrganizationMember, UserStatus
from packages.database.models.organization import Organization


def test_langsmith_disabled_by_default():
    """Verifies that LangSmith manager is disabled with zero overhead when no key is set."""
    mgr = LangSmithManager()
    with patch.object(settings, "langchain_tracing_v2", False), \
         patch.object(settings, "langchain_api_key", None):
        assert mgr.is_enabled() is False
        assert mgr.get_client() is None
        assert mgr.get_tracing_callbacks() == []
        
        status = mgr.test_connection()
        assert status["status"] == "disabled"
        assert status["configured"] is False
        assert status["features"]["langgraph_tracing"] is False


def test_langsmith_environment_configuration():
    """Verifies environment variables are set when enabled and disabled cleanly."""
    mgr = LangSmithManager()
    
    # 1. Test enabled state
    with patch.object(settings, "langchain_tracing_v2", True), \
         patch.object(settings, "langchain_api_key", "lsv2_test_api_key_12345"), \
         patch.object(settings, "langchain_project", "Test-ERP-Project"), \
         patch.object(settings, "langchain_endpoint", "https://api.smith.langchain.com"):
        
        enabled = mgr.configure_tracing_environment()
        assert enabled is True
        assert os.environ.get("LANGCHAIN_TRACING_V2") == "true"
        assert os.environ.get("LANGCHAIN_API_KEY") == "lsv2_test_api_key_12345"
        assert os.environ.get("LANGCHAIN_PROJECT") == "Test-ERP-Project"
        assert os.environ.get("LANGCHAIN_ENDPOINT") == "https://api.smith.langchain.com"

    # 2. Test disabled cleanup
    with patch.object(settings, "langchain_tracing_v2", False), \
         patch.object(settings, "langchain_api_key", None):
        
        enabled = mgr.configure_tracing_environment()
        assert enabled is False
        assert os.environ.get("LANGCHAIN_TRACING_V2") == "false"


def test_langsmith_metadata_sanitization_and_pci_defense():
    """Ensures sensitive credit cards, CVVs, and secrets are sanitized from trace metadata."""
    mgr = LangSmithManager()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    config = mgr.get_graph_run_config(
        organization_id=org_id,
        user_id=user_id,
        user_role="admin",
        session_id="sess-xyz",
        extra_metadata={
            "customer_card": "4532-1234-5678-9012",
            "security_code": "CVV 888",
            "notes": "Payment authorization confirmed",
        }
    )

    metadata = config["metadata"]
    assert metadata["organization_id"] == str(org_id)
    assert metadata["user_id"] == str(user_id)
    assert metadata["user_role"] == "admin"
    assert metadata["session_id"] == "sess-xyz"
    # Credit card and CVV must be completely masked
    assert "4532" not in metadata["customer_card"]
    assert "[CREDIT_CARD_REDACTED]" in metadata["customer_card"]
    assert "888" not in metadata["security_code"]
    assert "[CVV_REDACTED]" in metadata["security_code"]
    assert metadata["notes"] == "Payment authorization confirmed"

    tags = config["tags"]
    assert "agentic-erp" in tags
    assert "role:admin" in tags
    assert "graph:erp_multi_agent" in tags


def test_langsmith_connection_diagnostic_mock():
    """Tests connection diagnostic when client succeeds and when an error is raised."""
    mgr = LangSmithManager()
    
    with patch.object(settings, "langchain_tracing_v2", True), \
         patch.object(settings, "langchain_api_key", "lsv2_valid_key_test"):
        
        # Case A: Success
        mock_client = MagicMock()
        mock_client.has_project.return_value = True
        with patch.object(mgr, "get_client", return_value=mock_client):
            res = mgr.test_connection()
            assert res["status"] == "connected"
            assert res["configured"] is True
            assert res["project_exists"] is True
            assert res["features"]["langgraph_tracing"] is True

        # Case B: Network/Auth Error
        mock_client = MagicMock()
        mock_client.has_project.side_effect = Exception("401 Unauthorized: Invalid LangSmith API Key")
        with patch.object(mgr, "get_client", return_value=mock_client):
            res = mgr.test_connection()
            assert res["status"] == "error"
            assert "401 Unauthorized" in res["message"]
            assert res["features"]["langgraph_tracing"] is False


@pytest.mark.asyncio
async def test_langsmith_observability_api_endpoints():
    """Tests compliance and agent observability status endpoints via HTTP."""
    org_id = uuid.uuid4()
    admin_id = uuid.uuid4()

    async with async_session_scope() as session:
        org = Organization(
            id=org_id,
            name=f"LangSmith Org {uuid.uuid4().hex[:6]}",
            slug=f"langsmith-{uuid.uuid4().hex[:8]}",
            plan="enterprise",
            status="active",
        )
        session.add(org)
        await session.flush()

        admin = User(
            id=admin_id,
            email=f"admin-{uuid.uuid4().hex[:6]}@example.com",
            first_name="Admin",
            last_name="Observability",
            full_name="Admin Observability",
            organization_id=org_id,
            is_active=True,
            is_verified=True,
            status=UserStatus.ACTIVE,
        )
        session.add(admin)
        await session.flush()
        session.add(OrganizationMember(organization_id=org_id, user_id=admin_id, role="admin"))
        await session.commit()

    admin_token = create_access_token(
        user_id=admin_id, org_id=org_id, role="admin", email=admin.email
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Test GET /api/v1/compliance/langsmith/status
        res = await client.get(
            "/api/v1/compliance/langsmith/status",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert "status" in data
        assert "project" in data
        assert "endpoint" in data
        assert data["tenant_id"] == str(org_id)

        # 2. Test GET /api/v1/compliance/observability
        res_obs = await client.get(
            "/api/v1/compliance/observability",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res_obs.status_code == 200
        assert res_obs.json()["status"] == data["status"]

        # 3. Test GET /api/v1/agents/observability/status
        res_agents = await client.get(
            "/api/v1/agents/observability/status",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res_agents.status_code == 200
        agents_data = res_agents.json()
        assert "status" in agents_data
        assert "features" in agents_data


@pytest.mark.asyncio
async def test_run_erp_agent_with_langsmith_config():
    """Verifies run_erp_agent executes seamlessly with LangSmith configuration attached."""
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # Execute general query
    result = await run_erp_agent(
        organization_id=org_id,
        user_id=user_id,
        user_role="admin",
        prompt="Show system overview and status",
        session_id="test-session-123",
    )

    assert "response" in result
    assert result["tokens_used"] > 0
    assert "latency_ms" in result
    assert result["routed_to"] in [
        "inventory_agent", "sales_agent", "purchasing_agent",
        "finance_agent", "general_agent"
    ]
