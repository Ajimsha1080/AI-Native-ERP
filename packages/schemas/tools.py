"""
Tools schemas.

Pydantic schemas for tools API endpoints.
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict



class ToolBase(BaseModel):
    """Base tool schema."""
    name: str = Field(..., min_length=1, max_length=100, description="Tool name")
    description: Optional[str] = Field(None, max_length=500, description="Tool description")
    type: str = Field(..., min_length=1, max_length=50, description="Tool type")
    category: Optional[str] = Field(None, min_length=1, max_length=50, description="Tool category")
    version: str = Field("1.0.0", min_length=1, max_length=20, description="Tool version")
    config_schema: Optional[Dict[str, Any]] = Field(None, description="Tool configuration schema")
    input_schema: Optional[Dict[str, Any]] = Field(None, description="Tool input schema")
    output_schema: Optional[Dict[str, Any]] = Field(None, description="Tool output schema")
    is_enabled: bool = Field(True, description="Whether tool is enabled")
    is_public: bool = Field(False, description="Whether tool is public")
    author: Optional[str] = Field(None, max_length=100, description="Tool author")
    tags: Optional[List[str]] = Field(None, description="Tool tags")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate tool name."""
        if not v.strip():
            raise ValueError("Tool name cannot be empty")
        return v.strip()

    @field_validator('type')
    @classmethod
    def validate_type(cls, v):
        """Validate tool type."""
        valid_types = ["api", "database", "file", "ai", "calculation", "communication", "integration"]
        if v not in valid_types:
            raise ValueError(f"Invalid tool type. Must be one of: {valid_types}")
        return v


class ToolCreate(ToolBase):
    """Schema for creating a new tool."""
    pass


class ToolUpdate(BaseModel):
    """Schema for updating a tool."""
    description: Optional[str] = Field(None, max_length=500, description="Tool description")
    type: Optional[str] = Field(None, min_length=1, max_length=50, description="Tool type")
    category: Optional[str] = Field(None, min_length=1, max_length=50, description="Tool category")
    version: Optional[str] = Field(None, min_length=1, max_length=20, description="Tool version")
    config_schema: Optional[Dict[str, Any]] = Field(None, description="Tool configuration schema")
    input_schema: Optional[Dict[str, Any]] = Field(None, description="Tool input schema")
    output_schema: Optional[Dict[str, Any]] = Field(None, description="Tool output schema")
    is_enabled: Optional[bool] = Field(None, description="Whether tool is enabled")
    is_public: Optional[bool] = Field(None, description="Whether tool is public")
    author: Optional[str] = Field(None, max_length=100, description="Tool author")
    tags: Optional[List[str]] = Field(None, description="Tool tags")


class ToolResponse(ToolBase):
    """Schema for tool response."""
    id: UUID
    created_at: datetime
    updated_at: datetime
    usage_count: int
    last_used_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class ToolResponseWithConfig(ToolResponse):
    """Schema for tool response with full configuration."""
    pass


class ToolExecutionRequest(BaseModel):
    """Schema for tool execution request."""
    inputs: Dict[str, Any] = Field(..., description="Input data for tool execution")
    config: Optional[Dict[str, Any]] = Field(None, description="Optional configuration override")
    timeout: Optional[int] = Field(None, ge=1, le=300, description="Execution timeout in seconds")


class ToolExecutionResponse(BaseModel):
    """Schema for tool execution response."""
    tool_id: UUID
    tool_name: str
    status: str = Field(..., description="Execution status")
    output: Any = Field(..., description="Execution output")
    execution_time: float = Field(..., description="Execution time in seconds")
    timestamp: datetime = Field(..., description="Execution timestamp")


class ToolType(str, Enum):
    """Tool type enum."""
    API = "api"
    DATABASE = "database"
    FILE = "file"
    AI = "ai"
    CALCULATION = "calculation"
    COMMUNICATION = "communication"
    INTEGRATION = "integration"


class ToolStats(BaseModel):
    """Tool statistics."""
    total_count: int
    type_distribution: Dict[str, int]
    category_distribution: Dict[str, int]


class ToolValidationResponse(BaseModel):
    """Tool validation response."""
    tool_id: UUID
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
