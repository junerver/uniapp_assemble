"""
Base Pydantic models for the Android build tool.

This module contains base models, schemas, and common data structures
used throughout the application for data validation and serialization.
"""

from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, validator
from pydantic.generics import GenericModel

# Generic type for responses
ResponseType = TypeVar("ResponseType")


class BaseSchema(BaseModel):
    """
    Base schema with common configuration and fields.
    """

    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
        use_enum_values=True,
        extra="forbid",
    )


class TimestampedSchema(BaseSchema):
    """
    Base schema with timestamp fields.
    """

    id: UUID = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class SoftDeleteSchema(TimestampedSchema):
    """
    Base schema with soft delete support.
    """

    deleted_at: Optional[datetime] = Field(None, description="Deletion timestamp")
    is_deleted: bool = Field(False, description="Whether the record is deleted")

    @validator("deleted_at", always=True)
    def set_deleted_at(cls, v, values):
        """Set deleted_at when is_deleted is True."""
        if values.get("is_deleted") and v is None:
            return datetime.utcnow()
        return v


class PaginationParams(BaseModel):
    """
    Pagination parameters for list endpoints.
    """

    page: int = Field(1, ge=1, description="Page number (1-based)")
    size: int = Field(20, ge=1, le=100, description="Items per page")

    @property
    def skip(self) -> int:
        """Calculate skip offset for database queries."""
        return (self.page - 1) * self.size

    @property
    def limit(self) -> int:
        """Get limit for database queries."""
        return self.size


class PaginatedResponse(GenericModel, Generic[ResponseType]):
    """
    Standard paginated response structure.
    """

    items: List[ResponseType] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Items per page")
    pages: int = Field(..., description="Total number of pages")

    @classmethod
    def create(
        cls,
        items: List[ResponseType],
        total: int,
        page: int,
        size: int
    ) -> "PaginatedResponse[ResponseType]":
        """
        Create a paginated response.

        Args:
            items: List of items
            total: Total number of items
            page: Current page number
            size: Items per page

        Returns:
            PaginatedResponse instance
        """
        pages = (total + size - 1) // size  # Ceiling division
        return cls(
            items=items,
            total=total,
            page=page,
            size=size,
            pages=pages
        )


class SuccessResponse(BaseModel):
    """
    Standard success response structure.
    """

    success: bool = Field(True, description="Whether the operation was successful")
    message: str = Field(..., description="Success message")
    data: Optional[Dict[str, Any]] = Field(None, description="Optional response data")


class ErrorResponse(BaseModel):
    """
    Standard error response structure.
    """

    success: bool = Field(False, description="Whether the operation was successful")
    error: bool = Field(True, description="Whether this is an error response")
    message: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Application-specific error code")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional error details")


class HealthCheckResponse(BaseModel):
    """
    Health check response structure.
    """

    status: str = Field(..., description="Health status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Check timestamp")
    version: str = Field(..., description="Application version")
    checks: Dict[str, Any] = Field(default_factory=dict, description="Individual health checks")


class FileUploadResponse(BaseModel):
    """
    File upload response structure.
    """

    filename: str = Field(..., description="Original filename")
    file_path: str = Field(..., description="Stored file path")
    file_size: int = Field(..., description="File size in bytes")
    content_type: str = Field(..., description="File content type")
    upload_time: datetime = Field(default_factory=datetime.utcnow, description="Upload timestamp")


class BuildLogEntry(BaseModel):
    """
    Individual build log entry.
    """

    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Log timestamp")
    level: str = Field(..., description="Log level (INFO, WARNING, ERROR)")
    message: str = Field(..., description="Log message")
    source: str = Field(..., description="Log source (gradle, git, etc.)")


class GitOperationResult(BaseModel):
    """
    Git operation result structure.
    """

    operation: str = Field(..., description="Git operation type")
    success: bool = Field(..., description="Whether the operation was successful")
    commit_hash: Optional[str] = Field(None, description="Commit hash for successful operations")
    message: str = Field(..., description="Result message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Operation timestamp")


class ProgressUpdate(BaseModel):
    """
    Progress update for long-running operations.
    """

    operation_id: str = Field(..., description="Operation identifier")
    progress: int = Field(..., ge=0, le=100, description="Progress percentage")
    message: str = Field(..., description="Progress message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Update timestamp")


class FilterParams(BaseModel):
    """
    Base filter parameters for search endpoints.
    """

    search: Optional[str] = Field(None, description="Search term")
    sort_by: Optional[str] = Field(None, description="Sort field")
    sort_order: Optional[str] = Field("asc", regex="^(asc|desc)$", description="Sort order")

    @validator("sort_order")
    def validate_sort_order(cls, v):
        """Validate sort order."""
        return v.lower()


class DateRangeFilter(BaseModel):
    """
    Date range filter parameters.
    """

    start_date: Optional[datetime] = Field(None, description="Start date (inclusive)")
    end_date: Optional[datetime] = Field(None, description="End date (inclusive)")

    @validator("end_date")
    def validate_date_range(cls, v, values):
        """Validate that end_date is after start_date."""
        if v and "start_date" in values and values["start_date"]:
            if v < values["start_date"]:
                raise ValueError("end_date must be after start_date")
        return v


# Common field validators
def validate_non_empty_string(value: Optional[str]) -> Optional[str]:
    """Validate that string is not empty if provided."""
    if value is not None and value.strip() == "":
        raise ValueError("String cannot be empty")
    return value


def validate_positive_number(value: Optional[int]) -> Optional[int]:
    """Validate that number is positive if provided."""
    if value is not None and value <= 0:
        raise ValueError("Number must be positive")
    return value


def validate_file_path(value: Optional[str]) -> Optional[str]:
    """Validate file path format."""
    if value is not None:
        # Basic path validation
        if ".." in value:
            raise ValueError("File path cannot contain parent directory references")
        if value.startswith("/") and not value.startswith("./"):
            raise ValueError("File path must be relative")
    return value