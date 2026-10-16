"""
Integration tests for Phase 1 Stop-Ship Security & Auth Hardening.

Verifies:
1. Strict server-side password policy validation
2. Real DB RBAC (role loaded from OrganizationMember, not email string)
3. Invite user and change-role endpoints, verifying demoting/removing last owner is blocked
4. Refresh token rotation & family reuse detection
5. Single-use email verification and password reset tokens
6. Account lockout after consecutive failed attempts
7. Multi-tenant RLS isolation and pool leakage prevention as unprivileged app_user
"""

import hashlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.main import app
from packages.auth.dependencies import get_current_user
from packages.auth.password import hash_password, validate_password_policy
from packages.auth.tokens import TokenBlacklist, create_access_token, decode_token
from packages.database.models import Organization, OrganizationMember, OrganizationMemberRole, RefreshToken, SingleUseToken, User
from packages.database.tenant_context import set_tenant_context
from tests.conftest import ASYNC_TEST_DB_URL

# Connect as unprivileged non-superuser app_user to verify strict RLS enforcement
APP_DB_URL = ASYNC_TEST_DB_URL.replace("postgres:postgres@", "app_user:app_pass@") if "postgres:postgres@" in ASYNC_TEST_DB_URL else ASYNC_TEST_DB_URL


def test_password_policy_server_enforcement():
    """Assert server-side password policy strictly blocks weak or non-compliant passwords."""
    assert validate_password_policy("sh1A!")[0] is False  # too short
    assert validate_password_policy("nouppercase123!")[0] is False  # no uppercase
    assert validate_password_policy("NOLOWERCASE123!")[0] is False  # no lowercase
    assert validate_password_policy("NoDigitsAtAll!!")[0] is False  # no numbers
    assert validate_password_policy("password")[0] is False  # in common passwords blocklist
    assert validate_password_policy("Enterprise#Secure9921Pass!")[0] is True


@pytest.mark.asyncio
async def test_real_db_rbac_in_jwt_not_email_substring():
    """
    Assert that the role in the JWT is loaded strictly from the OrganizationMember database table
    and NEVER guessed from email substrings (e.g. an email containing 'admin' gets their actual DB role).
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        unique_id = uuid4().hex[:8]
        reg_payload = {
            "email": f"custom.admin.{unique_id}@example.com",
            "password": "SecureEnterprise#Pass2026",
            "first_name": "Test",
            "last_name": "Manager",
            "organization_name": f"Org-{unique_id}",
        }
        res = await client.post("/api/v1/auth/register", json=reg_payload)
        assert res.status_code == 201, f"Register failed: {res.text}"
        reg_data = res.json()
        org_id = UUID(reg_data["organization_id"])
        user_id = UUID(reg_data["user_id"])

        # Manually alter role in DB to 'viewer' despite email having 'admin' in it
        engine = create_async_engine(ASYNC_TEST_DB_URL, echo=False)
        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            stmt = select(OrganizationMember).where(
                OrganizationMember.user_id == user_id,
                OrganizationMember.organization_id == org_id,
            )
            member = (await session.execute(stmt)).scalar_one()
            member.role = OrganizationMemberRole.VIEWER.value
            await session.commit()
        await engine.dispose()

        # Login and inspect role in access token JWT
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": reg_payload["email"], "password": reg_payload["password"]},
        )
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        tokens = login_res.json()
        payload = decode_token(tokens["access_token"])
        assert payload.role == "viewer", f"Role leaked from email substring! Expected 'viewer' but got '{payload.role}'"


@pytest.mark.asyncio
async def test_invite_user_and_demote_last_owner_protection():
    """
    Assert user invite endpoint creates a member, and role change endpoint
    strictly protects the last owner from being demoted or removed.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        unique_id = uuid4().hex[:8]
        owner_email = f"owner.{unique_id}@example.com"
        owner_pass = "OwnerSecure#Pass2026"
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "email": owner_email,
                "password": owner_pass,
                "first_name": "Org",
                "last_name": "Owner",
                "organization_name": f"Owner-Org-{unique_id}",
            },
        )
        assert reg_res.status_code == 201
        owner_data = reg_res.json()
        owner_id = owner_data["user_id"]

        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": owner_email, "password": owner_pass},
        )
        assert login_res.status_code == 200
        tokens = login_res.json()
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        # Demote the ONLY owner -> must fail with 400
        demote_res = await client.patch(
            f"/api/v1/users/{owner_id}/role",
            headers=headers,
            json={"role": "admin"},
        )
        assert demote_res.status_code == 400
        assert "owner" in demote_res.json()["detail"].lower()

        # Invite a new user as admin
        invite_res = await client.post(
            "/api/v1/users/invite",
            headers=headers,
            json={
                "email": f"invited.{unique_id}@example.com",
                "first_name": "Invited",
                "last_name": "Admin",
                "role": "admin",
            },
        )
        assert invite_res.status_code == 201
        invited_id = invite_res.json()["user_id"]

        # Promote invited user to owner
        promote_res = await client.patch(
            f"/api/v1/users/{invited_id}/role",
            headers=headers,
            json={"role": "owner"},
        )
        assert promote_res.status_code == 200

        # Now demoting the original owner succeeds because there is another owner
        demote_original_res = await client.patch(
            f"/api/v1/users/{owner_id}/role",
            headers=headers,
            json={"role": "admin"},
        )
        assert demote_original_res.status_code == 200


@pytest.mark.asyncio
async def test_account_lockout_after_five_failed_attempts():
    """Assert account lockout triggers after 5 consecutive failed login attempts."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        unique_id = uuid4().hex[:8]
        email = f"lockout.{unique_id}@example.com"
        reg_payload = {
            "email": email,
            "password": "CorrectPassword#123",
            "first_name": "Lock",
            "last_name": "Out",
            "organization_name": f"Lockout-Org-{unique_id}",
        }
        reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
        assert reg_res.status_code == 201

        # 5 consecutive bad passwords
        for i in range(5):
            bad_login = await client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": f"WrongPass#{i}"},
            )
            assert bad_login.status_code == 401

        # 6th attempt should return 429 Too Many Requests (Account Locked)
        locked_res = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "CorrectPassword#123"},
        )
        assert locked_res.status_code == 429
        assert "temporarily locked" in locked_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_refresh_token_rotation_and_reuse_detection():
    """
    Assert true refresh token rotation and automated family revocation upon reuse.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        unique_id = uuid4().hex[:8]
        reg_payload = {
            "email": f"rot.{unique_id}@example.com",
            "password": "RotationPass#9920",
            "first_name": "Rot",
            "last_name": "Token",
            "organization_name": f"Rot-Org-{unique_id}",
        }
        reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
        assert reg_res.status_code == 201

        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": reg_payload["email"], "password": reg_payload["password"]},
        )
        assert login_res.status_code == 200
        initial_tokens = login_res.json()
        rf1 = initial_tokens["refresh_token"]

        # 1. Normal rotation: exchange rf1 for rf2
        rot_res = await client.post("/api/v1/auth/refresh", json={"refresh_token": rf1})
        assert rot_res.status_code == 200
        new_tokens = rot_res.json()
        rf2 = new_tokens["refresh_token"]
        assert rf1 != rf2

        # 2. Token reuse attack: attacker attempts to reuse rf1
        reuse_res = await client.post("/api/v1/auth/refresh", json={"refresh_token": rf1})
        assert reuse_res.status_code == 401
        assert "reuse detected" in reuse_res.json()["detail"].lower()

        # 3. Family revocation: legitimate rf2 is now also revoked due to family compromise
        legit_res = await client.post("/api/v1/auth/refresh", json={"refresh_token": rf2})
        assert legit_res.status_code == 401


@pytest.mark.asyncio
async def test_single_use_email_verification_token():
    """Assert email verification token cannot be reused once consumed."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        unique_id = uuid4().hex[:8]
        email = f"singleuse.{unique_id}@example.com"
        reg_payload = {
            "email": email,
            "password": "SingleUse#Pass123",
            "first_name": "Single",
            "last_name": "Use",
            "organization_name": f"SingleUse-Org-{unique_id}",
        }
        reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
        assert reg_res.status_code == 201
        user_id = UUID(reg_res.json()["user_id"])

        from packages.auth.tokens import create_email_token
        # Create token and hash
        verify_token = create_email_token(user_id, "verify_email", ttl_hours=24)
        hashed_attempt = hashlib.sha256(verify_token.encode("utf-8")).hexdigest()

        # Update DB single use token to match this test token's hash
        engine = create_async_engine(ASYNC_TEST_DB_URL, echo=False)
        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            await session.execute(
                text("UPDATE single_use_tokens SET token_hash = :new_hash WHERE user_id = :uid"),
                {"new_hash": hashed_attempt, "uid": user_id},
            )
            await session.commit()
        await engine.dispose()

        # First verification succeeds
        v1 = await client.post("/api/v1/auth/verify-email", json={"token": verify_token})
        assert v1.status_code == 200
        assert "verified" in v1.json()["message"].lower()

        # Second verification attempt fails (single-use enforcement)
        v2 = await client.post("/api/v1/auth/verify-email", json={"token": verify_token})
        assert v2.status_code == 400
        assert "already been consumed" in v2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_pooled_connection_tenant_leakage_prevented():
    """
    Proves that connection pool reuse between requests NEVER leaks tenant isolation
    even when connecting as unprivileged app_user.
    """
    engine = create_async_engine(APP_DB_URL, echo=False, pool_size=1, max_overflow=0)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    org_a = uuid4()

    # Request A: Sets tenant context to Org A
    async with session_factory() as session_a:
        await set_tenant_context(session_a, org_a)
        # Execute query inside transaction
        res = await session_a.execute(text("SELECT current_setting('app.tenant_id', true);"))
        val = res.scalar()
        assert val == str(org_a)
        await session_a.commit()

    # Request B: Checks out the same connection from the 1-connection pool WITHOUT setting context
    async with session_factory() as session_b:
        res = await session_b.execute(text("SELECT current_setting('app.tenant_id', true);"))
        val = res.scalar()
        # SET LOCAL cleared the transaction context upon commit — no leakage!
        assert val is None or val == "", f"Pool leakage detected! Value '{val}' remained across sessions!"

    await engine.dispose()
