"""
Integration tests for GDPR data export, account deletion, and audit trail tracking.
"""

import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from apps.api.main import app
from packages.auth.tokens import create_access_token
from packages.database.core import async_session_scope
from packages.database.models.user import User, OrganizationMember, UserStatus
from packages.database.models.organization import Organization
from packages.database.models.audit import AuditEvent


@pytest.mark.asyncio
async def test_gdpr_export_and_account_deletion_flow():
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    owner_id = uuid.uuid4()

    async with async_session_scope() as session:
        # Create organization
        org = Organization(
            id=org_id,
            name=f"GDPR Test Org {uuid.uuid4().hex[:6]}",
            slug=f"gdpr-{uuid.uuid4().hex[:8]}",
            plan="pro",
            status="active",
        )
        session.add(org)
        await session.flush()

        # Create primary owner
        owner = User(
            id=owner_id,
            email=f"owner-{uuid.uuid4().hex[:6]}@example.com",
            first_name="Primary",
            last_name="Owner",
            full_name="Primary Owner",
            organization_id=org_id,
            is_active=True,
            is_verified=True,
            status=UserStatus.ACTIVE,
        )
        session.add(owner)
        await session.flush()
        session.add(OrganizationMember(organization_id=org_id, user_id=owner_id, role="owner"))

        # Create member user to test export & self-deletion
        user = User(
            id=user_id,
            email=f"gdpr-user-{uuid.uuid4().hex[:6]}@example.com",
            first_name="Jane",
            last_name="Doe",
            full_name="Jane Doe",
            organization_id=org_id,
            is_active=True,
            is_verified=True,
            status=UserStatus.ACTIVE,
        )
        session.add(user)
        await session.flush()
        session.add(OrganizationMember(organization_id=org_id, user_id=user_id, role="viewer"))
        await session.commit()

    user_token = create_access_token(
        user_id=user_id, org_id=org_id, role="viewer", email=user.email
    )
    owner_token = create_access_token(
        user_id=owner_id, org_id=org_id, role="owner", email=owner.email
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Test GET /api/v1/users/me/export
        res_export = await client.get(
            "/api/v1/users/me/export",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert res_export.status_code == 200
        export_data = res_export.json()
        assert export_data["personal_data"]["email"] == user.email
        assert export_data["personal_data"]["first_name"] == "Jane"
        assert len(export_data["organization_memberships"]) >= 1
        assert "export_timestamp" in export_data

        # 2. Test GET /api/v1/organizations/{id}/export (Owner only)
        res_org_export = await client.get(
            f"/api/v1/organizations/{org_id}/export",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert res_org_export.status_code == 200
        org_data = res_org_export.json()
        assert org_data["organization"]["id"] == str(org_id)

        # 3. Test DELETE /api/v1/users/me (GDPR Right to be Forgotten)
        res_del_me = await client.delete(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert res_del_me.status_code == 200
        assert "anonymized under GDPR" in res_del_me.json()["message"]

        # Verify DB state of anonymized user
        async with async_session_scope() as session:
            check_res = await session.execute(select(User).where(User.id == user_id))
            updated_user = check_res.scalar_one()
            assert updated_user.is_active is False
            assert updated_user.first_name == "Anonymized"
            assert "deleted.local" in updated_user.email
            assert updated_user.password_hash == "DELETED"

            # Check that an audit log record was created
            audit_res = await session.execute(
                select(AuditEvent).where(AuditEvent.user_id == user_id)
            )
            audit_record = audit_res.scalar_one_or_none()
            assert audit_record is not None
            assert "GDPR" in audit_record.event_name
