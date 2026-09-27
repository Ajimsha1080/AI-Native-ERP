import pytest
import os
import importlib
from unittest.mock import patch


def test_database_url_missing_in_production_fails_loudly():
    """Asserts that importing database core in production without DATABASE_URL raises RuntimeError."""
    with patch.dict(os.environ, {"ENVIRONMENT": "production", "DATABASE_URL": ""}):
        with pytest.raises(RuntimeError) as exc_info:
            import packages.database.core
            importlib.reload(packages.database.core)
        assert "fatal database configuration" in str(exc_info.value).lower()
        assert "missing or empty in 'production'" in str(exc_info.value).lower()


def test_database_url_missing_in_development_fails_loudly():
    """Asserts that importing database core in development without DATABASE_URL raises RuntimeError."""
    with patch.dict(os.environ, {"ENVIRONMENT": "development", "DATABASE_URL": ""}):
        with pytest.raises(RuntimeError) as exc_info:
            import packages.database.core
            importlib.reload(packages.database.core)
        assert "fatal database configuration" in str(exc_info.value).lower()
        assert "missing or empty in 'development'" in str(exc_info.value).lower()


def test_sqlite_in_production_fails_loudly():
    """Asserts that configuring SQLite in production environment raises RuntimeError."""
    with patch.dict(os.environ, {"ENVIRONMENT": "production", "DATABASE_URL": "sqlite:///./prod.db"}):
        with pytest.raises(RuntimeError) as exc_info:
            import packages.database.core
            importlib.reload(packages.database.core)
        assert "sqlite is forbidden in production environment" in str(exc_info.value).lower()


def test_database_url_missing_in_test_environment_allowed():
    """Asserts that missing DATABASE_URL in test environment falls back to test sqlite without error."""
    with patch.dict(os.environ, {"ENVIRONMENT": "test", "DATABASE_URL": ""}):
        import packages.database.core
        importlib.reload(packages.database.core)
        assert packages.database.core.DATABASE_URL == "sqlite:///./test.db"
        assert packages.database.core.ASYNC_DATABASE_URL == "sqlite+aiosqlite:///./test.db"

    # Restore module state for subsequent integration tests
    test_db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:9527/agentic_erp")
    with patch.dict(os.environ, {"ENVIRONMENT": "testing", "DATABASE_URL": test_db_url}):
        import packages.database.core
        importlib.reload(packages.database.core)
