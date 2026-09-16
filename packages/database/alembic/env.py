"""Alembic environment configuration — fixed for ERP multi-tenant build."""
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool, create_engine

from alembic import context

# Add the project root to sys.path so all packages are importable
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, project_root)

# Import the unified Base metadata.
# All models must be imported here so that Alembic autogenerate
# detects them. We import the models package which in turn imports every model.
from packages.database.models.base import Base  # noqa: F401 — needed for metadata
import packages.database.models  # noqa: F401 — registers all ORM mappers

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The target metadata for --autogenerate support
target_metadata = Base.metadata


def get_url() -> str:
    """
    Prefer DATABASE_URL from environment, fall back to alembic.ini value.
    This allows CI to inject the real Postgres URL via the environment
    while local development can use the ini file.
    """
    return os.getenv(
        "DATABASE_URL",
        config.get_main_option("sqlalchemy.url"),
    )


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Configures the context with a URL string only — no live engine needed.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode — connects to a live database.
    """
    url = get_url()
    # Build a synchronous engine for Alembic (Alembic does not support async)
    connectable = create_engine(
        url,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
