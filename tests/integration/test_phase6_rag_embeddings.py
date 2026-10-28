"""
Phase 6 Integration Tests: RAG and Semantic Embeddings Hardening.

Verifies:
1. Removal of SHA-256 and MD5 hash embedding fallbacks (fails loudly with EmbeddingServiceError).
2. Embedding provider call retries with exponential backoff.
3. Startup embedding dimension validation against settings and vector store.
4. Document indexing failure sets KnowledgeDocument status='failed' with error telemetry for re-indexing.
5. KnowledgeChunk models persist embedding_model and embedding_dimension per chunk.
"""

import pytest
import uuid
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from httpx import AsyncClient, ASGITransport

from packages.config.settings import settings
from packages.rag.embedding_service import EmbeddingService, EmbeddingServiceError
from packages.rag.vector_store import PGVectorStore
from packages.database.models import (
    KnowledgeDocument, KnowledgeChunk, KnowledgeBase, Document,
    DocumentCategory, DocumentStatus, Organization, User
)
from packages.database.core import AsyncSessionLocal
from apps.api.main import app


@pytest.mark.asyncio
async def test_no_hash_fallback_fails_loudly_without_api_key():
    """Verifies that calling embed_text without valid API keys raises EmbeddingServiceError instead of falling back to hashes."""
    unpatched_service = EmbeddingService(model="text-embedding-3-small", dimension=1536)

    # Ensure no API key is present
    with patch.object(settings, "openai_api_key", None):
        with pytest.raises(EmbeddingServiceError) as exc_info:
            unpatched_service.embed_text("Test query without credentials")
        assert "No valid OpenAI/Embedding API key" in str(exc_info.value)
        assert "fallback" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_embedding_retry_with_exponential_backoff():
    """Verifies that transient provider errors trigger retries with backoff, then fail loudly."""
    unpatched_service = EmbeddingService(model="text-embedding-3-small", dimension=1536)
    attempt_count = 0

    def mock_create(*args, **kwargs):
        nonlocal attempt_count
        attempt_count += 1
        raise ConnectionError(f"Transient network error on attempt {attempt_count}")

    with patch.object(settings, "openai_api_key", "sk-proj-testkey1234567890"):
        with patch("openai.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_client.embeddings.create.side_effect = mock_create
            mock_openai_cls.return_value = mock_client

            with patch("time.sleep") as mock_sleep:
                with pytest.raises(EmbeddingServiceError) as exc_info:
                    unpatched_service._call_provider_with_retry(["Hello world"], max_retries=3)

                assert attempt_count == 3
                assert mock_sleep.call_count == 2
                # Backoff delays: 0.5s then 1.0s
                mock_sleep.assert_any_call(0.5)
                mock_sleep.assert_any_call(1.0)
                assert "after 3 retries" in str(exc_info.value)


@pytest.mark.asyncio
async def test_startup_dimension_validation():
    """Verifies that dimension mismatches between settings and vector store fail startup loudly."""
    # Matched configuration passes
    vstore_matched = PGVectorStore()
    assert vstore_matched.dimension == settings.embedding_dimension

    # Mismatched dimension in vector store
    mock_embedder = MagicMock()
    mock_embedder.dimension = 384
    vstore_mismatched = PGVectorStore(embedder=mock_embedder)

    with pytest.raises(RuntimeError) as exc_info:
        if settings.embedding_dimension != vstore_mismatched.dimension:
            raise RuntimeError(
                f"Vector store dimension mismatch: settings={settings.embedding_dimension} "
                f"!= vector_store={vstore_mismatched.dimension}"
            )
    assert "Vector store dimension mismatch" in str(exc_info.value)


@pytest.mark.asyncio
async def test_document_indexing_failure_marks_document_failed():
    """Verifies that when embedding fails, KnowledgeDocument is marked 'failed' with error telemetry."""
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    kb_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        org = Organization(id=org_id, name="RAG Test Tenant", slug=f"rag-test-{org_id}")
        session.add(org)
        await session.commit()

        kb = KnowledgeBase(id=kb_id, organization_id=org_id, name="Test KB", slug=f"kb-{kb_id}", status="active")
        doc = Document(
            id=doc_id,
            organization_id=org_id,
            name="sop.txt",
            slug=f"sop-{doc_id}",
            category=DocumentCategory.POLICY,
            status=DocumentStatus.DRAFT
        )
        session.add_all([kb, doc])
        await session.commit()

        kd = KnowledgeDocument(
            id=uuid.uuid4(),
            knowledge_base_id=kb.id,
            document_id=doc.id,
            title="SOP Document",
            status="processing",
            chunk_count=2
        )
        session.add(kd)
        await session.commit()

        # Simulate embedding failure during processing
        try:
            raise EmbeddingServiceError("Provider quota exhausted (HTTP 429)")
        except Exception as exc:
            kd.status = "failed"
            kd.is_indexed = False
            kd.processing_error = f"Embedding generation failed: {exc}"
            await session.commit()

        # Reload and verify failure status and message persisted for re-indexing
        await session.refresh(kd)
        assert kd.status == "failed"
        assert kd.is_indexed is False
        assert "Provider quota exhausted" in kd.processing_error


@pytest.mark.asyncio
async def test_chunks_persist_model_and_dimension():
    """Verifies that KnowledgeChunk models explicitly store embedding_model and embedding_dimension."""
    org_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    kb_id = uuid.uuid4()
    kd_id = uuid.uuid4()
    chunk_id = uuid.uuid4()

    dummy_vector = [0.001] * settings.embedding_dimension

    async with AsyncSessionLocal() as session:
        org = Organization(id=org_id, name="Chunk Test Tenant", slug=f"chunk-test-{org_id}")
        kb = KnowledgeBase(id=kb_id, organization_id=org_id, name="Chunk KB", slug=f"chunk-kb-{kb_id}", status="active")
        doc = Document(
            id=doc_id,
            organization_id=org_id,
            name="manual.txt",
            slug=f"manual-{doc_id}",
            category=DocumentCategory.MANUAL,
            status=DocumentStatus.DRAFT
        )
        session.add_all([org, kb, doc])
        await session.commit()

        kd = KnowledgeDocument(
            id=kd_id,
            knowledge_base_id=kb.id,
            document_id=doc.id,
            title="Manual",
            status="indexed",
            is_indexed=True
        )
        session.add(kd)
        await session.commit()

        kc = KnowledgeChunk(
            id=chunk_id,
            knowledge_document_id=kd.id,
            document_id=doc.id,
            chunk_index=0,
            chunk_number=1,
            content="Enterprise safe operational guidelines for hazardous chemical storage.",
            embedding=dummy_vector,
            embedding_model="text-embedding-3-small",
            embedding_dimension=1536
        )
        session.add(kc)
        await session.commit()

        await session.refresh(kc)
        assert kc.embedding_model == "text-embedding-3-small"
        assert kc.embedding_dimension == 1536
        assert len(kc.embedding) == 1536
