"""
Connectors schemas.

Pydantic schemas for connectors API endpoints.
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict


class ConnectorBase(BaseModel):
    """Base connector schema."""
    name: str = Field(..., min_length=1, max_length=100, description="Connector name")
    description: Optional[str] = Field(None, max_length=500, description="Connector description")
    service_type: str = Field(..., min_length=1, max_length=50, description="Service type")
    category: Optional[str] = Field(None, min_length=1, max_length=50, description="Connector category")
    version: str = Field("1.0.0", min_length=1, max_length=20, description="Connector version")
    config_schema: Optional[Dict[str, Any]] = Field(None, description="Connector configuration schema")
    auth_config: Optional[Dict[str, Any]] = Field(None, description="Authentication configuration")
    base_url: Optional[str] = Field(None, max_length=255, description="Base URL for external service")
    is_enabled: bool = Field(True, description="Whether connector is enabled")
    is_public: bool = Field(False, description="Whether connector is public")
    author: Optional[str] = Field(None, max_length=100, description="Connector author")
    tags: Optional[List[str]] = Field(None, description="Connector tags")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate connector name."""
        if not v.strip():
            raise ValueError("Connector name cannot be empty")
        return v.strip()

    @field_validator('service_type')
    @classmethod
    def validate_service_type(cls, v):
        """Validate service type."""
        valid_types = ["email", "storage", "api", "database", "messaging", "social", "analytics", "crm", "erp"]
        if v not in valid_types:
            raise ValueError(f"Invalid service type. Must be one of: {valid_types}")
        return v


class ConnectorCreate(ConnectorBase):
    """Schema for creating a new connector."""
    pass


class ConnectorUpdate(BaseModel):
    """Schema for updating a connector."""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Connector name")
    description: Optional[str] = Field(None, max_length=500, description="Connector description")
    service_type: Optional[str] = Field(None, min_length=1, max_length=50, description="Service type")
    category: Optional[str] = Field(None, min_length=1, max_length=50, description="Connector category")
    version: Optional[str] = Field(None, min_length=1, max_length=20, description="Connector version")
    config_schema: Optional[Dict[str, Any]] = Field(None, description="Connector configuration schema")
    auth_config: Optional[Dict[str, Any]] = Field(None, description="Authentication configuration")
    base_url: Optional[str] = Field(None, max_length=255, description="Base URL for external service")
    is_enabled: Optional[bool] = Field(None, description="Whether connector is enabled")
    is_public: Optional[bool] = Field(None, description="Whether connector is public")
    author: Optional[str] = Field(None, max_length=100, description="Connector author")
    tags: Optional[List[str]] = Field(None, description="Connector tags")


class ConnectorResponse(ConnectorBase):
    """Schema for connector response."""
    id: UUID
    created_at: datetime
    updated_at: datetime
    usage_count: int
    last_used_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class ConnectionCreate(BaseModel):
    """Schema for creating a new connection."""
    connector_id: UUID = Field(..., description="Connector ID")
    name: str = Field(..., min_length=1, max_length=100, description="Connection name")
    description: Optional[str] = Field(None, max_length=500, description="Connection description")
    config: Optional[Dict[str, Any]] = Field(None, description="Connection-specific configuration")


class ConnectionUpdate(BaseModel):
    """Schema for updating a connection."""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Connection name")
    description: Optional[str] = Field(None, max_length=500, description="Connection description")
    config: Optional[Dict[str, Any]] = Field(None, description="Connection-specific configuration")
    status: Optional[str] = Field(None, description="Connection status")


class ConnectionResponse(BaseModel):
    """Schema for connection response."""
    id: UUID
    connector_id: UUID
    user_id: UUID
    name: str
    description: Optional[str]
    config: Optional[Dict[str, Any]]
    status: str
    created_at: datetime
    updated_at: datetime
    last_connected_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class ConnectionStatus(str, Enum):
    """Connection status enum."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    REVOKED = "revoked"


class ConnectorTestRequest(BaseModel):
    """Schema for connector test request."""
    config: Dict[str, Any] = Field(..., description="Test configuration")


class ConnectorTestResponse(BaseModel):
    """Schema for connector test response."""
    connector_id: UUID
    is_successful: bool
    message: str
    response_time: Optional[float]
    timestamp: datetime


class ConnectorStats(BaseModel):
    """Connector statistics."""
    total_connectors: int
    total_connections: int
    active_connections: int
    type_distribution: Dict[str, int]
    category_distribution: Dict[str, int]


class ConnectorValidationResponse(BaseModel):
    """Connector validation response."""
    connector_id: UUID
    is_valid: bool
    errors: List[str] = Field(default_factory=list)