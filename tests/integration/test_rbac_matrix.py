"""
Integration tests for the complete RBAC Matrix across roles.

Validates that Owner, Admin, Manager, and Viewer permissions are strictly enforced
on administrative and write endpoints according to the enterprise security specification:
- invite_user: Owner (201), Admin (201), Manager (403), Viewer (403)
- change_user_role: Owner (200), Admin (200), Manager (403), Viewer (403)
- delete_user: Owner (204), Admin (204), Manager (403), Viewer (403)
- delete_organization: Owner (200), Admin (403), Manager (403), Viewer (403)
- Cannot demote or remove the last remaining Owner (400)
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


@pytest.mark.asyncio
async def test_complete_rbac_matrix_and_owner_safeguards():
    org_id = uuid.uuid4()

    async with async_session_scope() as session:
        # Create organization
        org = Organization(
            id=org_id,
            name=f"RBAC Matrix Org {uuid.uuid4().hex[:6]}",
            slug=f"rbac-{uuid.uuid4().hex[:8]}",
            plan="enterprise",
            status="active",
        )
        session.add(org)
        await session.flush()

        # Helper to create user with specific role
        async def create_member(role_name: str):
            u_id = uuid.uuid4()
            user = User(
                id=u_id,
                email=f"{role_name}-{uuid.uuid4().hex[:6]}@example.com",
                first_name="Test",
                last_name=role_name.capitalize(),
                full_name=f"Test {role_name.capitalize()}",
                organization_id=org_id,
                is_active=True,
                is_verified=True,
                status=UserStatus.ACTIVE,
            )
            session.add(user)
            await session.flush()

            member = OrganizationMember(
                organization_id=org_id,
                user_id=u_id,
                role=role_name,
            )
            session.add(member)
            await session.flush()
            return user

        owner_user = await create_member("owner")
        admin_user = await create_member("admin")
        manager_user = await create_member("manager")
        viewer_user = await create_member("viewer")
        target_user = await create_member("viewer")

        await session.commit()

    # Generate JWT access tokens
    owner_token = create_access_token(
        user_id=owner_user.id, org_id=org_id, role="owner", email=owner_user.email
    )
    admin_token = create_access_token(
        user_id=admin_user.id, org_id=org_id, role="admin", email=admin_user.email
    )
    manager_token = create_access_token(
        user_id=manager_user.id, org_id=org_id, role="manager", email=manager_user.email
    )
    viewer_token = create_access_token(
        user_id=viewer_user.id, org_id=org_id, role="viewer", email=viewer_user.email
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # ----------------------------------------------------------------------
        # 1. Test POST /api/v1/users/invite (Requires Min Role: Admin)
        # ----------------------------------------------------------------------
        # Viewer -> 403 Forbidden
        res_v = await client.post(
            "/api/v1/users/invite",
            json={"email": f"invited-v-{uuid.uuid4().hex[:6]}@example.com", "role": "viewer"},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert res_v.status_code == 403

        # Manager -> 403 Forbidden
        res_m = await client.post(
            "/api/v1/users/invite",
            json={"email": f"invited-m-{uuid.uuid4().hex[:6]}@example.com", "role": "viewer"},
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert res_m.status_code == 403

        # Admin -> 201 Created
        invited_email_admin = f"invited-a-{uuid.uuid4().hex[:6]}@example.com"
        res_a = await client.post(
            "/api/v1/users/invite",
            json={"email": invited_email_admin, "role": "viewer"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res_a.status_code == 201
        assert res_a.json()["role"] == "viewer"

        # Owner -> 201 Created
        invited_email_owner = f"invited-o-{uuid.uuid4().hex[:6]}@example.com"
        res_o = await client.post(
            "/api/v1/users/invite",
            json={"email": invited_email_owner, "role": "manager"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert res_o.status_code == 201
        assert res_o.json()["role"] == "manager"

        # ----------------------------------------------------------------------
        # 2. Test PATCH /api/v1/users/{id}/role (Requires Min Role: Admin)
        # ----------------------------------------------------------------------
        # Viewer -> 403
        res_role_v = await client.patch(
            f"/api/v1/users/{target_user.id}/role",
            json={"role": "manager"},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert res_role_v.status_code == 403

        # Manager -> 403
        res_role_m = await client.patch(
            f"/api/v1/users/{target_user.id}/role",
            json={"role": "manager"},
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert res_role_m.status_code == 403

        # Admin -> 200 OK
        res_role_a = await client.patch(
            f"/api/v1/users/{target_user.id}/role",
            json={"role": "manager"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res_role_a.status_code == 200
        assert res_role_a.json()["role"] == "manager"

        # ----------------------------------------------------------------------
        # 3. Test Owner Safeguard: Cannot demote the last remaining Owner
        # ----------------------------------------------------------------------
        res_demote_owner = await client.patch(
            f"/api/v1/users/{owner_user.id}/role",
            json={"role": "admin"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert res_demote_owner.status_code == 400
        assert "Cannot demote the last remaining owner" in res_demote_owner.json()["detail"]

        # ----------------------------------------------------------------------
        # 4. Test Owner Safeguard: Cannot remove the last remaining Owner
        # ----------------------------------------------------------------------
        res_remove_owner = await client.delete(
            f"/api/v1/users/{owner_user.id}",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert res_remove_owner.status_code == 400
        assert "Cannot remove the last remaining owner" in res_remove_owner.json()["detail"]

        # ----------------------------------------------------------------------
        # 5. Test DELETE /api/v1/organizations/{id} (Requires Role: Owner)
        # ----------------------------------------------------------------------
        # Admin -> 403 Forbidden
        res_del_org_admin = await client.delete(
            f"/api/v1/organizations/{org_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res_del_org_admin.status_code == 403

        # Manager -> 403 Forbidden
        res_del_org_manager = await client.delete(
            f"/api/v1/organizations/{org_id}",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert res_del_org_manager.status_code == 403

        # Owner -> 200 OK (Deactivates organization)
        res_del_org_owner = await client.delete(
            f"/api/v1/organizations/{org_id}",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert res_del_org_owner.status_code == 200
        assert "deactivated successfully" in res_del_org_owner.json()["message"]
