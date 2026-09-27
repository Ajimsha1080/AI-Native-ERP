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


class SettingType(str, Enum):
    """Setting types."""
    SYSTEM = "system"
    TENANT = "tenant"
    WORKSPACE = "workspace"
    ORGANIZATION = "organization"


class SettingScope(str, Enum):
    """Setting scopes."""
    GLOBAL = "global"
    ORGANIZATION = "organization"
    WORKSPACE = "workspace"


class SystemSetting(Base):
    """System-wide settings.

    Centralized configuration for the entire platform.
    """

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )

    # Setting Details
    key = Column(String(255), nullable=False)
    value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)

    # Type
    setting_type = Column(
        EnumCol(SettingType),
        default=SettingType.SYSTEM,
        nullable=False,
        index=True
    )

    # Scope
    scope = Column(
        EnumCol(SettingScope),
        default=SettingScope.GLOBAL,
        nullable=False,
        index=True
    )

    # Validation
    value_type = Column(String(50), nullable=True)  # string, integer, boolean, json, enum
    validation_regex = Column(String(500), nullable=True)
    min_value = Column(Integer, nullable=True)
    max_value = Column(Integer, nullable=True)

    # Access Control
    is_public = Column(Boolean, default=False)
    is_encrypted = Column(Boolean, default=False)

    # Default Value
    default_value = Column(Text, nullable=True)

    # Visibility
    is_visible_in_ui = Column(Boolean, default=False)
    is_editable_by_admins = Column(Boolean, default=True)
    is_editable_by_users = Column(Boolean, default=False)

    # Dependencies
    depends_on = Column(String(255), nullable=True)  # Other setting keys

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )

    # Relationships
    created_by = relationship("User")

    # Constraints
    __table_args__ = (
        UniqueConstraint('key', name='uix_system_setting_key'),
        CheckConstraint(
            "scope IN ('global', 'organization', 'workspace')",
            name='chk_system_setting_scope'
        ),
        Index('ix_system_setting_type', 'setting_type'),
        Index('ix_system_setting_scope', 'scope'),
    )


class TenantSetting(Base):
    """Organization-specific settings.

    Allows organizations to customize platform behavior.
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

    # Setting Details
    key = Column(String(255), nullable=False)
    value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)

    # Type
    setting_type = Column(
        EnumCol(SettingType),
        default=SettingType.TENANT,
        nullable=False,
        index=True
    )

    # Scope
    scope = Column(
        EnumCol(SettingScope),
        default=SettingScope.ORGANIZATION,
        nullable=False,
        index=True
    )

    # Validation
    value_type = Column(String(50), nullable=True)
    validation_regex = Column(String(500), nullable=True)

    # Default Value
    default_value = Column(Text, nullable=True)

    # Visibility
    is_public = Column(Boolean, default=False)
    is_encrypted = Column(Boolean, default=False)
    is_editable_by_org_admin = Column(Boolean, default=True)
    is_editable_by_tenant_admin = Column(Boolean, default=False)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True
    )

    # Relationships
    organization = relationship("Organization", back_populates="tenant_settings")
    created_by = relationship("User")

    # Constraints
    __table_args__ = (
        UniqueConstraint('organization_id', 'key', name='uix_tenant_setting_organization_key'),
        Index('ix_tenant_setting_organization', 'organization_id'),
        Index('ix_tenant_setting_type', 'setting_type'),
        Index('ix_tenant_setting_scope', 'scope'),
    )
