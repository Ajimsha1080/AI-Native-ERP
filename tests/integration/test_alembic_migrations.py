"""
Integration tests for Alembic database migrations.

Verifies Phase 2 requirement:
`alembic upgrade head` on an empty PostgreSQL database yields a schema
matching all SQLAlchemy models in Base.metadata and activates RLS on all tenant tables.
"""

import os
from uuid import uuid4
import pytest
from sqlalchemy import create_engine, inspect, text
from alembic.config import Config
from alembic import command

from packages.database.models.base import Base
import packages.database.models  # load all models
from packages.database.core import get_rls_tables
from tests.conftest import TEST_DB_URL


@pytest.mark.asyncio
async def test_alembic_upgrade_head_on_empty_db_matches_models():
    """
    Creates an empty temporary database, runs `alembic upgrade head`,
    and asserts that all 68 model tables and RLS policies are created properly.
    """
    # Base admin connection
    sync_url = TEST_DB_URL
    if sync_url.startswith("postgresql+asyncpg://"):
        sync_url = sync_url.replace("postgresql+asyncpg://", "postgresql://")
    elif sync_url.startswith("postgres+asyncpg://"):
        sync_url = sync_url.replace("postgres+asyncpg://", "postgresql://")

    # Connect to default postgres DB to create a temporary clean DB
    admin_engine = create_engine(sync_url, isolation_level="AUTOCOMMIT")
    clean_db_name = f"test_clean_alembic_{uuid4().hex[:8]}"

    with admin_engine.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{clean_db_name}";'))

    try:
        # Construct database URL for the clean temporary database
        clean_db_url = sync_url.rsplit("/", 1)[0] + f"/{clean_db_name}"

        # Setup Alembic Config pointing to the clean database
        alembic_ini_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini"))
        alembic_cfg = Config(alembic_ini_path)
        alembic_cfg.set_main_option("sqlalchemy.url", clean_db_url)
        alembic_cfg.set_main_option("script_location", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "packages", "database", "alembic")))

        old_db_url = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = clean_db_url
        try:
            # Run Alembic upgrade head
            command.upgrade(alembic_cfg, "head")
        finally:
            if old_db_url is not None:
                os.environ["DATABASE_URL"] = old_db_url

        # Inspect the clean database
        migrated_engine = create_engine(clean_db_url)
        inspector = inspect(migrated_engine)
        migrated_tables = set(inspector.get_table_names(schema="public"))

        # 1. Assert all Base.metadata tables were created
        expected_tables = set(Base.metadata.tables.keys())
        missing_tables = expected_tables - migrated_tables
        assert not missing_tables, f"Alembic migration failed to create expected tables: {missing_tables}"

        # 2. Assert RLS policies are active on all tenant-scoped tables
        with migrated_engine.connect() as conn:
            rls_res = conn.execute(text("""
                SELECT relname
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relrowsecurity = true;
            """))
            active_rls_tables = {row[0] for row in rls_res.fetchall()}

            expected_rls_tables = set(get_rls_tables())
            missing_rls = expected_rls_tables - active_rls_tables
            assert not missing_rls, f"Tables missing RLS after alembic upgrade head: {missing_rls}"

        migrated_engine.dispose()

    finally:
        # Tear down the temporary test database
        with admin_engine.connect() as conn:
            conn.execute(text(f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = '{clean_db_name}'
                  AND pid <> pg_backend_pid();
            """))
            conn.execute(text(f'DROP DATABASE IF EXISTS "{clean_db_name}";'))
        admin_engine.dispose()
