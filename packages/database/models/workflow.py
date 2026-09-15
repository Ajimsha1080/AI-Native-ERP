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


class WorkflowType(str, Enum):
    """Workflow types."""
    AGENT = "agent"
    MANUAL = "manual"
    AUTOMATED = "automated"
    CONDITIONAL = "conditional"
    EVENT_DRIVEN = "event_driven"


class WorkflowStatus(str, Enum):
    """Workflow status."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    TESTING = "testing"
    ARCHIVED = "archived"
    FAILED = "failed"


class WorkflowTriggerType(str, Enum):
    """Workflow trigger types."""
    SCHEDULE = "schedule"
    WEBHOOK = "webhook"
    EVENT = "event"
    MANUAL = "manual"
    CONDITION = "condition"
    TIME_TRIGGER = "time_trigger"


class WorkflowStepType(str, Enum):
    """Workflow step types."""
    AGENT = "agent"
    HUMAN_APPROVAL = "human_approval"
    CONDITION = "condition"
    ACTION = "action"
    FOR_LOOP = "for_loop"
    PARALLEL = "parallel"
    ERROR_HANDLER = "error_handler"


class Workflow(Base):
    """Workflow represents a business process workflow.

    Workflows define the sequence of steps and actions that must
    be completed to achieve a business goal.
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

    # Workflow Details
    name = Column(String(255), nullable=False)
    slug = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    display_name = Column(String(255), nullable=True)
    icon = Column(String(100), nullable=True)

    # Workflow Type
    type = Column(
        EnumCol(WorkflowType),
        default=WorkflowType.AGENT,
        nullable=False,
        index=True
    )

    # Category
    category = Column(String(100), nullable=True)
    # Categories: finance, procurement, inventory, sales, hr, operations

    # Source
    workspace_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('workspaces.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    workspace = relationship("Workspace", back_populates="workflows")

    business_unit_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('business_units.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    business_unit = relationship("BusinessUnit", back_populates="workflows")

    team_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('teams.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    team = relationship("Team", back_populates="workflows")

    # Trigger
    trigger_type = Column(
        EnumCol(WorkflowTriggerType),
        default=WorkflowTriggerType.EVENT,
        nullable=False,
        index=True
    )
    trigger_config = Column(JSON, nullable=True)
    # Configuration for trigger (schedule, webhook, event, etc.)

    # Execution
    timeout_seconds = Column(Integer, default=3600)
    max_retries = Column(Integer, default=3)
    retry_delay = Column(Integer, default=60)

    # Status
    status = Column(
        EnumCol(WorkflowStatus),
        default=WorkflowStatus.DRAFT,
        nullable=False,
        index=True
    )
    is_active = Column(Boolean, default=False)

    # Execution Statistics
    total_executions = Column(Integer, default=0)
    successful_executions = Column(Integer, default=0)
    failed_executions = Column(Integer, default=0)
    average_duration_seconds = Column(Float, default=0.0)
    last_execution_at = Column(DateTime, nullable=True)
    last_execution_result = Column(String(50), nullable=True)

    # Definition
    definition = Column(JSON, nullable=True)
    # Workflow definition in JSON format with steps, conditions, branches

    # Settings
    settings = Column(JSON, nullable=True)
    # Workflow-specific settings

    # Approval
    requires_approval = Column(Boolean, default=False)
    approval_required_steps = Column(JSON, nullable=True)

    # Error Handling
    error_handling = Column(JSON, nullable=True)
    # Error handling configuration (retry, skip, stop, continue)

    # Documentation
    documentation_url = Column(String(500), nullable=True)
    example_usage = Column(Text, nullable=True)

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
    organization = relationship("Organization", back_populates="workflows")
    steps = relationship("WorkflowStep", back_populates="workflow", cascade="all, delete-orphan")
    executions = relationship("WorkflowExecution", back_populates="workflow", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        UniqueConstraint('organization_id', 'slug', name='uix_workflow_organization_slug'),
        CheckConstraint(
            "status IN ('draft', 'active', 'paused', 'testing', 'archived', 'failed')",
            name='chk_workflow_status'
        ),
        Index('ix_workflow_name', 'name'),
        Index('ix_workflow_slug', 'slug'),
        Index('ix_workflow_type', 'type'),
        Index('ix_workflow_status', 'status'),
        Index('ix_workflow_organization', 'organization_id'),
        Index('ix_workflow_workspace', 'workspace_id'),
        Index('ix_workflow_business_unit', 'business_unit_id'),
    )


class WorkflowStep(Base):
    """Workflow step definition.

    Each step in a workflow represents an action or condition.
    """

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )

    # Workflow
    workflow_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('workflows.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    workflow = relationship("Workflow", back_populates="steps")

    # Step Details
    step_name = Column(String(255), nullable=False)
    step_description = Column(Text, nullable=True)
    step_number = Column(Integer, nullable=False)

    # Step Type
    type = Column(
        EnumCol(WorkflowStepType),
        nullable=False,
        index=True
    )

    # Step Configuration
    config = Column(JSON, nullable=True)
    # Configuration specific to step type

    # Dependencies
    depends_on = Column(JSON, nullable=True)  # List of step IDs to wait for
    parallel_steps = Column(JSON, nullable=True)  # List of parallel step IDs

    # Timeout
    timeout_seconds = Column(Integer, default=300)

    # Success/Failure Behavior
    on_success = Column(String(100), nullable=True)
    on_failure = Column(String(100), nullable=True)

    # Conditions
    condition = Column(JSON, nullable=True)
    # JSON boolean expression or conditions

    # Agent Configuration
    agent_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('agents.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    agent = relationship("Agent")

    # Approval Configuration
    requires_approval = Column(Boolean, default=False)
    approval_conditions = Column(JSON, nullable=True)

    # Error Handler
    error_handler_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('workflow_steps.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    error_handler = relationship("WorkflowStep", remote_side="WorkflowStep.id")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "type IN ('agent', 'human_approval', 'condition', 'action', 'for_loop', 'parallel', 'error_handler')",
            name='chk_workflow_step_type'
        ),
        CheckConstraint(
            "step_number > 0",
            name='chk_workflow_step_number'
        ),
        Index('ix_workflow_step_workflow', 'workflow_id'),
        Index('ix_workflow_step_number', 'step_number'),
        Index('ix_workflow_step_type', 'type'),
        Index('ix_workflow_step_agent', 'agent_id'),
    )


class WorkflowExecution(Base):
    """Workflow execution record.

    Tracks the execution of a workflow.
    """

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )

    # Workflow
    workflow_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('workflows.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    workflow = relationship("Workflow", back_populates="executions")

    # Trigger
    trigger_type = Column(String(50), nullable=False)
    trigger_data = Column(JSON, nullable=True)
    triggered_by_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )

    # Status
    status = Column(String(50), nullable=False)
    # Status: running, completed, failed, cancelled, paused

    # Results
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    # Timing
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Statistics
    steps_completed = Column(Integer, default=0)
    steps_failed = Column(Integer, default=0)
    steps_skipped = Column(Integer, default=0)
    total_steps = Column(Integer, nullable=True)

    # Progress
    progress_percentage = Column(Integer, default=0)

    # Step Execution Logs
    step_logs = Column(JSON, nullable=True)

    # Retry
    retry_count = Column(Integer, default=0)
    retry_at = Column(DateTime, nullable=True)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    triggered_by = relationship("User")
    step_executions = relationship("WorkflowStepExecution", back_populates="workflow_execution", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'cancelled', 'paused')",
            name='chk_workflow_execution_status'
        ),
        Index('ix_workflow_execution_workflow', 'workflow_id'),
        Index('ix_workflow_execution_triggered_by', 'triggered_by_id'),
        Index('ix_workflow_execution_status', 'status'),
        Index('ix_workflow_execution_started_at', 'started_at'),
    )


class WorkflowStepExecution(Base):
    """Execution log for a workflow step."""

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )

    # Workflow Execution
    workflow_execution_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('workflow_executions.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    workflow_execution = relationship("WorkflowExecution", back_populates="step_executions")

    # Step
    step_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('workflow_steps.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    step = relationship("WorkflowStep")

    # Execution Details
    status = Column(String(50), nullable=False)
    error_message = Column(Text, nullable=True)

    # Results
    output = Column(JSON, nullable=True)

    # Timing
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Agent/Action
    agent_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('agents.id', ondelete='SET NULL'),
        nullable=True
    )
    agent = relationship("Agent")

    # Approval
    approval_status = Column(String(50), nullable=True)
    approver_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )

    # Retry
    retry_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    approver = relationship("User")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'skipped', 'pending')",
            name='chk_workflow_step_execution_status'
        ),
        Index('ix_workflow_step_execution_workflow_exec', 'workflow_execution_id'),
        Index('ix_workflow_step_execution_step', 'step_id'),
    )
