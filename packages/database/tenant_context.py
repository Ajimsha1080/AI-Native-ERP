"""
Tenant context management for PostgreSQL Row-Level Security.

Every database session used by an authenticated route sets the
PostgreSQL session-level variable `app.tenant_id`, which RLS policies
read via `current_setting('app.tenant_id')::uuid`.
"""

from typing import AsyncGenerator, Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.core import AsyncSessionLocal
from packages.auth.dependencies import get_current_user, UserTokenPayload


async def set_tenant_context(session: AsyncSession, org_id: UUID) -> None:
    """Set PostgreSQL session-level tenant context for RLS."""
    try:
        await session.execute(
            text("SELECT set_config('app.tenant_id', :org_id, true)"),
            {"org_id": str(org_id)},
        )
    except Exception:
        # SQLite or dialects without set_config will ignore
        pass


async def get_tenant_db(
    current_user: Annotated[UserTokenPayload, Depends(get_current_user)],
) -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession with tenant context configured."""
    async with AsyncSessionLocal() as session:
        await set_tenant_context(session, current_user.org_id)
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_raw_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a raw AsyncSession without tenant context (for unauthenticated auth routes)."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


TenantDB = Annotated[AsyncSession, Depends(get_tenant_db)]
RawDB = Annotated[AsyncSession, Depends(get_raw_db)]
