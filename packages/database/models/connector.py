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

from .base import TenantIDMixin, Base, EnumCol
from packages.security.encryption import EncryptedString, EncryptedJSON


class ConnectorType(str, Enum):
    """Connector types."""
    ERP = "erp"
    CRM = "crm"
    DATABASE = "database"
    API = "api"
    FILE = "file"
    KNOWLEDGE_BASE = "knowledge"
    CUSTOM = "custom"


class ConnectorStatus(str, Enum):
    """Connector status."""
    PENDING = "pending"
    READY = "ready"
    CONFIGURING = "configuring"
    TESTING = "testing"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    DEPRECATED = "deprecated"


class SyncStatus(str, Enum):
    """Sync status."""
    IDLE = "idle"
    SYNCING = "syncing"
    PAUSED = "paused"
    FAILED = "failed"
    COMPLETED = "completed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


class Connector(Base):
    """Connector represents an ERP connector implementation.

    Connectors provide the implementation for interacting with
    specific ERP systems, databases, or APIs. Each connector
    implements the connector interface methods.
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

    # Connector Details
    name = Column(String(255), nullable=False)
    slug = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    version = Column(String(50), nullable=False, default='1.0.0')

    # Connector Type
    type = Column(
        EnumCol(ConnectorType),
        default=ConnectorType.API,
        nullable=False,
        index=True
    )

    # Connector Category
    category = Column(String(100), nullable=True)

    # Connector Implementation
    implementation_type = Column(String(50), nullable=False)
    # Types: REST, GraphQL, SOAP, ODATA, DIRECT_DB, FILE
    implementation_version = Column(String(50), nullable=True)

    # Provider
    provider = Column(String(100), nullable=True)
    provider_version = Column(String(50), nullable=True)

    # Source System
    source_system = Column(String(100), nullable=True)
    source_version = Column(String(50), nullable=True)

    # Workspace & Business Unit
    workspace_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('workspaces.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    workspace = relationship("Workspace", back_populates="connectors")
    business_unit_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('business_units.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    business_unit = relationship("BusinessUnit", back_populates="connectors")

    # Integration
    integration_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('integrations.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )

    # Status
    status = Column(
        EnumCol(ConnectorStatus),
        default=ConnectorStatus.PENDING,
        nullable=False,
        index=True
    )
    is_active = Column(Boolean, default=False)

    # Health
    health_score = Column(Integer, default=0)  # 0-100
    last_health_check = Column(DateTime, nullable=True)
    health_error = Column(Text, nullable=True)

    # Sync
    current_sync_status = Column(
        EnumCol(SyncStatus),
        default=SyncStatus.IDLE,
        nullable=False
    )
    last_sync_at = Column(DateTime, nullable=True)
    next_sync_at = Column(DateTime, nullable=True)
    sync_frequency_minutes = Column(Integer, nullable=True)
    last_sync_error = Column(Text, nullable=True)
    sync_error_count = Column(Integer, default=0)

    # Configuration
    config = Column(JSON, nullable=True)
    # Configuration includes: authentication, endpoints, mapping, etc.

    # Capabilities
    capabilities = Column(JSON, nullable=True)
    supported_operations = Column(JSON, nullable=True)
    supported_data_types = Column(JSON, nullable=True)

    # Authentication
    auth_method = Column(String(50), nullable=True)
    auth_config = Column(JSON, nullable=True)

    # Retry
    max_retries = Column(Integer, default=3)
    retry_delay = Column(Integer, default=60)  # seconds
    current_retry_count = Column(Integer, default=0)

    # Webhooks
    supports_webhooks = Column(Boolean, default=False)
    webhook_url = Column(String(500), nullable=True)

    # Data Mapping
    mapping_rules = Column(JSON, nullable=True)
    data_normalization_rules = Column(JSON, nullable=True)

    # Logging
    last_error = Column(Text, nullable=True)
    error_count = Column(Integer, default=0)

    # Metadata
    meta_data = Column("metadata", JSON, nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="connectors")
    integration = relationship("Integration")
    configs = relationship("ConnectorConfig", back_populates="connector", cascade="all, delete-orphan")
    sync_logs = relationship("ConnectorSyncLog", back_populates="connector", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        UniqueConstraint('organization_id', 'slug', name='uix_connector_organization_slug'),
        CheckConstraint(
            "status IN ('pending', 'ready', 'configuring', 'testing', 'connected', 'disconnected', 'error', 'deprecated')",
            name='chk_connector_status'
        ),
        CheckConstraint(
            "health_score BETWEEN 0 AND 100",
            name='chk_connector_health_score'
        ),
        Index('ix_connector_name', 'name'),
        Index('ix_connector_slug', 'slug'),
        Index('ix_connector_type', 'type'),
        Index('ix_connector_status', 'status'),
        Index('ix_connector_organization', 'organization_id'),
        Index('ix_connector_workspace', 'workspace_id'),
        Index('ix_connector_business_unit', 'business_unit_id'),
    )


class ConnectorConfig(Base):
    """Configuration for a connector.

    Stores per-organization/connector-specific configurations.
    """

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )
    connector_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('connectors.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Configuration Details
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    config_type = Column(String(50), nullable=False)

    # Configuration Data
    configuration = Column(JSON, nullable=True)

    # Connection Details (Encrypted at rest)
    connection_string = Column(EncryptedString, nullable=True)
    connection_details = Column(EncryptedJSON, nullable=True)

    # Authentication (Encrypted at rest)
    api_key = Column(EncryptedString, nullable=True)
    api_secret = Column(EncryptedString, nullable=True)
    oauth_token = Column(EncryptedJSON, nullable=True)
    username = Column(String(255), nullable=True)
    password = Column(EncryptedString, nullable=True)

    # Settings
    settings = Column(JSON, nullable=True)

    # Validation
    is_valid = Column(Boolean, default=False)
    validation_errors = Column(JSON, nullable=True)
    last_validated_at = Column(DateTime, nullable=True)

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
    connector = relationship("Connector", back_populates="configs")

    # Constraints
    __table_args__ = (
        Index('ix_connector_config_connector', 'connector_id'),
    )


class ConnectorSyncLog(Base):
    """Synchronization log for a connector.

    Tracks the status and results of connector synchronization.
    """

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )
    connector_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('connectors.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Sync Details
    sync_type = Column(String(50), nullable=False)
    # Types: full, incremental, delta, manual
    sync_start_time = Column(DateTime, nullable=False)
    sync_end_time = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Status
    status = Column(
        EnumCol(SyncStatus),
        nullable=False,
        index=True
    )
    error_message = Column(Text, nullable=True)

    # Results
    total_records = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    skipped_count = Column(Integer, default=0)
    records_processed = Column(JSON, nullable=True)  # Aggregated metrics

    # Change Tracking
    last_sync_token = Column(String(500), nullable=True)
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

    # Relationships
    connector = relationship("Connector", back_populates="sync_logs")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('idle', 'syncing', 'paused', 'failed', 'completed', 'partial', 'cancelled')",
            name='chk_connector_sync_status'
        ),
        Index('ix_connector_sync_log_connector', 'connector_id'),
        Index('ix_connector_sync_log_status', 'status'),
        Index('ix_connector_sync_log_sync_type', 'sync_type'),
        Index('ix_connector_sync_log_start_time', 'sync_start_time'),
    )
