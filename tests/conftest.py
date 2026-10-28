import os
import sys
import pytest
import pytest_asyncio
import asyncio
from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set DATABASE_URL to PostgreSQL for integration tests
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:9527/agentic_erp")
os.environ["ENVIRONMENT"] = "testing"

from packages.database.core import create_db_and_tables, create_rls_policies, assert_rls_policies_active
from packages.database.models.base import Base

TEST_DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:9527/agentic_erp")
if TEST_DB_URL.startswith("postgresql://"):
    ASYNC_TEST_DB_URL = TEST_DB_URL.replace("postgresql://", "postgresql+asyncpg://")
elif TEST_DB_URL.startswith("postgres://"):
    ASYNC_TEST_DB_URL = TEST_DB_URL.replace("postgres://", "postgresql+asyncpg://")
else:
    ASYNC_TEST_DB_URL = TEST_DB_URL


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database():
    """Initializes PostgreSQL schema, extensions, app_user role, and RLS policies."""
    admin_engine = create_async_engine(ASYNC_TEST_DB_URL, echo=False)
    async with admin_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Create non-superuser application test role to verify strict RLS enforcement
        try:
            await conn.execute(text("CREATE ROLE app_user WITH LOGIN PASSWORD 'app_pass' NOSUPERUSER NOBYPASSRLS;"))
        except Exception:
            pass
        try:
            await conn.execute(text("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO app_user;"))
            await conn.execute(text("GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO app_user;"))
            await conn.execute(text("GRANT ALL PRIVILEGES ON SCHEMA public TO app_user;"))
        except Exception:
            pass
    
    await create_rls_policies()
    await assert_rls_policies_active()
    yield
    await admin_engine.dispose()


@pytest.fixture(autouse=True)
def mock_embedding_for_offline_tests(monkeypatch):
    """Provides test vectors for offline test runs when OpenAI API key is unset."""
    from packages.rag.embedding_service import embedding_service
    from packages.config.settings import settings
    import math

    api_key = getattr(settings, "openai_api_key", None)
    if not api_key or not str(api_key).startswith("sk-"):
        def _mock_call(texts, max_retries=3):
            import hashlib
            vectors = []
            for t in texts:
                words = t.lower().split()
                vec = [0.0] * embedding_service.dimension
                for w in words:
                    h = int(hashlib.md5(w.encode('utf-8')).hexdigest(), 16)
                    idx = h % embedding_service.dimension
                    sign = 1.0 if (h >> 4) % 2 == 0 else -1.0
                    vec[idx] += sign
                norm = math.sqrt(sum(x * x for x in vec))
                if norm > 0:
                    vec = [x / norm for x in vec]
                vectors.append(vec)
            return vectors

        monkeypatch.setattr(embedding_service, "_call_provider_with_retry", _mock_call)
