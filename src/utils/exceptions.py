"""
Custom exceptions and error handling utilities for the Android build tool.

This module defines custom exception classes and error handling utilities
to provide consistent error responses and logging throughout the application.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class BaseCustomException(Exception):
    """
    Base class for all custom exceptions.
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)


class DatabaseException(BaseCustomException):
    """Database-related exceptions."""

    def __init__(
        self,
        message: str = "Database operation failed",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message, "DATABASE_ERROR", details)


class GitException(BaseCustomException):
    """Git operation related exceptions."""

    def __init__(
        self,
        message: str = "Git operation failed",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message, "GIT_ERROR", details)


class GradleException(BaseCustomException):
    """Gradle build related exceptions."""

    def __init__(
        self,
        message: str = "Gradle build failed",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message, "GRADLE_ERROR", details)


class FileOperationException(BaseCustomException):
    """File operation related exceptions."""

    def __init__(
        self,
        message: str = "File operation failed",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message, "FILE_ERROR", details)


class ValidationException(BaseCustomException):
    """Data validation related exceptions."""

    def __init__(
        self,
        message: str = "Validation failed",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message, "VALIDATION_ERROR", details)


class ProjectNotFoundException(BaseCustomException):
    """Exception raised when an Android project is not found."""

    def __init__(
        self,
        project_id: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        message = f"Android project not found: {project_id}"
        super().__init__(message, "PROJECT_NOT_FOUND", details)


class BuildTaskException(BaseCustomException):
    """Build task related exceptions."""

    def __init__(
        self,
        message: str = "Build task operation failed",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message, "BUILD_TASK_ERROR", details)


class ResourcePackageException(BaseCustomException):
    """Resource package processing exceptions."""

    def __init__(
        self,
        message: str = "Resource package processing failed",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message, "RESOURCE_PACKAGE_ERROR", details)


class APKExtractionException(BaseCustomException):
    """APK extraction related exceptions."""

    def __init__(
        self,
        message: str = "APK extraction failed",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message, "APK_EXTRACTION_ERROR", details)


class ConfigurationException(BaseCustomException):
    """Application configuration related exceptions."""

    def __init__(
        self,
        message: str = "Configuration error",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message, "CONFIGURATION_ERROR", details)


class SecurityException(BaseCustomException):
    """Security related exceptions."""

    def __init__(
        self,
        message: str = "Security violation detected",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message, "SECURITY_ERROR", details)


# HTTP Exception helpers
def create_http_exception(
    status_code: int,
    message: str,
    error_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> HTTPException:
    """
    Create a standardized HTTPException.

    Args:
        status_code: HTTP status code
        message: Error message
        error_code: Application-specific error code
        details: Additional error details

    Returns:
        HTTPException instance
    """
    return HTTPException(
        status_code=status_code,
        detail={
            "error": True,
            "message": message,
            "error_code": error_code,
            "details": details or {},
        }
    )


def create_not_found_exception(resource: str, identifier: str) -> HTTPException:
    """Create a standardized 404 Not Found exception."""
    return create_http_exception(
        status_code=status.HTTP_404_NOT_FOUND,
        message=f"{resource} not found",
        error_code="NOT_FOUND",
        details={"resource": resource, "identifier": identifier}
    )


def create_validation_exception(message: str, field: Optional[str] = None) -> HTTPException:
    """Create a standardized 400 Validation exception."""
    details = {"field": field} if field else {}
    return create_http_exception(
        status_code=status.HTTP_400_BAD_REQUEST,
        message=message,
        error_code="VALIDATION_ERROR",
        details=details
    )


def create_conflict_exception(message: str, details: Optional[Dict[str, Any]] = None) -> HTTPException:
    """Create a standardized 409 Conflict exception."""
    return create_http_exception(
        status_code=status.HTTP_409_CONFLICT,
        message=message,
        error_code="CONFLICT",
        details=details
    )


def create_internal_server_exception(message: str, details: Optional[Dict[str, Any]] = None) -> HTTPException:
    """Create a standardized 500 Internal Server Error exception."""
    return create_http_exception(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message=message,
        error_code="INTERNAL_ERROR",
        details=details
    )


# Error response formatters
def format_error_response(
    error: bool = True,
    message: str = "An error occurred",
    error_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    status_code: int = 500
) -> JSONResponse:
    """
    Create a standardized error response.

    Args:
        error: Whether this is an error response
        message: Error message
        error_code: Application-specific error code
        details: Additional error details
        status_code: HTTP status code

    Returns:
        JSONResponse with standardized error format
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "error": error,
            "message": message,
            "error_code": error_code,
            "details": details or {},
        }
    )


# Exception handlers for FastAPI
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTPException instances."""
    return format_error_response(
        message=exc.detail.get("message", "HTTP Error"),
        error_code=exc.detail.get("error_code", "HTTP_ERROR"),
        details=exc.detail.get("details", {}),
        status_code=exc.status_code
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle FastAPI RequestValidationError instances."""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(x) for x in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })

    return format_error_response(
        message="Request validation failed",
        error_code="VALIDATION_ERROR",
        details={"validation_errors": errors},
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
    )


async def pydantic_validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """Handle Pydantic ValidationError instances."""
    return format_error_response(
        message="Data validation failed",
        error_code="PYDANTIC_VALIDATION_ERROR",
        details={"validation_errors": exc.errors()},
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle all other exceptions.

    This should be the last resort handler for unhandled exceptions.
    """
    logger.error(f"Unhandled exception in {request.method} {request.url}: {str(exc)}", exc_info=True)

    # Don't expose internal details in production
    if not logger.isEnabledFor(logging.DEBUG):
        return format_error_response(
            message="An internal server error occurred",
            error_code="INTERNAL_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return format_error_response(
        message=f"Internal server error: {str(exc)}",
        error_code="INTERNAL_ERROR",
        details={"exception_type": type(exc).__name__},
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    )


class ProjectAlreadyExistsError(BaseCustomException):
    """Exception raised when trying to create a project that already exists."""

    def __init__(
        self,
        message: str = "Project already exists",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message, "PROJECT_ALREADY_EXISTS", details)


class InvalidProjectPathError(BaseCustomException):
    """Exception raised when project path is invalid."""

    def __init__(
        self,
        message: str = "Invalid project path",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message, "INVALID_PROJECT_PATH", details)


class ProjectNotFoundError(BaseCustomException):
    """Exception raised when an Android project is not found."""

    def __init__(
        self,
        message: str = "Android project not found",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message, "PROJECT_NOT_FOUND", details)


def setup_exception_handlers(app) -> None:
    """
    Register exception handlers with FastAPI application.

    Args:
        app: FastAPI application instance
    """
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, pydantic_validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)