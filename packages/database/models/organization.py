from typing import List, Optional
from sqlalchemy import (
    Float,
    Column, String, Text, Integer, Boolean, JSON, DateTime,
    ForeignKey, Index, UniqueConstraint, CheckConstraint
)
from datetime import datetime
from sqlalchemy.orm import relationship
from enum import Enum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from uuid import uuid4

from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from uuid import uuid4

from .base import TenantIDMixin, Base


class Organization(TenantIDMixin, Base):
    """Organization represents a multi-tenant entity.

    This is the top-level container for all tenant data.
    Each organization can contain multiple workspaces, legal entities,
    and business units.
    """

    # Organization Details
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    logo_url = Column(String(500), nullable=True)

    # Contact Information
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    website = Column(String(255), nullable=True)

    # Organization Settings
    industry = Column(String(100), nullable=True)
    size = Column(String(50), nullable=True)  # Small, Medium, Large
    country = Column(String(100), nullable=True)
    region = Column(String(100), nullable=True)
    timezone = Column(String(50), nullable=True)

    # Plan & Billing
    plan = Column(String(50), nullable=False, default='free')
    billing_email = Column(String(255), nullable=True)
    billing_address = Column(JSON, nullable=True)
    settings = Column(JSON, nullable=True)  # Custom organization settings

    # Status
    status = Column(String(20), nullable=False, default='active')
    # Status options: active, suspended, archived, pending

    # Audit
    mfa_enabled = Column(Boolean, default=False)
    two_factor_enabled = Column(Boolean, default=False)
    require_approval_for_agents = Column(Boolean, default=False)
    require_approval_for_actions = Column(Boolean, default=False)

    # Relationships
    workspaces = relationship("Workspace", back_populates="organization", cascade="all, delete-orphan", foreign_keys="Workspace.organization_id")
    business_units = relationship("BusinessUnit", back_populates="organization", cascade="all, delete-orphan", foreign_keys="BusinessUnit.organization_id")
    teams = relationship("Team", back_populates="organization", cascade="all, delete-orphan", foreign_keys="Team.organization_id")
    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    user_roles = relationship("UserRole", back_populates="organization", cascade="all, delete-orphan")
    agents = relationship("Agent", back_populates="organization", cascade="all, delete-orphan")
    integrations = relationship("Integration", back_populates="organization", cascade="all, delete-orphan")
    connectors = relationship("Connector", back_populates="organization", cascade="all, delete-orphan")
    data_sources = relationship("DataSource", back_populates="organization", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="organization", cascade="all, delete-orphan")
    knowledge_bases = relationship("KnowledgeBase", back_populates="organization", cascade="all, delete-orphan")
    workflows = relationship("Workflow", back_populates="organization", cascade="all, delete-orphan")
    actions = relationship("Action", back_populates="organization", cascade="all, delete-orphan")
    audit_events = relationship("AuditEvent", back_populates="organization", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="organization", cascade="all, delete-orphan")
    usage_metrics = relationship("UsageMetric", back_populates="organization", cascade="all, delete-orphan")
    usage_aggregations = relationship("UsageAggregation", back_populates="organization", cascade="all, delete-orphan")
    tenant_settings = relationship("TenantSetting", back_populates="organization", cascade="all, delete-orphan")
    tools = relationship("Tool", back_populates="organization", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        UniqueConstraint('tenant_id', 'slug', name='uix_organization_tenant_slug'),
        CheckConstraint(
            "status IN ('active', 'suspended', 'archived', 'pending')",
            name='chk_organization_status'
        ),
        CheckConstraint(
            "plan IN ('free', 'basic', 'pro', 'enterprise', 'custom')",
            name='chk_organization_plan'
        ),
        Index('ix_organization_name', 'name'),
        Index('ix_organization_slug', 'slug'),
        Index('ix_organization_status', 'status'),
    )


class Workspace(TenantIDMixin, Base):
    """Workspace represents a logical division within an organization.

    Workspaces allow organizations to organize their business operations
    into different areas, such as departments, projects, or business units.
    Each workspace has its own permissions, users, and configurations.
    """

    organization_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('organizations.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Workspace Details
    name = Column(String(255), nullable=False)
    slug = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String(100), nullable=True)  # Emoji or icon name

    # Parent Workspace (for nested structures)
    parent_workspace_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('workspaces.id', ondelete='CASCADE'),
        nullable=True,
        index=True
    )
    parent_workspace = relationship("Workspace", remote_side="Workspace.id", backref="child_workspaces")

    # Business Unit Association
    business_unit_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('business_units.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    business_unit = relationship("BusinessUnit", back_populates="workspaces")

    # Access
    is_default = Column(Boolean, default=False)
    is_public = Column(Boolean, default=False)
    requires_access = Column(Boolean, default=True)

    # Settings
    settings = Column(JSON, nullable=True)
    permissions = Column(JSON, nullable=True)  # Custom permissions

    # Status
    status = Column(String(20), nullable=False, default='active')
    # Status options: active, archived

    # Relationships
    organization = relationship("Organization", back_populates="workspaces", foreign_keys=[organization_id])
    users = relationship("User", secondary="user_workspace_roles", back_populates="workspaces")
    agents = relationship("Agent", back_populates="workspace")
    data_sources = relationship("DataSource", back_populates="workspace")
    documents = relationship("Document", back_populates="workspace")
    workflows = relationship("Workflow", back_populates="workspace")
    integrations = relationship("Integration", back_populates="workspace")
    connectors = relationship("Connector", back_populates="workspace")
    knowledge_bases = relationship("KnowledgeBase", back_populates="workspace")

    # Constraints
    __table_args__ = (
        UniqueConstraint('tenant_id', 'slug', name='uix_workspace_tenant_slug'),
        CheckConstraint(
            "status IN ('active', 'archived')",
            name='chk_workspace_status'
        ),
        Index('ix_workspace_name', 'name'),
        Index('ix_workspace_slug', 'slug'),
        Index('ix_workspace_organization', 'organization_id'),
        Index('ix_workspace_business_unit', 'business_unit_id'),
    )


class BusinessUnit(TenantIDMixin, Base):
    """Business Unit represents a legal entity or operating division.

    Allows organizations to maintain multiple legal entities
    within a single tenant. Each business unit can have its own
    financials, reporting, and operational structure.
    """

    organization_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('organizations.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Business Unit Details
    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)

    # Legal Entity Information
    tax_id = Column(String(100), nullable=True, unique=True, index=True)
    country = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    address = Column(JSON, nullable=True)  # Street, city, state, zip, country

    # Financial Information
    currency = Column(String(3), nullable=False, default='USD')
    financials_enabled = Column(Boolean, default=True)

    # Contact
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    finance_email = Column(String(255), nullable=True)

    # Parent Business Unit
    parent_business_unit_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('business_units.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    parent_business_unit = relationship(
        "BusinessUnit",
        remote_side="BusinessUnit.id",
        backref="child_business_units"
    )

    # Relationships
    organization = relationship("Organization", back_populates="business_units", foreign_keys=[organization_id])
    workspaces = relationship("Workspace", back_populates="business_unit")
    teams = relationship("Team", back_populates="business_unit")
    agents = relationship("Agent", back_populates="business_unit")
    documents = relationship("Document", back_populates="business_unit")
    workflows = relationship("Workflow", back_populates="business_unit")
    data_sources = relationship("DataSource", back_populates="business_unit")
    integrations = relationship("Integration", back_populates="business_unit")
    connectors = relationship("Connector", back_populates="business_unit")
    knowledge_bases = relationship("KnowledgeBase", back_populates="business_unit")

    # Constraints
    __table_args__ = (
        UniqueConstraint('tenant_id', 'code', name='uix_business_unit_tenant_code'),
        CheckConstraint(
            "currency IN ('USD', 'EUR', 'GBP', 'CAD', 'AUD', 'INR', 'JPY', 'CNY', 'AED')",
            name='chk_business_unit_currency'
        ),
        Index('ix_business_unit_name', 'name'),
        Index('ix_business_unit_code', 'code'),
        Index('ix_business_unit_organization', 'organization_id'),
    )


class Team(TenantIDMixin, Base):
    """Team represents a group of users working together.

    Teams can be used for project teams, departments, or functional groups.
    They provide organizational structure and access control.
    """

    organization_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('organizations.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    business_unit_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('business_units.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    business_unit = relationship("BusinessUnit", back_populates="teams")

    # Team Details
    name = Column(String(255), nullable=False)
    slug = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    avatar_url = Column(String(500), nullable=True)

    # Team Type
    team_type = Column(String(50), nullable=True)
    # Types: department, project, functional, special

    # Parent Team (for nested structures)
    parent_team_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('teams.id', ondelete='CASCADE'),
        nullable=True,
        index=True
    )
    parent_team = relationship("Team", remote_side="Team.id", backref="child_teams")

    # Access Control
    is_default = Column(Boolean, default=False)
    max_members = Column(Integer, nullable=True)

    # Settings
    settings = Column(JSON, nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="teams", foreign_keys=[organization_id])
    users = relationship("User", secondary="user_team_roles", back_populates="teams")
    agents = relationship("Agent", back_populates="team")
    workflows = relationship("Workflow", back_populates="team")

    # Constraints
    __table_args__ = (
        UniqueConstraint('tenant_id', 'slug', name='uix_team_tenant_slug'),
        Index('ix_team_name', 'name'),
        Index('ix_team_slug', 'slug'),
        Index('ix_team_organization', 'organization_id'),
        Index('ix_team_business_unit', 'business_unit_id'),
    )


# Workspace-User relationship table
class UserWorkspaceRole(Base):
    """Many-to-many relationship between users and workspaces with roles."""
    __tablename__ = 'user_workspace_roles'

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    workspace_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('workspaces.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    role_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('user_roles.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="workspace_roles", overlaps="users,workspaces")
    workspace = relationship("Workspace", overlaps="users,workspaces")
    role = relationship("UserRole")

    # Constraints
    __table_args__ = (
        UniqueConstraint('user_id', 'workspace_id', name='uix_user_workspace_role'),
        Index('ix_user_workspace_role_workspace', 'workspace_id'),
        Index('ix_user_workspace_role_user', 'user_id'),
    )


# Team-User relationship table
class UserTeamRole(Base):
    """Many-to-many relationship between users and teams with roles."""
    __tablename__ = 'user_team_roles'

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    team_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('teams.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    role_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('user_roles.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="team_roles", overlaps="users,teams")
    team = relationship("Team", overlaps="users,teams")
    role = relationship("UserRole")

    # Constraints
    __table_args__ = (
        UniqueConstraint('user_id', 'team_id', name='uix_user_team_role'),
        Index('ix_user_team_role_team', 'team_id'),
        Index('ix_user_team_role_user', 'user_id'),
    )
