from typing import List, Optional
from datetime import datetime
from sqlalchemy import (
    Float,
    Column, String, Text, Integer, Boolean, DateTime, JSON,
    ForeignKey, Index, Enum as SQLEnum, UniqueConstraint, CheckConstraint
)
from sqlalchemy.orm import relationship
from enum import Enum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from uuid import uuid4


from .base import TenantIDMixin, Base


class KnowledgeBaseType(str, Enum):
    """Knowledge base types."""
    INTERNAL = "internal"
    POLICY = "policy"
    PROCEDURE = "procedure"
    CONTRACT = "contract"
    MANUAL = "manual"
    REPORT = "report"
    CUSTOM = "custom"
    COMPLIANCE = "compliance"


class KnowledgeDocumentStatus(str, Enum):
    """Knowledge document status."""
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"
    ARCHIVED = "archived"


class KnowledgeBase(Base):
    """Knowledge base for RAG.

    Knowledge bases organize documents for AI retrieval.
    """

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )
    organization_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('organizations.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Knowledge Base Details
    name = Column(String(255), nullable=False)
    slug = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # Type
    type = Column(
        SQLEnum(KnowledgeBaseType),
        default=KnowledgeBaseType.INTERNAL,
        nullable=False,
        index=True
    )

    # Knowledge Store
    store_type = Column(String(50), nullable=True)
    # Types: pinecone, faiss, chroma, local

    # Connection
    vector_store_config = Column(JSON, nullable=True)
    embedding_model = Column(String(100), nullable=True)
    embedding_dimension = Column(Integer, nullable=True)

    # Source
    workspace_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('workspaces.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    workspace = relationship("Workspace", back_populates="knowledge_bases")

    business_unit_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('business_units.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    business_unit = relationship("BusinessUnit", back_populates="knowledge_bases")

    # Settings
    settings = Column(JSON, nullable=True)
    # Retrieval settings, chunking rules, etc.

    # Permissions
    access_level = Column(String(50), nullable=True)

    # Status
    status = Column(String(50), nullable=False)
    # Status: active, inactive, archived

    # Statistics
    total_documents = Column(Integer, default=0)
    total_chunks = Column(Integer, default=0)
    last_synced_at = Column(DateTime, nullable=True)
    last_indexed_at = Column(DateTime, nullable=True)

    # Retention
    retention_days = Column(Integer, nullable=True)

    # Audit
    created_by_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )
    created_by = relationship("User", foreign_keys=[created_by_id])
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="knowledge_bases")
    documents = relationship("KnowledgeDocument", back_populates="knowledge_base", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        UniqueConstraint('organization_id', 'slug', name='uix_knowledge_base_organization_slug'),
        CheckConstraint(
            "status IN ('active', 'inactive', 'archived')",
            name='chk_knowledge_base_status'
        ),
        Index('ix_knowledge_base_name', 'name'),
        Index('ix_knowledge_base_slug', 'slug'),
        Index('ix_knowledge_base_type', 'type'),
        Index('ix_knowledge_base_organization', 'organization_id'),
        Index('ix_knowledge_base_workspace', 'workspace_id'),
        Index('ix_knowledge_base_business_unit', 'business_unit_id'),
    )


class KnowledgeDocument(Base):
    """Document in a knowledge base.

    Documents are indexed for AI retrieval.
    """

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )

    # Knowledge Base
    knowledge_base_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('knowledge_bases.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    knowledge_base = relationship("KnowledgeBase", back_populates="documents")

    # Document
    document_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('documents.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    document = relationship("Document", back_populates="knowledge_documents")

    # Document Details
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Status
    status = Column(
        SQLEnum(KnowledgeDocumentStatus),
        default=KnowledgeDocumentStatus.PENDING,
        nullable=False,
        index=True
    )

    # Indexing
    is_indexed = Column(Boolean, default=False)
    index_version = Column(Integer, default=0)
    index_time = Column(DateTime, nullable=True)

    # Metadata
    meta_data = Column("metadata", JSON, nullable=True)
    # Document metadata

    # Chunking
    chunk_count = Column(Integer, default=0)
    chunks = Column(JSON, nullable=True)  # List of chunk IDs

    # Processing
    processing_error = Column(Text, nullable=True)

    # Retention
    last_accessed_at = Column(DateTime, nullable=True)
    access_count = Column(Integer, default=0)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'indexed', 'failed', 'archived')",
            name='chk_knowledge_document_status'
        ),
        Index('ix_knowledge_document_kb', 'knowledge_base_id'),
        Index('ix_knowledge_document_status', 'status'),
        Index('ix_knowledge_document_created_at', 'created_at'),
    )


class KnowledgeChunk(Base):
    """Indexed chunk from a document.

    Chunks are embedded and stored for vector similarity search.
    """

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )

    # Knowledge Document
    knowledge_document_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('knowledge_documents.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    knowledge_document = relationship("KnowledgeDocument")

    # Content
    content = Column(Text, nullable=False)
    embedding = Column(JSON, nullable=True)  # Vector embedding
    embedding_model = Column(String(100), nullable=True)

    # Chunk Information
    chunk_index = Column(Integer, nullable=False)
    chunk_number = Column(Integer, nullable=False)
    chunk_position = Column(Integer, nullable=True)
    chunk_type = Column(String(50), nullable=True)

    # Metadata
    meta_data = Column("metadata", JSON, nullable=True)
    # Chunk-specific metadata

    # Content Source
    document_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('documents.id', ondelete='CASCADE'),
        nullable=True,
        index=True
    )
    document = relationship("Document")

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "chunk_number > 0",
            name='chk_knowledge_chunk_number'
        ),
        Index('ix_knowledge_chunk_document', 'document_id'),
        Index('ix_knowledge_chunk_created_at', 'created_at'),
    )
