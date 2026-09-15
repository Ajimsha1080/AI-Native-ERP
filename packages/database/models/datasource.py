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


class DataSourceType(str, Enum):
    """Data source types."""
    ERP = "erp"
    DATABASE = "database"
    API = "api"
    FILE = "file"
    CLOUD_STORAGE = "cloud_storage"
    SALESFORCE = "salesforce"
    SAP = "sap"
    ORACLE = "oracle"
    DYNAMICS = "dynamics"
    TALLY = "tally"
    ODOO = "odoo"
    SHOPIFY = "shopify"
    MAGENTO = "magento"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLSERVER = "sqlserver"
    CSV = "csv"
    EXCEL = "excel"
    API_REST = "rest_api"
    API_GRAPHQL = "graphql_api"
    WEBHOOK = "webhook"
    KNOWLEDGE_BASE = "knowledge_base"
    CONFLUENCE = "confluence"
    NOTION = "notion"


class DataSourceStatus(str, Enum):
    """Data source status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SYNCING = "syncing"
    FAILED = "failed"
    PENDING = "pending"
    ARCHIVED = "archived"


class DataSource(Base):
    """Data Source represents a source of data for agents.

    Data sources are connected to integrations and contain
    the actual data that agents can query and analyze.
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

    # Source Details
    name = Column(String(255), nullable=False)
    slug = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    data_type = Column(String(100), nullable=True)

    # Source Type
    type = Column(
        SQLEnum(DataSourceType),
        default=DataSourceType.API,
        nullable=False,
        index=True
    )

    # Connection
    connection_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('integration_connections.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    connection = relationship("IntegrationConnection", back_populates="data_sources")

    # Workspace & Business Unit
    workspace_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('workspaces.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    workspace = relationship("Workspace", back_populates="data_sources")
    business_unit_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('business_units.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    business_unit = relationship("BusinessUnit", back_populates="data_sources")

    # Source Configuration
    source_config = Column(JSON, nullable=True)
    # Configuration for the specific data source (tables, endpoints, queries, etc.)

    # Query Configuration
    query_template = Column(Text, nullable=True)
    query_parameters = Column(JSON, nullable=True)
    filter_rules = Column(JSON, nullable=True)

    # Status
    status = Column(
        SQLEnum(DataSourceStatus),
        default=DataSourceStatus.PENDING,
        nullable=False,
        index=True
    )
    is_active = Column(Boolean, default=False)

    # Data Statistics
    total_records = Column(Integer, default=0)
    last_synced_at = Column(DateTime, nullable=True)
    next_sync_at = Column(DateTime, nullable=True)
    sync_frequency_minutes = Column(Integer, nullable=True)

    # Health
    health_score = Column(Integer, default=0)  # 0-100
    last_health_check = Column(DateTime, nullable=True)
    health_error = Column(Text, nullable=True)

    # Capabilities
    supports_query = Column(Boolean, default=True)
    supports_filter = Column(Boolean, default=True)
    supports_sort = Column(Boolean, default=True)
    supports_pagination = Column(Boolean, default=True)
    supports_pagination = Column(Boolean, default=True)

    # Indexing
    has_indexes = Column(Boolean, default=False)
    index_name = Column(String(100), nullable=True)

    # Cache
    cache_enabled = Column(Boolean, default=True)
    cache_ttl = Column(Integer, default=300)  # seconds
    last_cache_hit = Column(DateTime, nullable=True)

    # Access
    requires_permission = Column(Boolean, default=True)
    access_level = Column(String(50), nullable=True)

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
    organization = relationship("Organization", back_populates="data_sources")
    sync_logs = relationship("DataSyncLog", back_populates="data_source", cascade="all, delete-orphan")
    document_sources = relationship("DocumentDataSource", back_populates="data_source")

    # Constraints
    __table_args__ = (
        UniqueConstraint('organization_id', 'slug', name='uix_datasource_organization_slug'),
        CheckConstraint(
            "status IN ('active', 'inactive', 'syncing', 'failed', 'pending', 'archived')",
            name='chk_datasource_status'
        ),
        CheckConstraint(
            "health_score BETWEEN 0 AND 100",
            name='chk_datasource_health_score'
        ),
        Index('ix_datasource_name', 'name'),
        Index('ix_datasource_slug', 'slug'),
        Index('ix_datasource_type', 'type'),
        Index('ix_datasource_status', 'status'),
        Index('ix_datasource_organization', 'organization_id'),
        Index('ix_datasource_workspace', 'workspace_id'),
        Index('ix_datasource_business_unit', 'business_unit_id'),
    )


class DocumentDataSource(Base):
    """Document data source association.

    Links data sources to documents for document indexing.
    """

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )

    data_source_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('data_sources.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    data_source = relationship("DataSource", back_populates="document_sources")

    # Document
    document_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('documents.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    document = relationship("Document", back_populates="document_sources")

    # Association Details
    is_indexed = Column(Boolean, default=False)
    indexed_at = Column(DateTime, nullable=True)
    index_version = Column(Integer, default=0)

    # Constraints
    __table_args__ = (
        UniqueConstraint('data_source_id', 'document_id', name='uix_document_data_source'),
        Index('ix_document_data_source_data_source', 'data_source_id'),
        Index('ix_document_data_source_document', 'document_id'),
    )


class DataSyncLog(Base):
    """Data synchronization log.

    Tracks the status and results of data synchronization.
    """

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )
    data_source_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('data_sources.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    data_source = relationship("DataSource", back_populates="sync_logs")

    # Sync Details
    sync_type = Column(String(50), nullable=False)
    # Types: full, incremental, delta, webhook
    sync_start_time = Column(DateTime, nullable=False)
    sync_end_time = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Status
    status = Column(String(50), nullable=False)
    error_message = Column(Text, nullable=True)

    # Results
    total_records = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    skipped_count = Column(Integer, default=0)

    # Change Tracking
    new_records = Column(Integer, default=0)
    updated_records = Column(Integer, default=0)
    deleted_records = Column(Integer, default=0)

    # Source Information
    source_version = Column(String(50), nullable=True)
    source_checksum = Column(String(100), nullable=True)

    # Error Details
    error_details = Column(JSON, nullable=True)

    # Retry
    retry_count = Column(Integer, default=0)
    retry_status = Column(String(50), nullable=True)

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('idle', 'syncing', 'paused', 'failed', 'completed', 'partial', 'cancelled')",
            name='chk_datasync_log_status'
        ),
        Index('ix_datasync_log_data_source', 'data_source_id'),
        Index('ix_datasync_log_status', 'status'),
        Index('ix_datasync_log_sync_type', 'sync_type'),
        Index('ix_datasync_log_start_time', 'sync_start_time'),
    )
