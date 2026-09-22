"""
Database core functionality - Enterprise Edition.

Provides enterprise-grade PostgreSQL connection pooling, async session management,
Row-Level Security (RLS) multi-tenant policies, native pgvector extension setup,
and health diagnostics.
"""

from contextlib import contextmanager, asynccontextmanager
from typing import Generator, AsyncGenerator, Optional, Dict, Any
import time
import os
import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session

logger = logging.getLogger("database.core")

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Enterprise PostgreSQL default connection string with environment override
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/agentic_erp"
)

# Derive Async Database URL
if DATABASE_URL.startswith("sqlite:///"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///")
elif DATABASE_URL.startswith("postgresql://"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
elif DATABASE_URL.startswith("postgres://"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://")
else:
    ASYNC_DATABASE_URL = DATABASE_URL

is_sqlite = "sqlite" in DATABASE_URL
is_dev = os.getenv("ENVIRONMENT", "development") == "development"

# Configure Enterprise-Grade Engine Options
if is_sqlite:
    async_engine_kwargs = {
        "echo": False,
    }
    sync_engine_kwargs = {
        "echo": False,
        "connect_args": {"check_same_thread": False},
    }
else:
    # Enterprise High-Concurrency PostgreSQL Configuration
    async_engine_kwargs = {
        "echo": is_dev,
        "pool_size": int(os.getenv("DB_POOL_SIZE", "20")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "30")),
        "pool_pre_ping": True,
        "pool_recycle": 1800,  # Recycle every 30 mins to avoid stale connection drops
        "pool_timeout": 30,    # Max seconds to wait for a connection from pool
        "connect_args": {
            "server_settings": {
                "application_name": "agentic_erp_api",
                "timezone": "UTC",
                "statement_timeout": "60000",  # 60 second query timeout to prevent table lock deadlocks
            }
        }
    }
    sync_engine_kwargs = {
        "echo": is_dev,
        "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
        "pool_pre_ping": True,
        "pool_recycle": 1800,
        "pool_timeout": 30,
        "connect_args": {
            "application_name": "agentic_erp_worker",
        }
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


async def init_enterprise_extensions() -> None:
    """
    Ensures required enterprise PostgreSQL extensions are enabled:
    - vector: Native high-performance vector similarity search (pgvector)
    - uuid-ossp: Enterprise UUID generator functions
    - pg_trgm: Trigram fuzzy text matching index accelerator
    - btree_gin: Multi-column composite GIN indexes
    """
    if is_sqlite:
        return

    extensions = ["vector", "uuid-ossp", "pg_trgm", "btree_gin"]
    async with async_engine.begin() as conn:
        for ext in extensions:
            try:
                await conn.execute(text(f'CREATE EXTENSION IF NOT EXISTS "{ext}";'))
                logger.info(f"PostgreSQL extension '{ext}' verified active.")
            except Exception as e:
                logger.debug(f"Extension '{ext}' init note: {e}")


async def check_db_health() -> Dict[str, Any]:
    """
    Enterprise health check measuring round-trip latency and pool metrics.
    """
    start = time.time()
    try:
        async with AsyncSessionLocal() as session:
            res = await session.execute(text("SELECT 1"))
            res.scalar()
        latency_ms = round((time.time() - start) * 1000, 2)
        return {
            "status": "healthy",
            "latency_ms": latency_ms,
            "dialect": "postgresql" if not is_sqlite else "sqlite",
            "pool_size": async_engine.pool.size() if hasattr(async_engine, "pool") else 0,
            "checked_in": async_engine.pool.checkedin() if hasattr(async_engine, "pool") else 0,
            "checked_out": async_engine.pool.checkedout() if hasattr(async_engine, "pool") else 0,
        }
    except Exception as e:
        latency_ms = round((time.time() - start) * 1000, 2)
        return {
            "status": "unhealthy",
            "latency_ms": latency_ms,
            "error": str(e),
            "dialect": "postgresql" if not is_sqlite else "sqlite",
        }


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session for async operations (FastAPI dependency).
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
    Create database and all tables from Base metadata, then initialize enterprise extensions.
    """
    from .models.base import Base
    await init_enterprise_extensions()
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await create_rls_policies()


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
# Each table has an `organization_id` / `tenant_id` UUID column.
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
    "knowledge_bases",
    "knowledge_documents",
]


async def create_rls_policies() -> None:
    """
    Enable PostgreSQL Row-Level Security on all ERP business tables.
    """
    if is_sqlite:
        return

    async with async_engine.begin() as conn:
        for table in _RLS_TABLES:
            try:
                # Enable RLS on the table
                await conn.execute(
                    text(f"ALTER TABLE IF EXISTS {table} ENABLE ROW LEVEL SECURITY;")
                )
                # Drop and recreate policy so startup is idempotent
                await conn.execute(
                    text(f"DROP POLICY IF EXISTS tenant_isolation ON {table};")
                )
                await conn.execute(
                    text(
                        f"CREATE POLICY tenant_isolation ON {table} "
                        f"USING (organization_id = current_setting('app.tenant_id', true)::uuid);"
                    )
                )
            except Exception as e:
                logger.debug(f"RLS policy setup note on {table}: {e}")


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
