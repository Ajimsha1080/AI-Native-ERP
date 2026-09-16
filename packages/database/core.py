"""
Database core functionality.

Provides database connections, session management, and initialization.
Supports both PostgreSQL (production) and SQLite (development/testing).
"""

from contextlib import contextmanager, asynccontextmanager
from typing import Generator, AsyncGenerator, Optional
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Database URL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./agents.db"
)

# Derive Async Database URL
if DATABASE_URL.startswith("sqlite:///"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///")
elif DATABASE_URL.startswith("postgresql://"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
else:
    ASYNC_DATABASE_URL = DATABASE_URL

is_sqlite = "sqlite" in DATABASE_URL
is_dev = os.getenv("ENVIRONMENT", "development") == "development"

# Configure engine options
if is_sqlite:
    async_engine_kwargs = {
        "echo": False,
    }
    sync_engine_kwargs = {
        "echo": False,
        "connect_args": {"check_same_thread": False},
    }
else:
    async_engine_kwargs = {
        "echo": is_dev,
        "pool_size": 10,
        "max_overflow": 20,
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    }
    sync_engine_kwargs = {
        "echo": is_dev,
        "pool_size": 10,
        "max_overflow": 20,
        "pool_pre_ping": True,
        "pool_recycle": 3600,
    }

# Create async engine
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    **async_engine_kwargs
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Create sync engine for worker/background tasks
engine = create_engine(
    DATABASE_URL,
    **sync_engine_kwargs
)

# Create session factory for sync
SessionLocal = sessionmaker(
    engine,
    class_=Session,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session for async operations (FastAPI dependency).

    Yields:
        AsyncSession: Database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get async database session generator (for worker tasks and services).
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def get_sync_db() -> Generator[Session, None, None]:
    """
    Get database session for sync operations.

    Yields:
        Session: Database session
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_engine():
    """Get the async database engine."""
    return async_engine


async def create_db_and_tables() -> None:
    """
    Create database and all tables from Base metadata.
    """
    from .models.base import Base
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_all_tables() -> None:
    """
    Drop all tables.
    """
    from .models.base import Base
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def init_database() -> None:
    """
    Initialize database with all tables synchronously.
    """
    from .models.base import Base
    Base.metadata.create_all(bind=engine)


def reset_database() -> None:
    """
    Reset database - drop all tables and recreate.
    """
    from .models.base import Base
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


# ERP tables that require Row-Level Security tenant isolation.
# Each table must have an `organization_id` UUID column.
_RLS_TABLES = [
    "products",
    "warehouses",
    "stock_levels",
    "stock_movements",
    "customers",
    "sales_orders",
    "sales_order_lines",
    "invoices",
    "invoice_lines",
    "payments",
    "vendors",
    "purchase_orders",
    "purchase_order_lines",
    "goods_receipts",
    "goods_receipt_lines",
    "accounts",
    "journal_entries",
    "journal_lines",
    "departments",
    "employees",
    "attendance_records",
    "leave_requests",
    "pending_approvals",
    "agent_runs",
    "tool_executions",
]


async def create_rls_policies() -> None:
    """
    Enable PostgreSQL Row-Level Security on all ERP business tables.

    Creates a policy per table that restricts access to rows whose
    organization_id matches the current session-level app.tenant_id setting.

    The setting is written by packages.database.tenant_context.set_tenant_context()
    at the start of every authenticated request.

    This function is idempotent — it uses CREATE POLICY IF NOT EXISTS syntax
    (available in Postgres 9.5+). Safe to call on every application startup.

    Note: This only applies to PostgreSQL. SQLite (used in unit tests without
    a container) silently ignores the statements because the tables do not exist
    in that dialect.
    """
    from sqlalchemy import text

    if "sqlite" in DATABASE_URL:
        # SQLite does not support RLS; skip silently in unit-test mode
        return

    async with async_engine.begin() as conn:
        for table in _RLS_TABLES:
            # Enable RLS on the table
            await conn.execute(
                text(f"ALTER TABLE IF EXISTS {table} ENABLE ROW LEVEL SECURITY")
            )
            # Drop and recreate policy so startup is idempotent
            await conn.execute(
                text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
            )
            await conn.execute(
                text(
                    f"CREATE POLICY tenant_isolation ON {table} "
                    f"USING (organization_id = current_setting('app.tenant_id', true)::uuid)"
                )
            )


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """
    Provide a transactional scope around a series of operations.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@asynccontextmanager
async def async_session_scope() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a transactional scope for async operations.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
