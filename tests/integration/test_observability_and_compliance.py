"""
Integration tests for Observability, Metrics, and GDPR Compliance.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from uuid import uuid4
from datetime import datetime, timezone

from apps.api.main import app
from packages.database.core import async_session_scope, create_db_and_tables
from packages.database.tenant_context import set_tenant_context
from packages.database.models import Organization, User, UserStatus, AuditEvent, AuditEventType
from packages.database.models.erp.inventory import Product
from packages.auth.tokens import create_access_token



@pytest.mark.asyncio
async def test_observability_endpoints_and_prometheus_metrics():
    await create_db_and_tables()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Test Health & Readiness
        res_health = await client.get("/health")
        assert res_health.status_code == 200
        assert res_health.json()["status"] == "healthy"

        res_ready = await client.get("/ready")
        assert res_ready.status_code == 200
        assert res_ready.json()["status"] == "ready"

        # 2. Test Prometheus Metrics Endpoint
        res_metrics = await client.get("/metrics")
        assert res_metrics.status_code == 200
        metrics_text = res_metrics.text
        assert "http_requests_total" in metrics_text
        assert "http_request_duration_seconds" in metrics_text


@pytest.mark.asyncio
async def test_gdpr_data_export_and_account_deletion_flow():
    await create_db_and_tables()
    org_id = uuid4()
    user_id = uuid4()

    async with async_session_scope() as session:
        await set_tenant_context(session, org_id)

        org = Organization(
            id=org_id,
            name="Compliance Tenant Corp",
            slug=f"comp-{uuid4().hex[:6]}",
            plan="enterprise",
            status="active"
        )
        user = User(
            id=user_id,
            tenant_id=org_id,
            email=f"compliance-officer-{uuid4().hex[:4]}@tenant.com",
            first_name="Eleanor",
            last_name="Vane",
            status=UserStatus.ACTIVE,
            is_active=True,
        )
        item = Product(
            organization_id=org_id,
            sku="SKU-GDPR-TEST",
            name="GDPR Sensitive Asset",
            unit_price=120.0
        )
        session.add_all([org, user, item])
        await session.commit()

    token = create_access_token(
        user_id=user_id,
        org_id=org_id,
        role="owner"
    )
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Test GDPR Data Export (Article 20)
        res_export = await client.get("/api/v1/compliance/export", headers=headers)
        assert res_export.status_code == 200
        data = res_export.json()
        assert data["organization"]["name"] == "Compliance Tenant Corp"
        assert len(data["users"]) >= 1
        assert len(data["products"]) >= 1
        assert data["export_metadata"]["compliance_standard"] == "GDPR Article 20 (Data Portability)"

        # 2. Test Audit Trail Export in JSON & CSV
        res_audit_json = await client.get("/api/v1/compliance/audit-export?format=json", headers=headers)
        assert res_audit_json.status_code == 200
        assert isinstance(res_audit_json.json(), list)

        res_audit_csv = await client.get("/api/v1/compliance/audit-export?format=csv", headers=headers)
        assert res_audit_csv.status_code == 200
        assert "text/csv" in res_audit_csv.headers["content-type"]
        assert "Event Type" in res_audit_csv.text

        # 3. Test GDPR Right to Erasure / Deletion confirmation requirement
        res_bad_del = await client.post("/api/v1/compliance/delete-account?confirm_text=WRONG", headers=headers)
        assert res_bad_del.status_code == 400

        res_del = await client.post("/api/v1/compliance/delete-account?confirm_text=DELETE-MY-DATA", headers=headers)
        assert res_del.status_code == 200
        assert res_del.json()["status"] == "success"

    # 4. Verify Organization Status updated to archived
    async with async_session_scope() as session:
        from sqlalchemy import select
        res = await session.execute(select(Organization).where(Organization.id == org_id))
        archived_org = res.scalar_one_or_none()
        assert archived_org.status == "archived"
