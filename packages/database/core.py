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

from .models import Base

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
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_all_tables() -> None:
    """
    Drop all tables.
    """
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def init_database() -> None:
    """
    Initialize database with all tables synchronously.
    """
    Base.metadata.create_all(bind=engine)


def reset_database() -> None:
    """
    Reset database - drop all tables and recreate.
    """
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


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
