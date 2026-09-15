from typing import List, Optional
from datetime import datetime
from sqlalchemy import (
    Float,
    Column, String, Text, Integer, Boolean, DateTime, JSON,
    ForeignKey, Index, Enum as SQLEnum, Table, UniqueConstraint, CheckConstraint
)
from sqlalchemy.orm import relationship
from enum import Enum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from uuid import uuid4

from .base import TenantIDMixin, Base


class IntegrationType(str, Enum):
    """Integration types."""
    ERP = "erp"
    CRM = "crm"
    CRM_SALESFORCE = "salesforce"
    CRM_HUBSPOT = "hubspot"
    CRM_ZOHO = "zoho"
    CRM_PIPEDRIVE = "pipedrive"
    ERP_SAP = "sap"
    ERP_ORACLE = "oracle"
    ERP_DYNAMICS = "dynamics"
    ERP_TALLY = "tally"
    ERP_ODOO = "odoo"
    ERP_CUSTOM = "erp_custom"
    E_COMMERCE = "ecommerce"
    E_COMMERCE_SHOPIFY = "shopify"
    E_COMMERCE_MAGENTO = "magento"
    E_COMMERCE_WOOCommerce = "woocommerce"
    E_COMMERCE_CUSTOM = "ecommerce_custom"
    DATABASE = "database"
    DATABASE_POSTGRESQL = "postgresql"
    DATABASE_MYSQL = "mysql"
    DATABASE_SQLSERVER = "sqlserver"
    DATABASE_ORACLE = "oracle"
    DATABASE_CUSTOM = "database_custom"
    API = "api"
    API_REST = "rest"
    API_GRAPHQL = "graphql"
    API_CUSTOM = "api_custom"
    FILE = "file"
    FILE_CSV = "csv"
    FILE_EXCEL = "excel"
    FILE_CUSTOM = "file_custom"
    KNOWLEDGE_BASE = "knowledge"
    KNOWLEDGE_CONFLUENCE = "confluence"
    KNOWLEDGE_NOTION = "notion"
    KNOWLEDGE_CUSTOM = "knowledge_custom"


class IntegrationStatus(str, Enum):
    """Integration status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    TESTING = "testing"
    FAILED = "failed"
    SUSPENDED = "suspended"


class IntegrationConnection(Base):
    """Connection configuration for an integration.

    Stores authentication credentials, connection details, and
    connection health status.
    """

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )
    integration_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('integrations.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Connection Details
    connection_name = Column(String(255), nullable=False)
    connection_type = Column(
        SQLEnum(IntegrationType),
        default=IntegrationType.API,
        nullable=False,
        index=True
    )
    connection_config = Column(JSON, nullable=True)  # Auth details, endpoints, etc.

    # Authentication
    api_key = Column(String(500), nullable=True)
    api_secret = Column(String(500), nullable=True)  # Encrypted
    oauth_token = Column(JSON, nullable=True)  # Access token, refresh token
    username = Column(String(255), nullable=True)
    password = Column(String(500), nullable=True)  # Encrypted
    connection_string = Column(Text, nullable=True)  # Encrypted

    # Status
    status = Column(
        SQLEnum(IntegrationStatus),
        default=IntegrationStatus.INACTIVE,
        nullable=False,
        index=True
    )
    is_verified = Column(Boolean, default=False)
    last_verified_at = Column(DateTime, nullable=True)
    last_verified_by = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )
    verification_notes = Column(Text, nullable=True)

    # Health
    health_status = Column(String(50), nullable=True)
    health_score = Column(Integer, nullable=True)  # 0-100
    last_health_check_at = Column(DateTime, nullable=True)
    health_error = Column(Text, nullable=True)

    # Rate Limiting
    rate_limit = Column(Integer, nullable=True)  # Requests per minute
    rate_limit_window = Column(Integer, nullable=True)  # Window in seconds
    current_requests = Column(Integer, default=0)
    last_rate_limit_reset = Column(DateTime, nullable=True)

    # Retry
    max_retries = Column(Integer, default=3)
    retry_count = Column(Integer, default=0)
    last_retry_at = Column(DateTime, nullable=True)
    last_retry_error = Column(Text, nullable=True)

    # Sync
    last_sync_at = Column(DateTime, nullable=True)
    next_sync_at = Column(DateTime, nullable=True)
    sync_frequency_minutes = Column(Integer, nullable=True)

    # Webhooks
    has_webhooks = Column(Boolean, default=False)
    webhook_url = Column(String(500), nullable=True)
    webhook_secret = Column(String(500), nullable=True)  # Encrypted

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
    integration = relationship("Integration", foreign_keys=[integration_id], back_populates="connections")
    data_sources = relationship("DataSource", back_populates="connection")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "health_score BETWEEN 0 AND 100",
            name='chk_health_score'
        ),
        Index('ix_integration_connection_status', 'status'),
        Index('ix_integration_connection_type', 'connection_type'),
    )


class Integration(Base):
    """Integration represents a connected external system.

    Integrations connect the platform to various external systems
    including ERPs, CRMs, databases, and APIs.
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

    # Integration Details
    name = Column(String(255), nullable=False)
    slug = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String(100), nullable=True)
    category = Column(String(100), nullable=True)

    # Integration Type
    type = Column(
        SQLEnum(IntegrationType),
        default=IntegrationType.API,
        nullable=False,
        index=True
    )

    # Provider (specific integration)
    provider = Column(String(100), nullable=True)

    # Integration Version
    integration_version = Column(String(50), nullable=True)

    # Source System
    source_system = Column(String(100), nullable=True)
    source_url = Column(String(500), nullable=True)

    # Workspace & Business Unit
    workspace_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('workspaces.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    workspace = relationship("Workspace", back_populates="integrations")
    business_unit_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('business_units.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    business_unit = relationship("BusinessUnit", back_populates="integrations")

    # Integration Details
    api_endpoint = Column(String(500), nullable=True)
    api_version = Column(String(50), nullable=True)
    api_method = Column(String(20), nullable=True)  # REST, GraphQL, SOAP
    authentication_method = Column(String(50), nullable=True)

    # Capabilities
    capabilities = Column(JSON, nullable=True)
    supported_features = Column(JSON, nullable=True)
    supported_data_types = Column(JSON, nullable=True)

    # Status
    status = Column(
        SQLEnum(IntegrationStatus),
        default=IntegrationStatus.INACTIVE,
        nullable=False,
        index=True
    )
    is_active = Column(Boolean, default=False)
    priority = Column(Integer, default=100)  # Higher priority for critical integrations

    # Settings
    settings = Column(JSON, nullable=True)
    mapping_rules = Column(JSON, nullable=True)  # Data mapping configurations

    # Usage
    total_requests = Column(Integer, default=0)
    last_request_at = Column(DateTime, nullable=True)
    total_errors = Column(Integer, default=0)

    # Connection
    primary_connection_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('integration_connections.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    primary_connection = relationship("IntegrationConnection", foreign_keys=[primary_connection_id])

    # Relationships
    organization = relationship("Organization", back_populates="integrations")
    connections = relationship("IntegrationConnection", foreign_keys="IntegrationConnection.integration_id", back_populates="integration", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        UniqueConstraint('organization_id', 'slug', name='uix_integration_organization_slug'),
        CheckConstraint(
            "status IN ('active', 'inactive', 'pending', 'testing', 'failed', 'suspended')",
            name='chk_integration_status'
        ),
        Index('ix_integration_name', 'name'),
        Index('ix_integration_slug', 'slug'),
        Index('ix_integration_type', 'type'),
        Index('ix_integration_status', 'status'),
        Index('ix_integration_organization', 'organization_id'),
        Index('ix_integration_workspace', 'workspace_id'),
        Index('ix_integration_business_unit', 'business_unit_id'),
    )
