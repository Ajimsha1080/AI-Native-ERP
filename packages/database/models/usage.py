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


from .base import TenantIDMixin, Base


class UsageMetricType(str, Enum):
    """Usage metric types."""
    AGENT_EXECUTION = "agent_execution"
    TOKEN_USAGE = "token_usage"
    ACTION_EXECUTION = "action_execution"
    TOOL_CALL = "tool_call"
    DOCUMENT_UPLOAD = "document_upload"
    KNOWLEDGE_SEARCH = "knowledge_search"
    WORKFLOW_EXECUTION = "workflow_execution"
    API_REQUEST = "api_request"
    DATA_SYNC = "data_sync"
    USER_LOGIN = "user_login"


class UsageMetricUnit(str, Enum):
    """Usage metric units."""
    COUNT = "count"
    SECONDS = "seconds"
    BYTES = "bytes"
    TOKENS = "tokens"
    DOLLARS = "dollars"


class UsageMetric(Base):
    """Usage metric tracking.

    Tracks various usage metrics across the platform.
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

    # Metric Details
    metric_type = Column(
        SQLEnum(UsageMetricType),
        default=UsageMetricType.AGENT_EXECUTION,
        nullable=False,
        index=True
    )
    metric_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)


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

    # User Context
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    agent_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('agents.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    action_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('actions.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )

    # Metric Value
    value = Column(Integer, nullable=False)
    unit = Column(String(50), nullable=True)

    # Context Data
    context = Column(JSON, nullable=True)  # Additional context

    # Aggregation
    aggregation_period = Column(String(20), nullable=True)
    # Types: hourly, daily, weekly, monthly, yearly

    aggregation_date = Column(DateTime, nullable=False, index=True)

    # Additional Details
    meta_data = Column("metadata", JSON, nullable=True)
    # Additional metadata about the metric

    # Audit
    recorded_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    recorded_by_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )

    # Relationships
    organization = relationship("Organization", back_populates="usage_metrics")
    user = relationship("User", foreign_keys=[user_id])
    recorded_by = relationship("User", foreign_keys=[recorded_by_id])

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "value >= 0",
            name='chk_usage_metric_value'
        ),
        UniqueConstraint(
            'metric_type',
            'organization_id',
            'workspace_id',
            'business_unit_id',
            'team_id',
            'user_id',
            'agent_id',
            'action_id',
            'aggregation_period',
            'aggregation_date',
            name='uix_usage_metric'
        ),
        Index('ix_usage_metric_type', 'metric_type'),
        Index('ix_usage_metric_date', 'aggregation_date'),
        Index('ix_usage_metric_organization', 'organization_id'),
        Index('ix_usage_metric_workspace', 'workspace_id'),
        Index('ix_usage_metric_business_unit', 'business_unit_id'),
        Index('ix_usage_metric_user', 'user_id'),
        Index('ix_usage_metric_agent', 'agent_id'),
    )


class UsageAggregation(Base):
    """Aggregated usage metrics.

    Pre-computed aggregates for performance.
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

    # Aggregation Details
    metric_type = Column(
        SQLEnum(UsageMetricType),
        default=UsageMetricType.AGENT_EXECUTION,
        nullable=False,
        index=True
    )
    aggregation_period = Column(String(20), nullable=False)

    # Aggregation Period
    period_start = Column(DateTime, nullable=False, index=True)
    period_end = Column(DateTime, nullable=False, index=True)

    # Aggregation Dimensions
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
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )

    # Aggregated Values
    total_count = Column(Integer, default=0)
    total_value = Column(Integer, default=0)
    average_value = Column(Float, default=0.0)
    max_value = Column(Integer, default=0)
    min_value = Column(Integer, default=0)

    # Cost Tracking
    estimated_cost = Column(Float, default=0.0)
    actual_cost = Column(Float, default=0.0)

    # Additional Metrics
    other_metrics = Column(JSON, nullable=True)

    # Status
    is_calculated = Column(Boolean, default=False)
    calculation_status = Column(String(50), nullable=True)

    # Audit
    calculated_at = Column(DateTime, nullable=True)
    calculated_by_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )

    # Relationships
    organization = relationship("Organization", back_populates="usage_aggregations")
    user = relationship("User", foreign_keys=[user_id])
    calculated_by = relationship("User", foreign_keys=[calculated_by_id])

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "period_start <= period_end",
            name='chk_usage_period'
        ),
        UniqueConstraint(
            'metric_type',
            'organization_id',
            'workspace_id',
            'business_unit_id',
            'team_id',
            'user_id',
            'aggregation_period',
            'period_start',
            'period_end',
            name='uix_usage_aggregation'
        ),
        Index('ix_usage_aggregation_type', 'metric_type'),
        Index('ix_usage_aggregation_period', 'aggregation_period'),
        Index('ix_usage_aggregation_date', 'period_start'),
        Index('ix_usage_aggregation_organization', 'organization_id'),
        Index('ix_usage_aggregation_workspace', 'workspace_id'),
    )
