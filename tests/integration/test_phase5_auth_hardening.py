"""
Phase 5 Integration Tests:
- Token revocation and blacklisting via async Redis.
- Short-TTL user active and org membership check (deactivation / org removal invalidates token).
- Access token TTL is 15 minutes.
- Fail closed (503) outside test if Redis is down during revocation check.
"""

import pytest
from uuid import uuid4
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, update

from apps.api.main import app
from tests.conftest import ASYNC_TEST_DB_URL
from packages.auth.tokens import create_access_token, TokenBlacklist, decode_token
from packages.database.models import Organization, User
from packages.database.tenant_context import set_tenant_context
from packages.config.settings import settings


@pytest.mark.asyncio
async def test_access_token_ttl_is_15_minutes():
    """Verify default access token TTL is 15 minutes."""
    assert settings.access_token_expire_minutes == 15
    token = create_access_token(user_id=uuid4(), org_id=uuid4(), role="viewer")
    payload = decode_token(token)
    # Check expiry is within 15 mins (allowing slight test execution margin)
    now_ts = int(datetime.now(timezone.utc).timestamp())
    ttl_seconds = payload.exp - now_ts
    assert 850 <= ttl_seconds <= 950, f"Expected ~900s (15 min) TTL, got {ttl_seconds}s"


@pytest.mark.asyncio
async def test_user_deactivation_invalidates_access_token():
    """Deactivating a user in the database immediately invalidates their access token (401)."""
    engine = create_async_engine(ASYNC_TEST_DB_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid4()
    user_id = uuid4()

    async with session_factory() as session:
        await set_tenant_context(session, org_id)
        org = Organization(id=org_id, name="Deactivation Test Org", slug=f"deact-{org_id.hex[:6]}")
        user = User(
            id=user_id,
            email=f"deact.{org_id.hex[:4]}@corp.io",
            organization_id=org_id,
            tenant_id=org_id,
            password_hash="argon2id$mock$hash",
            first_name="Active",
            last_name="User",
            is_active=True
        )
        session.add_all([org, user])
        await session.commit()

    token = create_access_token(user_id=user_id, org_id=org_id, role="viewer", email=user.email)
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # First request while active: succeeds
        res1 = await client.get("/api/v1/dashboard/home", headers=headers)
        assert res1.status_code == 200

        # Deactivate user in database
        async with session_factory() as session:
            await set_tenant_context(session, org_id)
            await session.execute(
                update(User).where(User.id == user_id).values(is_active=False)
            )
            await session.commit()

        # Second request with the same token: MUST be rejected with 401
        res2 = await client.get("/api/v1/dashboard/home", headers=headers)
        assert res2.status_code == 401
        assert "deactivated" in res2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_token_revocation_blacklist():
    """Revoking a token or its JTI blocks subsequent requests immediately (401)."""
    engine = create_async_engine(ASYNC_TEST_DB_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid4()
    user_id = uuid4()

    async with session_factory() as session:
        await set_tenant_context(session, org_id)
        org = Organization(id=org_id, name="Blacklist Test Org", slug=f"bl-{org_id.hex[:6]}")
        user = User(
            id=user_id,
            email=f"bl.{org_id.hex[:4]}@corp.io",
            organization_id=org_id,
            tenant_id=org_id,
            password_hash="argon2id$mock$hash",
            first_name="Blacklist",
            last_name="User",
            is_active=True
        )
        session.add_all([org, user])
        await session.commit()

    jti = f"revoked-jti-{uuid4().hex}"
    token = create_access_token(user_id=user_id, org_id=org_id, role="viewer", email=user.email, jti=jti)
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Before revocation: succeeds
        res1 = await client.get("/api/v1/dashboard/home", headers=headers)
        assert res1.status_code == 200

        # Revoke the token via async blacklist
        await TokenBlacklist.blacklist_async(jti)

        # After revocation: rejected with 401
        res2 = await client.get("/api/v1/dashboard/home", headers=headers)
        assert res2.status_code == 401
        assert "revoked" in res2.json()["detail"].lower() or "blacklisted" in res2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_fail_closed_outside_test_environment():
    """In production mode, if Redis is down during revocation check, fail closed with 503."""
    orig_env = settings.environment
    try:
        settings.environment = "production"
        # Attempting check on invalid redis url must raise 503
        from fastapi import HTTPException
        orig_url = settings.redis_url
        settings.redis_url = "redis://127.0.0.1:59999/0"  # unreachable port
        TokenBlacklist._redis_pool = None

        with pytest.raises(HTTPException) as exc_info:
            await TokenBlacklist.is_blacklisted_async("some-jti-123")
        assert exc_info.value.status_code == 503
        assert "Security Service Unavailable" in exc_info.value.detail
    finally:
        settings.environment = orig_env
        settings.redis_url = orig_url
        TokenBlacklist._redis_pool = None
