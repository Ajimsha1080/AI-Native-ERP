from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy import (
    Float,
    Column, String, Text, Integer, Boolean, DateTime, ForeignKey,
    Index, UniqueConstraint, CheckConstraint, Enum as SQLEnum, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from uuid import uuid4

from .base import TenantIDMixin, Base, EnumCol

try:
    from enum import Enum
except ImportError:
    from enum import IntEnum


class UserRoleType(str, Enum):
    """User role types."""
    SUPER_ADMIN = "super_admin"
    ORGANIZATION_ADMIN = "organization_admin"
    SECURITY_ADMIN = "security_admin"
    FINANCE_ADMIN = "finance_admin"
    OPERATIONS_ADMIN = "operations_admin"
    AGENT_ADMIN = "agent_admin"
    MANAGER = "manager"
    EMPLOYEE = "employee"
    ANALYST = "analyst"
    VIEWER = "viewer"


class UserStatus(str, Enum):
    """User account status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"
    ARCHIVED = "archived"


class AuthenticationProvider(str, Enum):
    """Authentication providers."""
    EMAIL = "email"
    GOOGLE = "google"
    MICROSOFT = "microsoft"
    SAML = "saml"
    OIDC = "oidc"
    SCIM = "scim"


class User(TenantIDMixin, Base):
    """User represents a human user in the system.

    Each user can be part of multiple workspaces and teams with
    different roles. Users can authenticate via multiple providers.
    """

    # Authentication
    email = Column(String(255), nullable=False, index=True)
    password_hash = Column(String(500), nullable=True)
    is_verified = Column(Boolean, default=False)
    email_verified_at = Column(DateTime, nullable=True)

    # User Profile
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    full_name = Column(String(255), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    title = Column(String(255), nullable=True)
    department = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    location = Column(String(255), nullable=True)

    # Authentication Provider
    provider = Column(
        EnumCol(AuthenticationProvider),
        default=AuthenticationProvider.EMAIL,
        nullable=False
    )
    provider_id = Column(String(255), nullable=True)
    provider_profile_data = Column(JSON, nullable=True)  # OAuth profile data

    # Status
    status = Column(
        EnumCol(UserStatus),
        default=UserStatus.PENDING,
        nullable=False,
        index=True
    )
    is_active = Column(Boolean, default=True)
    is_locked = Column(Boolean, default=False)
    login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)

    # Two-Factor Authentication
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String(255), nullable=True)
    mfa_method = Column(String(50), nullable=True)  # TOTP, SMS, EMAIL

    # Session Management
    last_login_at = Column(DateTime, nullable=True)
    last_login_ip = Column(String(45), nullable=True)
    current_session_id = Column(String(255), nullable=True)

    # Preferences
    preferences = Column(JSON, nullable=True)  # Language, theme, etc.
    notifications_enabled = Column(Boolean, default=True)
    email_notifications_enabled = Column(Boolean, default=True)
    dashboard_widgets = Column(JSON, nullable=True)

    # Audit
    created_by_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )
    created_by = relationship("User", remote_side="User.id")

    # Relationships
    organization = relationship("Organization", back_populates="users")
    workspaces = relationship("Workspace", secondary="user_workspace_roles", back_populates="users", overlaps="workspace_roles,user,workspace")
    teams = relationship("Team", secondary="user_team_roles", back_populates="users", overlaps="team_roles,user,team")
    approvals = relationship("Approval", foreign_keys="Approval.approver_id", back_populates="approver")
    workspace_roles = relationship(
        "UserWorkspaceRole",
        back_populates="user",
        cascade="all, delete-orphan",
        overlaps="workspaces,users"
    )
    team_roles = relationship(
        "UserTeamRole",
        back_populates="user",
        cascade="all, delete-orphan",
        overlaps="teams,users"
    )
    assigned_roles = relationship("UserRoleAssignment", foreign_keys="UserRoleAssignment.user_id", back_populates="user")
    agents = relationship("Agent", foreign_keys="Agent.owner_id", back_populates="owner")
    documents = relationship("Document", foreign_keys="Document.owner_id", back_populates="owner")
    audit_logs = relationship("AuditEvent", back_populates="user")
    agent_executions = relationship("AgentExecution", back_populates="user", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        UniqueConstraint('tenant_id', 'email', name='uix_user_tenant_email'),
        CheckConstraint(
            "status IN ('active', 'inactive', 'suspended', 'pending', 'archived')",
            name='chk_user_status'
        ),
        CheckConstraint(
            "mfa_method IN ('totp', 'sms', 'email', 'none')",
            name='chk_user_mfa_method'
        ),
        Index('ix_user_email', 'email'),
        Index('ix_user_status', 'status'),
        Index('ix_user_organization', 'tenant_id'),
    )

    def is_active_user(self) -> bool:
        """Check if user is active and not locked."""
        return self.is_active and not self.is_locked

    def is_authenticated(self) -> bool:
        """Check if user has been authenticated."""
        return self.is_active and self.status == UserStatus.ACTIVE

    def can_access_workspace(self, workspace_id: str) -> bool:
        """Check if user has access to workspace."""
        return any(wr.workspace_id == workspace_id for wr in self.workspace_roles)

    def get_workspace_roles(self, workspace_id: str) -> List[str]:
        """Get all roles for a specific workspace."""
        roles = []
        for wr in self.workspace_roles:
            if wr.workspace_id == workspace_id and wr.role:
                roles.append(wr.role.name)
        return roles

    def can_manage_agents(self, workspace_id: str) -> bool:
        """Check if user can manage agents in workspace."""
        return any(
            wr.role and wr.role.can_manage_agents
            for wr in self.workspace_roles
            if wr.workspace_id == workspace_id
        )


class UserRole(Base):
    """Role definitions in the organization.

    Roles define permission groups that can be assigned to users
    at different scope levels (organization, workspace, team).
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

    # Role Details
    name = Column(String(100), nullable=False)
    slug = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    display_name = Column(String(255), nullable=True)

    # Role Type
    role_type = Column(
        EnumCol(UserRoleType),
        default=UserRoleType.EMPLOYEE,
        nullable=False,
        index=True
    )

    # Permissions
    can_view_dashboard = Column(Boolean, default=False)
    can_access_settings = Column(Boolean, default=False)
    can_manage_users = Column(Boolean, default=False)
    can_manage_roles = Column(Boolean, default=False)
    can_manage_agents = Column(Boolean, default=False)
    can_execute_actions = Column(Boolean, default=False)
    can_approve_actions = Column(Boolean, default=False)
    can_access_financial_data = Column(Boolean, default=False)
    can_approve_financial_actions = Column(Boolean, default=False)
    can_access_inventory_data = Column(Boolean, default=False)
    can_manage_inventory = Column(Boolean, default=False)
    can_access_procurement = Column(Boolean, default=False)
    can_manage_procurement = Column(Boolean, default=False)
    can_access_sales_data = Column(Boolean, default=False)
    can_manage_sales = Column(Boolean, default=False)
    can_access_operations = Column(Boolean, default=False)
    can_manage_operations = Column(Boolean, default=False)

    # Custom Permissions
    custom_permissions = Column(JSON, nullable=True)

    # Scope
    scope = Column(String(50), nullable=False, default='organization')
    # Scope: organization, workspace, team, global

    # Settings
    requires_approval = Column(Boolean, default=False)
    approval_threshold = Column(Integer, nullable=True)
    spending_limit = Column(Integer, nullable=True)
    rate_limit = Column(Integer, nullable=True)  # Requests per minute

    # Status
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)

    # Relationships
    organization = relationship("Organization", back_populates="user_roles")
    assignments = relationship("UserRoleAssignment", back_populates="role")
    workspace_roles = relationship("UserWorkspaceRole", back_populates="role")
    team_roles = relationship("UserTeamRole", back_populates="role")

    # Constraints
    __table_args__ = (
        UniqueConstraint('organization_id', 'slug', name='uix_user_role_organization_slug'),
        CheckConstraint(
            "scope IN ('organization', 'workspace', 'team', 'global')",
            name='chk_user_role_scope'
        ),
        Index('ix_user_role_name', 'name'),
        Index('ix_user_role_slug', 'slug'),
        Index('ix_user_role_organization', 'organization_id'),
        Index('ix_user_role_type', 'role_type'),
    )

    def can_perform_action(self, action_type: str) -> bool:
        """Check if role can perform a specific action."""
        # Global actions
        if action_type in ["view_dashboard", "access_settings", "manage_users"]:
            return self.can_view_dashboard or self.can_access_settings or self.can_manage_users

        # Agent actions
        if action_type in ["manage_agents", "execute_agent_actions", "approve_agent_actions"]:
            return self.can_manage_agents or self.can_execute_actions or self.can_approve_actions

        # Financial actions
        if action_type in ["access_financial", "manage_financial", "approve_financial"]:
            return self.can_access_financial_data or self.can_approve_financial_actions

        # Inventory actions
        if action_type in ["access_inventory", "manage_inventory"]:
            return self.can_access_inventory_data or self.can_manage_inventory

        # Procurement actions
        if action_type in ["access_procurement", "manage_procurement"]:
            return self.can_access_procurement or self.can_manage_procurement

        # Sales actions
        if action_type in ["access_sales", "manage_sales"]:
            return self.can_access_sales_data or self.can_manage_sales

        # Operations actions
        if action_type in ["access_operations", "manage_operations"]:
            return self.can_access_operations or self.can_manage_operations

        return True  # Default allow


class UserRoleAssignment(Base):
    """Assignment of a role to a user at specific scope levels."""

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )

    # User
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    user = relationship("User", foreign_keys=[user_id], back_populates="assigned_roles")

    # Role
    role_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('user_roles.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    role = relationship("UserRole", back_populates="assignments")

    # Scope (organization, workspace, team)
    scope = Column(String(50), nullable=False, index=True)
    # Scope: organization, workspace, team

    # Scope Identifier
    scope_id = Column(PG_UUID(as_uuid=True), nullable=True, index=True)

    # Assigned By
    assigned_by_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )
    assigned_by = relationship("User", foreign_keys=[assigned_by_id])

    # Date
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Expiration
    expires_at = Column(DateTime, nullable=True)

    # Constraints
    __table_args__ = (
        UniqueConstraint('user_id', 'role_id', 'scope', 'scope_id', name='uix_user_role_assignment'),
        CheckConstraint(
            "scope IN ('organization', 'workspace', 'team')",
            name='chk_user_role_assignment_scope'
        ),
        Index('ix_user_role_assignment_user', 'user_id'),
        Index('ix_user_role_assignment_role', 'role_id'),
        Index('ix_user_role_assignment_scope', 'scope'),
        Index('ix_user_role_assignment_scope_id', 'scope_id'),
    )

    def is_active(self) -> bool:
        """Check if assignment is active."""
        if self.expires_at is None:
            return True
        return datetime.utcnow() < self.expires_at
