import re
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, String, Text, Boolean, JSON, ForeignKey, Index, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import DeclarativeBase, declared_attr

# Register compiler for PostgreSQL UUID on SQLite dialect
@compiles(PG_UUID, 'sqlite')
def compile_pg_uuid_sqlite(type_, compiler, **kw):
    return "CHAR(36)"


def EnumCol(enum_cls, **kwargs):
    """Dialect-safe Enum column type using string values."""
    return SQLEnum(enum_cls, values_callable=lambda x: [e.value for e in x], **kwargs)


class TimestampMixin:
    """Mixin to add created_at and updated_at timestamps."""
    __allow_unmapped__ = True

    @declared_attr
    def created_at(cls):
        return Column(DateTime, default=datetime.utcnow, nullable=False)

    @declared_attr
    def updated_at(cls):
        return Column(
            DateTime,
            default=datetime.utcnow,
            onupdate=datetime.utcnow,
            nullable=False
        )


class UUIDMixin:
    """Mixin to add UUID primary key."""
    __allow_unmapped__ = True

    @declared_attr
    def id(cls):
        return Column(
            PG_UUID(as_uuid=True),
            primary_key=True,
            default=uuid4,
            nullable=False
        )


class TenantScopedMixin:
    """Mixin to add tenant-scoped properties."""
    __allow_unmapped__ = True

    @declared_attr
    def tenant_id(cls):
        if cls.__name__ == 'Organization':
            return Column(
                PG_UUID(as_uuid=True),
                nullable=True,
                index=True
            )
        return Column(
            PG_UUID(as_uuid=True),
            ForeignKey('organizations.id', ondelete='CASCADE'),
            nullable=False,
            index=True
        )


class SoftDeleteMixin:
    """Mixin for soft delete functionality."""
    __allow_unmapped__ = True

    @declared_attr
    def is_deleted(cls):
        return Column(Boolean, default=False, nullable=False)

    @declared_attr
    def deleted_at(cls):
        return Column(DateTime, nullable=True)


class TenantIDMixin(TenantScopedMixin, UUIDMixin, TimestampMixin):
    """Mixin combining tenant scoping with UUID and timestamps."""
    __allow_unmapped__ = True
    pass


class Base(DeclarativeBase, UUIDMixin, TimestampMixin):
    """Base model class for all database models."""
    __abstract__ = True
    __allow_unmapped__ = True

    @declared_attr
    def __tablename__(cls) -> str:
        """Generate table name from class name."""
        s = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', cls.__name__)
        s = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s).lower()
        if s.endswith('s'):
            return s + 'es'
        return s + 's'

    def to_dict(self, exclude: Optional[list] = None) -> Dict[str, Any]:
        """Convert model instance to dictionary."""
        if exclude is None:
            exclude = []

        data = {}
        for column in self.__table__.columns:
            if column.name not in exclude:
                value = getattr(self, column.name)
                # Convert UUID to string
                if isinstance(value, UUID):
                    value = str(value)
                data[column.name] = value
        return data


# Create indexes for common query patterns
class IndexMixin:
    """Mixin to create database indexes."""
    __allow_unmapped__ = True

    @classmethod
    def __table_args__(cls):
        """Define table-specific indexes."""
        indexes = []
        for attr_name, index_config in cls.__dict__.items():
            if attr_name.startswith('ix_'):
                indexes.append(index_config)
        return tuple(indexes) or None
