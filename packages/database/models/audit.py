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


class AuditEventType(str, Enum):
    """Audit event types."""
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    USER_ROLE_ASSIGN = "user_role_assign"
    USER_ROLE_REMOVE = "user_role_remove"
    AGENT_CREATE = "agent_create"
    AGENT_UPDATE = "agent_update"
    AGENT_DELETE = "agent_delete"
    AGENT_EXECUTE = "agent_execute"
    ACTION_CREATE = "action_create"
    ACTION_APPROVE = "action_approve"
    ACTION_REJECT = "action_reject"
    ACTION_EXECUTE = "action_execute"
    ACTION_VERIFY = "action_verify"
    ACTION_FAILED = "action_failed"
    CONNECTOR_CONNECT = "connector_connect"
    CONNECTOR_SYNC = "connector_sync"
    DATA_SOURCE_SYNC = "data_source_sync"
    WORKFLOW_EXECUTE = "workflow_execute"
    WORKFLOW_STEP = "workflow_step"
    TOOL_EXECUTE = "tool_execute"
    POLICY_CHECK = "policy_check"
    PERMISSION_CHECK = "permission_check"
    DOCUMENT_UPLOAD = "document_upload"
    DOCUMENT_DELETE = "document_delete"
    KNOWLEDGE_SEARCH = "knowledge_search"
    SETTINGS_UPDATE = "settings_update"
    BILLING_UPDATE = "billing_update"
    SECURITY_ALERT = "security_alert"
    SYSTEM_ERROR = "system_error"
    CONFIGURATION_CHANGE = "configuration_change"
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    AGENT_EXECUTION = "agent_execution"
    ACTION_CREATION = "action_creation"
    ACTION_APPROVAL = "action_approval"
    ACTION_EXECUTION = "action_execution"
    DATA_SYNC = "data_sync"
    WORKFLOW_EXECUTION = "workflow_execution"
    SECURITY_EVENT = "security_event"
    SYSTEM_EVENT = "system_event"


class AuditEvent(Base):
    """Audit event record.

    Tracks all significant events in the system for auditability.
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

    # Event Details
    event_type = Column(
        EnumCol(AuditEventType),
        default=AuditEventType.LOGIN,
        nullable=False,
        index=True
    )
    event_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # User
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    user_email = Column(String(255), nullable=True)
    user_role = Column(String(100), nullable=True)

    # Request
    request_id = Column(String(255), nullable=True, index=True)
    trace_id = Column(String(255), nullable=True, index=True)
    session_id = Column(String(255), nullable=True, index=True)

    # IP Address
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    country = Column(String(100), nullable=True)
    region = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)

    # Resource
    resource_type = Column(String(100), nullable=True)
    resource_id = Column(String(500), nullable=True)
    resource_name = Column(String(255), nullable=True)
    resource_action = Column(String(100), nullable=True)

    # Action Details
    action_data = Column(JSON, nullable=True)
    result = Column(String(50), nullable=True)
    # Result: success, failure, warning, error

    # Metadata
    meta_data = Column("metadata", JSON, nullable=True)
    # Additional context about the event

    # Timing
    event_time = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Error (if applicable)
    error_code = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)

    # Resource Relationships
    agent_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('agents.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    agent_name = Column(String(255), nullable=True)

    action_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('actions.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    action_type = Column(String(100), nullable=True)

    workflow_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('workflows.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    workflow_name = Column(String(255), nullable=True)

    tool_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('tools.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    tool_name = Column(String(255), nullable=True)

    connector_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('connectors.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    connector_name = Column(String(255), nullable=True)

    document_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('documents.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    document_name = Column(String(255), nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="audit_events")
    user = relationship("User", back_populates="audit_logs")
    agent = relationship("Agent")
    action = relationship("Action", overlaps="audit_logs")
    workflow = relationship("Workflow")
    tool = relationship("Tool")
    connector = relationship("Connector")
    document = relationship("Document", back_populates="audit_logs")
    logs = relationship("AuditLog", back_populates="event", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "result IN ('success', 'failure', 'warning', 'error')",
            name='chk_audit_event_result'
        ),
        Index('ix_audit_event_type', 'event_type'),
        Index('ix_audit_event_user', 'user_id'),
        Index('ix_audit_event_request', 'request_id'),
        Index('ix_audit_event_trace', 'trace_id'),
        Index('ix_audit_event_session', 'session_id'),
        Index('ix_audit_event_time', 'event_time'),
        Index('ix_audit_event_resource', 'resource_type', 'resource_id'),
    )


class AuditLog(Base):
    """Detailed audit log.

    Provides more detailed tracking of specific operations.
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

    # Reference
    organization = relationship("Organization", back_populates="audit_logs")
    event_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('audit_events.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    event = relationship("AuditEvent", back_populates="logs")

    # Log Details
    log_level = Column(String(20), nullable=False)
    # Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

    message = Column(Text, nullable=False)
    stack_trace = Column(Text, nullable=True)

    # Context
    context = Column(JSON, nullable=True)
    # Additional context for the log entry

    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Trace ID
    correlation_id = Column(String(255), nullable=True)

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "log_level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')",
            name='chk_audit_log_level'
        ),
        CheckConstraint(
            "timestamp <= CURRENT_TIMESTAMP",
            name='chk_audit_log_timestamp'
        ),
        Index('ix_audit_log_event', 'event_id'),
        Index('ix_audit_log_level', 'log_level'),
        Index('ix_audit_log_timestamp', 'timestamp'),
        Index('ix_audit_log_correlation', 'correlation_id'),
    )
