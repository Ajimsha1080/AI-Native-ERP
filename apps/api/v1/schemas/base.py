"""Base schemas and types."""

from typing import Generic, TypeVar, Optional, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

T = TypeVar('T')


class PaginationParams(BaseModel):
    """Pagination parameters."""

    page: int = Field(1, ge=1, description="Page number (starting from 1)")
    page_size: int = Field(20, ge=1, le=100, description="Number of items per page")

    @property
    def offset(self) -> int:
        """Calculate offset."""
        return (self.page - 1) * self.page_size


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response."""

    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [],
                "total": 100,
                "page": 1,
                "page_size": 20,
                "total_pages": 5,
            }
        }
    )


class ErrorResponse(BaseModel):
    """Error response.

    Args:
        error: Error type
        message: Error message
        details: Optional error details
    """

    error: str
    message: str
    details: Optional[dict] = None


class SuccessResponse(BaseModel):
    """Success response.

    Args:
        message: Success message
        data: Optional data
    """

    message: str
    data: Optional[dict] = None


class MetaData(BaseModel):
    """Metadata for responses.

    Args:
        timestamp: ISO timestamp
        version: API version
    """

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = "1.0"


# ID and UUID schemas
class UUIDResponse(BaseModel):
    """Response with UUID.

    Args:
        id: UUID of created resource
    """

    id: UUID
