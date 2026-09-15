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


class ToolCategory(str, Enum):
    """Tool categories."""
    DATABASE = "database"
    ERP = "erp"
    CRM = "crm"
    PAYMENT = "payment"
    EMAIL = "email"
    CALENDAR = "calendar"
    DOCUMENT = "document"
    WEBHOOK = "webhook"
    REPORTING = "reporting"
    NOTIFICATION = "notification"
    WORKFLOW = "workflow"
    INTEGRATION = "integration"
    API = "api"
    ANALYTICS = "analytics"
    FINANCIAL = "financial"


class ToolStatus(str, Enum):
    """Tool status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    TESTING = "testing"
    DEPRECATED = "deprecated"


class ToolPermissionLevel(str, Enum):
    """Permission levels for tools."""
    NONE = "none"
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    APPROVE = "approve"


class Tool(Base):
    """Tool represents a capability available to agents.

    Tools are the interface between agents and external systems.
    Each tool must be properly configured with schemas and permissions.
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

    # Tool Details
    name = Column(String(255), nullable=False)
    slug = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(
        SQLEnum(ToolCategory),
        default=ToolCategory.API,
        nullable=False,
        index=True
    )

    # Tool Provider
    provider = Column(String(100), nullable=True)
    provider_version = Column(String(50), nullable=True)

    # Tool Implementation
    implementation_type = Column(String(50), nullable=False)
    # Types: REST, GraphQL, SOAP, DIRECT_DB, FILE, PYTHON, PYTHON_CLASS

    # Configuration
    config = Column(JSON, nullable=True)
    endpoint_url = Column(String(500), nullable=True)
    endpoint_method = Column(String(20), nullable=True)  # GET, POST, PUT, DELETE

    # Input/Output Schemas
    input_schema = Column(JSON, nullable=True)
    output_schema = Column(JSON, nullable=True)
    input_parameters = Column(JSON, nullable=True)

    # Security
    auth_required = Column(Boolean, default=False)
    auth_type = Column(String(50), nullable=True)
    permission_level = Column(
        SQLEnum(ToolPermissionLevel),
        default=ToolPermissionLevel.READ,
        nullable=False
    )

    # Risk Assessment
    risk_level = Column(String(20), nullable=True)
    # Levels: low, medium, high, critical
    requires_approval = Column(Boolean, default=False)
    approval_threshold = Column(Integer, nullable=True)

    # Rate Limiting
    rate_limit_requests = Column(Integer, default=100)
    rate_limit_window = Column(Integer, default=60)  # seconds
    current_requests = Column(Integer, default=0)
    last_rate_limit_reset = Column(DateTime, nullable=True)

    # Timeout
    timeout_seconds = Column(Integer, default=30)

    # Retry
    max_retries = Column(Integer, default=3)
    retry_delay = Column(Integer, default=1)  # seconds

    # Status
    status = Column(
        SQLEnum(ToolStatus),
        default=ToolStatus.PENDING,
        nullable=False,
        index=True
    )
    is_active = Column(Boolean, default=False)

    # Documentation
    documentation_url = Column(String(500), nullable=True)
    example_usage = Column(JSON, nullable=True)

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
    organization = relationship("Organization", back_populates="tools")
    agent_tools = relationship("AgentTool", back_populates="tool", cascade="all, delete-orphan")
    tool_permissions = relationship("ToolPermission", back_populates="tool", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        UniqueConstraint('organization_id', 'slug', name='uix_tool_organization_slug'),
        CheckConstraint(
            "status IN ('active', 'inactive', 'pending', 'testing', 'deprecated')",
            name='chk_tool_status'
        ),
        CheckConstraint(
            "permission_level IN ('none', 'read', 'write', 'execute', 'approve')",
            name='chk_tool_permission_level'
        ),
        CheckConstraint(
            "risk_level IN ('low', 'medium', 'high', 'critical')",
            name='chk_tool_risk_level'
        ),
        Index('ix_tool_name', 'name'),
        Index('ix_tool_slug', 'slug'),
        Index('ix_tool_category', 'category'),
        Index('ix_tool_status', 'status'),
        Index('ix_tool_organization', 'organization_id'),
    )


class ToolPermission(Base):
    """Tool permission assignment for specific users/groups.

    Defines what specific users or roles can do with a tool.
    """

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )

    # Tool
    tool_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('tools.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    tool = relationship("Tool", back_populates="tool_permissions")

    # Permission Assignment
    permission_level = Column(
        SQLEnum(ToolPermissionLevel),
        default=ToolPermissionLevel.READ,
        nullable=False
    )

    # Scope
    scope_type = Column(String(50), nullable=False)
    # Types: user, role, workspace, organization
    scope_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)

    # Permission Details
    can_execute = Column(Boolean, default=False)
    can_approve = Column(Boolean, default=False)
    can_view_logs = Column(Boolean, default=True)
    can_manage = Column(Boolean, default=False)

    # Constraints
    __table_args__ = (
        UniqueConstraint('tool_id', 'scope_type', 'scope_id', name='uix_tool_permission'),
        CheckConstraint(
            "scope_type IN ('user', 'role', 'workspace', 'organization')",
            name='chk_tool_permission_scope_type'
        ),
        CheckConstraint(
            "permission_level IN ('none', 'read', 'write', 'execute', 'approve')",
            name='chk_tool_permission_permission_level'
        ),
        Index('ix_tool_permission_tool', 'tool_id'),
        Index('ix_tool_permission_scope_id', 'scope_id'),
    )
