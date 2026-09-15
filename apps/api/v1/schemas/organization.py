"""Organization schemas."""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    description: Optional[str] = None
    logo_url: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    size: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    timezone: Optional[str] = None
    plan: str = 'free'
    status: str = 'active'
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    name: str
    slug: str
    description: Optional[str] = None
    icon: Optional[str] = None
    is_default: bool = False
    is_public: bool = False
    status: str = 'active'
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BusinessUnitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    name: str
    code: str
    description: Optional[str] = None
    currency: str = 'USD'
    country: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TeamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    business_unit_id: Optional[UUID] = None
    name: str
    slug: str
    description: Optional[str] = None
    team_type: Optional[str] = None
    avatar_url: Optional[str] = None
    is_default: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
