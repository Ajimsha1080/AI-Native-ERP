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


class AgentType(str, Enum):
    """Agent types."""
    GENERAL = "general"
    FINANCE = "finance"
    INVENTORY = "inventory"
    PROCUREMENT = "procurement"
    SALES = "sales"
    OPERATIONS = "operations"
    HR = "hr"
    CUSTOM = "custom"


class AgentStatus(str, Enum):
    """Agent status."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    TESTING = "testing"
    FAILED = "failed"
    ARCHIVED = "archived"


class AgentExecutionStatus(str, Enum):
    """Agent execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class Agent(Base):
    """Agent represents an AI agent in the system.

    Agents are autonomous entities that can reason over data,
    retrieve information, propose actions, and execute approved actions.
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
    team_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('teams.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    owner_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )

    # Agent Details
    name = Column(String(255), nullable=False)
    slug = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    display_name = Column(String(255), nullable=True)
    icon = Column(String(100), nullable=True)

    # Agent Type
    type = Column(
        EnumCol(AgentType),
        default=AgentType.GENERAL,
        nullable=False,
        index=True
    )

    # Agent Configuration
    config = Column(JSON, nullable=True)
    # Configuration includes: model, temperature, max_tokens, etc.

    # Model Configuration
    model_provider = Column(String(50), nullable=True)
    model_name = Column(String(100), nullable=True)
    model_temperature = Column(Float, default=0.7)
    model_max_tokens = Column(Integer, default=4000)

    # Instructions
    system_prompt = Column(Text, nullable=True)
    tool_instructions = Column(Text, nullable=True)
    policy_instructions = Column(Text, nullable=True)
    retrieval_instructions = Column(Text, nullable=True)

    # Tools
    tools_enabled = Column(Boolean, default=True)
    available_tools = Column(JSON, nullable=True)  # List of tool IDs
    tool_selection_strategy = Column(String(50), default="auto")
    # Strategies: auto, manual, predefined

    # Retrieval
    retrieval_enabled = Column(Boolean, default=True)
    knowledge_bases = Column(JSON, nullable=True)  # List of knowledge base IDs
    retrieval_top_k = Column(Integer, default=5)
    retrieval_threshold = Column(Float, default=0.7)

    # Workflow
    workflow_enabled = Column(Boolean, default=False)
    workflow_definition = Column(JSON, nullable=True)

    # Permissions
    requires_approval = Column(Boolean, default=False)
    approval_threshold = Column(Integer, nullable=True)
    spending_limit = Column(Integer, nullable=True)

    # Execution Limits
    max_execution_steps = Column(Integer, default=10)
    timeout_seconds = Column(Integer, default=300)
    rate_limit_requests = Column(Integer, default=100)
    rate_limit_window = Column(Integer, default=60)  # seconds

    # Retry Policy
    max_retries = Column(Integer, default=3)
    retry_delay = Column(Integer, default=1)  # seconds

    # Status
    status = Column(
        EnumCol(AgentStatus),
        default=AgentStatus.DRAFT,
        nullable=False,
        index=True
    )
    is_active = Column(Boolean, default=False)

    # Performance
    success_rate = Column(Float, default=0.0)
    total_executions = Column(Integer, default=0)
    successful_executions = Column(Integer, default=0)
    failed_executions = Column(Integer, default=0)
    average_latency_seconds = Column(Float, default=0.0)

    # Cost Tracking
    total_tokens_used = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    cost_per_1000_tokens = Column(Float, nullable=True)

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
    organization = relationship("Organization", back_populates="agents")
    workspace = relationship("Workspace", back_populates="agents")
    business_unit = relationship("BusinessUnit", back_populates="agents")
    team = relationship("Team", back_populates="agents")
    owner = relationship("User", foreign_keys=[owner_id], back_populates="agents")
    agent_tools = relationship("AgentTool", back_populates="agent", cascade="all, delete-orphan")
    executions = relationship("AgentExecution", back_populates="agent", cascade="all, delete-orphan")
    actions = relationship("Action", back_populates="agent", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        UniqueConstraint('organization_id', 'slug', name='uix_agent_organization_slug'),
        CheckConstraint(
            "status IN ('draft', 'active', 'paused', 'testing', 'failed', 'archived')",
            name='chk_agent_status'
        ),
        CheckConstraint(
            "model_temperature BETWEEN 0 AND 2",
            name='chk_agent_temperature'
        ),
        CheckConstraint(
            "model_max_tokens > 0",
            name='chk_agent_max_tokens'
        ),
        Index('ix_agent_name', 'name'),
        Index('ix_agent_slug', 'slug'),
        Index('ix_agent_type', 'type'),
        Index('ix_agent_status', 'status'),
        Index('ix_agent_organization', 'organization_id'),
        Index('ix_agent_workspace', 'workspace_id'),
        Index('ix_agent_business_unit', 'business_unit_id'),
    )


class AgentTool(Base):
    """Agent-tool association.

    Defines which tools are available to a specific agent.
    """

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )

    # Agent
    agent_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('agents.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    agent = relationship("Agent", back_populates="agent_tools")

    # Tool
    tool_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('tools.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    tool = relationship("Tool", back_populates="agent_tools")

    # Tool Configuration
    enabled = Column(Boolean, default=True)
    tool_config = Column(JSON, nullable=True)
    # Custom configuration for this agent-tool combination

    # Constraints
    __table_args__ = (
        UniqueConstraint('agent_id', 'tool_id', name='uix_agent_tool'),
        Index('ix_agent_tool_agent', 'agent_id'),
        Index('ix_agent_tool_tool', 'tool_id'),
    )


class AgentExecution(Base):
    """Agent execution record.

    Tracks the execution of an agent and its results.
    """

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )
    agent_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('agents.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    agent = relationship("Agent", back_populates="executions")

    # User
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )

    # Execution Details
    status = Column(
        EnumCol(AgentExecutionStatus),
        default=AgentExecutionStatus.PENDING,
        nullable=False,
        index=True
    )

    # Prompt
    prompt = Column(Text, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    prompt_model = Column(String(100), nullable=True)

    # Execution Results
    output = Column(Text, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    # Execution Steps
    execution_steps = Column(JSON, nullable=True)  # List of steps taken
    tools_used = Column(JSON, nullable=True)  # List of tool IDs used
    knowledge_used = Column(JSON, nullable=True)  # List of knowledge bases used

    # Timing
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Retry
    retry_count = Column(Integer, default=0)
    retry_at = Column(DateTime, nullable=True)

    # Context
    context = Column(JSON, nullable=True)  # Additional context
    parameters = Column(JSON, nullable=True)  # Input parameters

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="agent_executions")
    actions = relationship("Action", back_populates="agent_execution", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'timeout', 'cancelled')",
            name='chk_agent_execution_status'
        ),
        Index('ix_agent_execution_agent', 'agent_id'),
        Index('ix_agent_execution_user', 'user_id'),
        Index('ix_agent_execution_status', 'status'),
        Index('ix_agent_execution_started_at', 'started_at'),
    )
