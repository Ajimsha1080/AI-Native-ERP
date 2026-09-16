"""
Agent execution, tool execution audit log, and human-in-the-loop pending approvals models.
"""

from enum import Enum as PyEnum
from sqlalchemy import (
    Column, String, Text, Integer, Numeric, DateTime, JSON,
    ForeignKey, Index, Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from packages.database.models.base import Base, UUIDMixin, TimestampMixin


class ApprovalStatus(str, PyEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class AgentRun(Base):
    """Full execution audit log for a LangGraph agent run."""
    __tablename__ = "agent_runs"

    organization_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    graph_name = Column(String(100), nullable=False, default="erp_supervisor")
    prompt = Column(Text, nullable=False)
    status = Column(String(50), nullable=False, default="running")
    response = Column(Text, nullable=True)

    # Metrics & Cost Tracking
    token_input = Column(Integer, nullable=False, default=0)
    token_output = Column(Integer, nullable=False, default=0)
    cost_usd = Column(Numeric(10, 6), nullable=False, default=0)
    latency_ms = Column(Integer, nullable=False, default=0)

    # Relationships
    tool_executions = relationship("ToolExecution", back_populates="run", cascade="all, delete-orphan")
    pending_approvals = relationship("PendingApproval", back_populates="run", cascade="all, delete-orphan")


class ToolExecution(Base):
    """Audit log for a specific tool call executed during an agent run."""
    __tablename__ = "tool_executions"

    organization_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    tool_name = Column(String(100), nullable=False)
    inputs = Column(JSON, nullable=False, default=dict)
    output = Column(JSON, nullable=True)
    status = Column(String(50), nullable=False, default="success")
    latency_ms = Column(Integer, nullable=False, default=0)

    # Relationships
    run = relationship("AgentRun", back_populates="tool_executions")


class PendingApproval(Base):
    """High-risk action requiring human sign-off before tool execution."""
    __tablename__ = "pending_approvals"

    organization_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    tool_name = Column(String(100), nullable=False)
    inputs = Column(JSON, nullable=False, default=dict)
    status = Column(
        SAEnum(ApprovalStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ApprovalStatus.PENDING,
    )
    risk_level = Column(String(50), nullable=False, default="high")
    reason = Column(Text, nullable=True)

    approved_by_id = Column(PG_UUID(as_uuid=True), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    execution_result = Column(JSON, nullable=True)

    # Relationships
    run = relationship("AgentRun", back_populates="pending_approvals")
