"""
Initial Base Schema Migration for Enterprise Multi-Tenant SaaS.

Creates all core tables, users, organizations, memberships, ERP business
entities, AI agent entities, workflows, documents, and applies PostgreSQL
Row-Level Security (RLS) policies to all tenant-scoped tables.

Revision ID: 0001_initial_base_schema
Revises: (initial — no prior revision)
Create Date: 2026-10-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from packages.database.models.base import Base
import packages.database.models  # registers all mappers
from packages.database.core import get_rls_tables

# revision identifiers, used by Alembic
revision = "0001_initial_base_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Enable available PostgreSQL extensions safely
    for ext in ("uuid-ossp", "pgcrypto", "vector"):
        has_ext = conn.execute(text("SELECT 1 FROM pg_available_extensions WHERE name = :name"), {"name": ext}).scalar()
        if has_ext:
            conn.execute(text(f'CREATE EXTENSION IF NOT EXISTS "{ext}";'))

    # 2. Create ALL tables registered in SQLAlchemy Base.metadata
    Base.metadata.create_all(bind=conn)

    # 3. Apply PostgreSQL Row-Level Security (RLS) policies to all tenant tables
    rls_tables = get_rls_tables()
    for table_name in rls_tables:
        conn.execute(text(f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY;'))
        conn.execute(text(f'ALTER TABLE "{table_name}" FORCE ROW LEVEL SECURITY;'))
        conn.execute(text(f'DROP POLICY IF EXISTS "{table_name}_tenant_isolation" ON "{table_name}";'))
        conn.execute(text(f'''
            CREATE POLICY "{table_name}_tenant_isolation" ON "{table_name}"
            AS RESTRICTIVE
            FOR ALL
            USING (
                organization_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            )
            WITH CHECK (
                organization_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            );
        '''))


def downgrade() -> None:
    conn = op.get_bind()
    rls_tables = get_rls_tables()
    for table_name in rls_tables:
        try:
            conn.execute(text(f'DROP POLICY IF EXISTS "{table_name}_tenant_isolation" ON "{table_name}";'))
            conn.execute(text(f'ALTER TABLE "{table_name}" NO FORCE ROW LEVEL SECURITY;'))
            conn.execute(text(f'ALTER TABLE "{table_name}" DISABLE ROW LEVEL SECURITY;'))
        except Exception:
            pass

    Base.metadata.drop_all(bind=conn)
