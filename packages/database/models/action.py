from typing import List, Optional
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Integer, Boolean, DateTime, JSON, Float,
    ForeignKey, Index, Enum as SQLEnum, UniqueConstraint, CheckConstraint
)
from sqlalchemy.orm import relationship
from enum import Enum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from uuid import uuid4


from .base import TenantIDMixin, Base, EnumCol


class ActionType(str, Enum):
    """Action types."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    APPROVE = "approve"
    REJECT = "reject"
    EXECUTE = "execute"
    VERIFY = "verify"
    EXPORT = "export"
    IMPORT = "import"
    SYNC = "sync"
    NOTIFY = "notify"
    REPORT = "report"
    ANALYZE = "analyze"


class ActionStatus(str, Enum):
    """Action status."""
    PROPOSED = "proposed"
    APPROVAL_REQUIRED = "approval_required"
    APPROVED = "approved"
    EXECUTING = "executing"
    EXECUTED = "executed"
    VERIFIED = "verified"
    REJECTED = "rejected"
    FAILED = "failed"
    TIMEOUT = "timeout"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class Action(Base):
    """Action represents a business action performed by an agent.

    Every action goes through a lifecycle: Proposed → Approval → Approved → Executed → Verified.
    Actions must be idempotent to prevent duplicate execution.
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

    # Action Details
    action_type = Column(
        EnumCol(ActionType),
        default=ActionType.CREATE,
        nullable=False,
        index=True
    )
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Source
    agent_execution_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('agent_executions.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    agent_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('agents.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )

    # User
    requested_by_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )

    # Action Content
    action_data = Column(JSON, nullable=True)
    # The actual data for the action (e.g., purchase order details)

    # Policy Check Results
    policy_compliant = Column(Boolean, default=True)
    policy_errors = Column(JSON, nullable=True)
    policy_warnings = Column(JSON, nullable=True)

    # Approval
    requires_approval = Column(Boolean, default=False)
    approval_level = Column(String(50), nullable=True)
    approval_status = Column(String(50), nullable=True)

    # Status
    status = Column(
        EnumCol(ActionStatus),
        default=ActionStatus.PROPOSED,
        nullable=False,
        index=True
    )

    # Verification
    is_verified = Column(Boolean, default=False)
    verification_data = Column(JSON, nullable=True)
    verification_error = Column(Text, nullable=True)

    # Lifecycle
    proposed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    approved_at = Column(DateTime, nullable=True)
    approved_by_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )
    executed_at = Column(DateTime, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    verified_by_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )

    # Retry
    retry_count = Column(Integer, default=0)
    last_retry_at = Column(DateTime, nullable=True)
    last_retry_error = Column(Text, nullable=True)

    # Execution Results
    execution_result = Column(JSON, nullable=True)
    execution_error = Column(Text, nullable=True)

    # Idempotency
    idempotency_key = Column(String(500), nullable=True, unique=True, index=True)

    # Retry
    max_retries = Column(Integer, default=3)
    current_retry = Column(Integer, default=0)

    # Cost
    estimated_cost = Column(Float, default=0.0)
    actual_cost = Column(Float, default=0.0)

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
    organization = relationship("Organization", back_populates="actions")
    agent_execution = relationship("AgentExecution", back_populates="actions")
    agent = relationship("Agent", back_populates="actions")
    requested_by = relationship("User", foreign_keys=[requested_by_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    verification_by = relationship("User", foreign_keys=[verified_by_id])
    approvals = relationship("Approval", back_populates="action", cascade="all, delete-orphan")
    execution_logs = relationship("ActionExecutionLog", back_populates="action", cascade="all, delete-orphan")
    audit_logs = relationship("AuditEvent")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('proposed', 'approval_required', 'approved', 'executing', 'executed', 'verified', 'rejected', 'failed', 'timeout', 'rolled_back', 'cancelled')",
            name='chk_action_status'
        ),
        CheckConstraint(
            "retry_count >= 0 AND current_retry >= 0",
            name='chk_action_retry'
        ),
        Index('ix_action_idempotency_key', 'idempotency_key'),
        Index('ix_action_status', 'status'),
        Index('ix_action_type', 'action_type'),
        Index('ix_action_organization', 'organization_id'),
        Index('ix_action_agent', 'agent_id'),
        Index('ix_action_requested_by', 'requested_by_id'),
    )


class Approval(Base):
    """Approval request for an action.

    Handles the approval workflow for high-risk or sensitive actions.
    """

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )

    # Action
    action_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('actions.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    action = relationship("Action", back_populates="approvals")

    # Approver
    approver_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    approver = relationship("User", foreign_keys=[approver_id], back_populates="approvals")

    # Approval Details
    approver_role_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('user_roles.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )

    # Approval Status
    status = Column(String(50), nullable=False)
    # Status: pending, approved, rejected, revoked

    # Rationale
    justification = Column(Text, nullable=True)
    comments = Column(JSON, nullable=True)  # Additional comments from approver

    # Approval Type
    approval_type = Column(String(50), nullable=True)
    # Types: manager, financial, operations, security

    # Approval History
    approval_chain = Column(JSON, nullable=True)
    approver_sequence = Column(Integer, nullable=True)

    # Actions
    action_on_action = Column(String(50), nullable=True)
    # Actions: approve, reject, request_changes, delegate

    # Delegation
    delegated_to_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )
    delegation_notes = Column(Text, nullable=True)

    # Timestamps
    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    delegated_to = relationship("User", foreign_keys=[delegated_to_id])

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'revoked')",
            name='chk_approval_status'
        ),
        Index('ix_approval_action', 'action_id'),
        Index('ix_approval_approver', 'approver_id'),
        Index('ix_approval_status', 'status'),
    )


class ActionExecutionLog(Base):
    """Execution log for an action.

    Tracks all execution attempts and results.
    """

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )

    # Action
    action_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('actions.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    action = relationship("Action", back_populates="execution_logs")

    # Execution Details
    execution_type = Column(String(50), nullable=False)
    # Types: initial, retry, verification

    status = Column(String(50), nullable=False)
    error_message = Column(Text, nullable=True)

    # Results
    success = Column(Boolean, nullable=False)
    response_data = Column(JSON, nullable=True)
    response_time_ms = Column(Integer, nullable=True)

    # Tool Used
    tool_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('tools.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    tool_name = Column(String(255), nullable=True)

    # Retry
    retry_count = Column(Integer, default=0)
    retry_at = Column(DateTime, nullable=True)

    # Timestamps
    executed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    tool = relationship("Tool")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "execution_type IN ('initial', 'retry', 'verification')",
            name='chk_action_execution_type'
        ),
        CheckConstraint(
            "status IN ('success', 'failed')",
            name='chk_action_execution_status'
        ),
        Index('ix_action_execution_log_action', 'action_id'),
        Index('ix_action_execution_log_tool', 'tool_id'),
    )
