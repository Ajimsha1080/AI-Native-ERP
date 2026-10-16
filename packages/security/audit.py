"""Audit logging service for tracking administrative and security actions."""

from typing import Optional, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.models.audit import AuditEvent, AuditEventType
from packages.database.models.base import utc_now


async def log_audit_event(
    db: AsyncSession,
    organization_id: UUID,
    user_id: Optional[UUID],
    event_type: AuditEventType,
    event_name: str,
    description: Optional[str] = None,
    user_email: Optional[str] = None,
    user_role: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    action_data: Optional[Dict[str, Any]] = None,
    result: str = "success",
    request_id: Optional[str] = None,
) -> AuditEvent:
    """Record an immutable audit event to the database for administrative actions."""
    event = AuditEvent(
        organization_id=organization_id,
        user_id=user_id,
        event_type=event_type,
        event_name=event_name,
        description=description,
        user_email=user_email,
        user_role=user_role,
        resource_type=resource_type,
        resource_id=resource_id,
        action_data=action_data or {},
        result=result,
        request_id=request_id,
        event_time=utc_now(),
    )
    db.add(event)
    await db.flush()
    return event
