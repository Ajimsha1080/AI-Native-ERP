"""
Workflows schemas.

Pydantic schemas for workflows API endpoints.
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict

from packages.database.models import WorkflowStatus


class WorkflowExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class WorkflowBase(BaseModel):
    """Base workflow schema."""
    name: str = Field(..., min_length=1, max_length=100, description="Workflow name")
    description: Optional[str] = Field(None, max_length=500, description="Workflow description")
    category: Optional[str] = Field(None, min_length=1, max_length=50, description="Workflow category")
    version: str = Field("1.0.0", min_length=1, max_length=20, description="Workflow version")
    config_schema: Optional[Dict[str, Any]] = Field(None, description="Workflow configuration schema")
    input_schema: Optional[Dict[str, Any]] = Field(None, description="Workflow input schema")
    output_schema: Optional[Dict[str, Any]] = Field(None, description="Workflow output schema")
    triggers: Optional[List[Dict[str, Any]]] = Field(None, description="Workflow triggers")
    schedule: Optional[Dict[str, Any]] = Field(None, description="Schedule configuration")
    is_enabled: bool = Field(True, description="Whether workflow is enabled")
    is_public: bool = Field(False, description="Whether workflow is public")
    author: Optional[str] = Field(None, max_length=100, description="Workflow author")
    tags: Optional[List[str]] = Field(None, description="Workflow tags")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate workflow name."""
        if not v.strip():
            raise ValueError("Workflow name cannot be empty")
        return v.strip()


class WorkflowCreate(WorkflowBase):
    """Schema for creating a new workflow."""
    agent_id: Optional[UUID] = None


class WorkflowUpdate(BaseModel):
    """Schema for updating a workflow."""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Workflow name")
    description: Optional[str] = Field(None, max_length=500, description="Workflow description")
    agent_id: Optional[UUID] = Field(None, description="Agent ID")
    category: Optional[str] = Field(None, min_length=1, max_length=50, description="Workflow category")
    version: Optional[str] = Field(None, min_length=1, max_length=20, description="Workflow version")
    config_schema: Optional[Dict[str, Any]] = Field(None, description="Workflow configuration schema")
    input_schema: Optional[Dict[str, Any]] = Field(None, description="Workflow input schema")
    output_schema: Optional[Dict[str, Any]] = Field(None, description="Workflow output schema")
    triggers: Optional[List[Dict[str, Any]]] = Field(None, description="Workflow triggers")
    schedule: Optional[Dict[str, Any]] = Field(None, description="Schedule configuration")
    is_enabled: Optional[bool] = Field(None, description="Whether workflow is enabled")
    is_public: Optional[bool] = Field(None, description="Whether workflow is public")
    author: Optional[str] = Field(None, max_length=100, description="Workflow author")
    tags: Optional[List[str]] = Field(None, description="Workflow tags")


class WorkflowResponse(WorkflowBase):
    """Schema for workflow response."""
    id: UUID
    status: Optional[WorkflowStatus] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    usage_count: int = 0
    last_used_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class WorkflowExecutionRequest(BaseModel):
    """Schema for workflow execution request."""
    input_data: Optional[Dict[str, Any]] = Field(None, description="Input data for workflow execution")
    config: Optional[Dict[str, Any]] = Field(None, description="Optional configuration override")
    trigger_type: Optional[str] = Field(None, description="Execution trigger type")


class WorkflowExecutionResponse(BaseModel):
    """Schema for workflow execution response."""
    id: UUID
    workflow_id: UUID
    user_id: UUID
    agent_id: Optional[UUID]
    trigger_type: Optional[str]
    input_data: Optional[Dict[str, Any]]
    output_data: Optional[Dict[str, Any]]
    status: WorkflowExecutionStatus
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    execution_time: Optional[float]
    current_step: Optional[int]
    total_steps: Optional[int]
    error_message: Optional[str]
    metadata: Optional[Dict[str, Any]]

    model_config = ConfigDict(from_attributes=True)


class WorkflowExecutionLog(BaseModel):
    """Schema for workflow execution log."""
    timestamp: datetime
    level: str = Field(..., description="Log level")
    message: str = Field(..., description="Log message")
    step: Optional[str] = Field(None, description="Step name")


class WorkflowExecutionCreate(BaseModel):
    """Schema for creating workflow execution."""
    workflow_id: UUID = Field(..., description="Workflow ID")
    user_id: UUID = Field(..., description="User ID")
    trigger_type: Optional[str] = Field(None, description="Execution trigger type")
    input_data: Optional[Dict[str, Any]] = Field(None, description="Input data")


class WorkflowExecutionUpdate(BaseModel):
    """Schema for updating workflow execution."""
    status: Optional[WorkflowExecutionStatus] = Field(None, description="Execution status")
    started_at: Optional[datetime] = Field(None, description="Start time")
    completed_at: Optional[datetime] = Field(None, description="Completion time")
    execution_time: Optional[float] = Field(None, description="Execution time")
    current_step: Optional[int] = Field(None, description="Current step")
    total_steps: Optional[int] = Field(None, description="Total steps")
    output_data: Optional[Dict[str, Any]] = Field(None, description="Output data")
    error_message: Optional[str] = Field(None, description="Error message")
    logs: Optional[List[WorkflowExecutionLog]] = Field(None, description="Execution logs")


class WorkflowTemplateBase(BaseModel):
    """Base workflow template schema."""
    name: str = Field(..., min_length=1, max_length=100, description="Template name")
    description: Optional[str] = Field(None, max_length=500, description="Template description")
    category: Optional[str] = Field(None, min_length=1, max_length=50, description="Template category")
    version: str = Field("1.0.0", min_length=1, max_length=20, description="Template version")
    config_schema: Optional[Dict[str, Any]] = Field(None, description="Template configuration schema")
    input_schema: Optional[Dict[str, Any]] = Field(None, description="Template input schema")
    output_schema: Optional[Dict[str, Any]] = Field(None, description="Template output schema")
    steps: Optional[List[Dict[str, Any]]] = Field(None, description="Template steps definition")
    triggers: Optional[List[Dict[str, Any]]] = Field(None, description="Template triggers")
    tags: Optional[List[str]] = Field(None, description="Template tags")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate template name."""
        if not v.strip():
            raise ValueError("Template name cannot be empty")
        return v.strip()


class WorkflowTemplateCreate(WorkflowTemplateBase):
    """Schema for creating a new workflow template."""
    pass


class WorkflowTemplateResponse(WorkflowTemplateBase):
    """Schema for workflow template response."""
    id: UUID
    created_at: datetime
    updated_at: datetime
    usage_count: int
    author: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class WorkflowStats(BaseModel):
    """Workflow statistics."""
    total_workflows: int
    active_workflows: int
    total_executions: int
    category_distribution: Dict[str, int]
    execution_status_distribution: Dict[str, int]
    average_execution_time: float