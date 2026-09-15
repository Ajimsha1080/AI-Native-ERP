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


class DocumentCategory(str, Enum):
    """Document categories."""
    POLICY = "policy"
    PROCEDURE = "procedure"
    CONTRACT = "contract"
    AGREEMENT = "agreement"
    MANUAL = "manual"
    GUIDE = "guide"
    REPORT = "report"
    FORM = "form"
    TEMPLATE = "template"
    INVOICE = "invoice"
    RECEIPT = "receipt"
    CERTIFICATE = "certificate"
    INSTRUCTION = "instruction"
    REGULATION = "regulation"
    COMPLIANCE = "compliance"
    TRAINING = "training"
    OTHER = "other"


class DocumentStatus(str, Enum):
    """Document status."""
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"
    DELETED = "deleted"
    DEPRECATED = "deprecated"


class Document(Base):
    """Document represents a business document.

    Documents can be uploaded, indexed, and retrieved via RAG.
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
    workspace_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('workspaces.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    business_unit_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('business_units.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )

    # Document Details
    name = Column(String(255), nullable=False)
    slug = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # Category
    category = Column(
        SQLEnum(DocumentCategory),
        default=DocumentCategory.OTHER,
        nullable=False,
        index=True
    )

    # File Information
    file_name = Column(String(500), nullable=True)
    file_size = Column(Integer, nullable=True)  # in bytes
    file_type = Column(String(100), nullable=True)
    file_extension = Column(String(20), nullable=True)
    mime_type = Column(String(100), nullable=True)

    # Storage
    storage_type = Column(String(50), nullable=True)
    storage_path = Column(String(500), nullable=True)
    cloud_storage_url = Column(String(500), nullable=True)

    # Document Content
    content = Column(Text, nullable=True)
    extracted_text = Column(Text, nullable=True)

    # Processing
    is_indexed = Column(Boolean, default=False)
    index_version = Column(Integer, default=0)
    processing_status = Column(String(50), nullable=True)
    # Status: pending, processing, completed, failed

    # Chunking
    chunk_count = Column(Integer, default=0)
    chunk_size = Column(Integer, default=1000)
    overlap = Column(Integer, default=200)

    # Metadata
    meta_data = Column("metadata", JSON, nullable=True)
    # Custom metadata extracted from document

    # Access
    is_public = Column(Boolean, default=False)
    access_level = Column(String(50), nullable=True)

    # Status
    status = Column(
        SQLEnum(DocumentStatus),
        default=DocumentStatus.DRAFT,
        nullable=False,
        index=True
    )
    is_active = Column(Boolean, default=True)

    # Versioning
    version = Column(Integer, default=1)
    previous_version_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('documents.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )

    # Review
    requires_review = Column(Boolean, default=False)
    reviewed_at = Column(DateTime, nullable=True)
    reviewer_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )

    # Access Control
    owner_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=True,
        index=True
    )

    # Encryption
    is_encrypted = Column(Boolean, default=False)
    encryption_key_id = Column(String(500), nullable=True)

    # Retention
    retention_days = Column(Integer, nullable=True)
    retention_date = Column(DateTime, nullable=True)

    # Audit
    created_by_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )
    created_by = relationship("User", foreign_keys=[created_by_id])
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="documents")
    workspace = relationship("Workspace", back_populates="documents")
    business_unit = relationship("BusinessUnit", back_populates="documents")
    owner = relationship("User", foreign_keys=[owner_id], back_populates="documents")
    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan")
    document_sources = relationship("DocumentDataSource", back_populates="document")
    knowledge_documents = relationship("KnowledgeDocument", back_populates="document")
    audit_logs = relationship("AuditEvent", back_populates="document")

    # Constraints
    __table_args__ = (
        UniqueConstraint('organization_id', 'slug', name='uix_document_organization_slug'),
        CheckConstraint(
            "status IN ('draft', 'pending_review', 'approved', 'rejected', 'archived', 'deleted', 'deprecated')",
            name='chk_document_status'
        ),
        Index('ix_document_name', 'name'),
        Index('ix_document_slug', 'slug'),
        Index('ix_document_category', 'category'),
        Index('ix_document_status', 'status'),
        Index('ix_document_organization', 'organization_id'),
        Index('ix_document_owner', 'owner_id'),
        Index('ix_document_created_at', 'created_at'),
    )


class DocumentVersion(Base):
    """Document version history."""

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )

    # Document
    document_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('documents.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    document = relationship("Document", back_populates="versions")

    # Version Details
    version = Column(Integer, nullable=False)
    version_name = Column(String(255), nullable=True)
    version_description = Column(Text, nullable=True)

    # File Information
    file_name = Column(String(500), nullable=True)
    file_size = Column(Integer, nullable=True)
    storage_path = Column(String(500), nullable=True)

    # Content
    content = Column(Text, nullable=True)
    extracted_text = Column(Text, nullable=True)

    # Processing
    is_indexed = Column(Boolean, default=False)
    index_version = Column(Integer, default=0)

    # Changes
    changes_summary = Column(Text, nullable=True)

    # Audit
    created_by_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )
    created_by = relationship("User", foreign_keys=[created_by_id])
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Constraints
    __table_args__ = (
        UniqueConstraint('document_id', 'version', name='uix_document_version'),
        Index('ix_document_version_document', 'document_id'),
        Index('ix_document_version_created_at', 'created_at'),
    )
