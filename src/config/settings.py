"""
Application settings and configuration management.

This module handles all application configuration using Pydantic settings,
with support for environment variables, validation, and type safety.
"""

import os
from pathlib import Path
from typing import List, Optional

from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings with environment variable support.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        validate_assignment=True,
    )

    # Application settings
    app_name: str = Field(default="Android项目构建工具", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode")
    host: str = Field(default="127.0.0.1", description="Server host")
    port: int = Field(default=8000, ge=1, le=65535, description="Server port")

    # Database settings
    database_url: str = Field(
        default="sqlite+aiosqlite:///./android_builder.db",
        description="Database connection URL"
    )

    # File storage settings
    upload_dir: str = Field(default="./uploads", description="Upload directory")
    max_file_size: int = Field(default=524288000, description="Max file size in bytes (500MB)")
    allowed_extensions: List[str] = Field(default=[".zip"], description="Allowed file extensions")

    # Git settings
    git_auto_backup: bool = Field(default=True, description="Auto backup before Git operations")
    git_commit_author: str = Field(
        default="Android Builder <builder@example.com>",
        description="Default Git commit author"
    )
    git_max_commit_message_length: int = Field(
        default=1000,
        ge=1,
        le=2000,
        description="Maximum commit message length"
    )

    # Build settings
    gradle_timeout: int = Field(default=1800, description="Gradle build timeout in seconds")
    max_concurrent_builds: int = Field(default=3, ge=1, le=10, description="Max concurrent builds")
    default_gradle_tasks: List[str] = Field(
        default=["clean", ":app:assembleRelease"],
        description="Default Gradle tasks"
    )

    # Security settings
    secret_key: str = Field(
        default="change-this-in-production",
        min_length=32,
        description="Secret key for token signing"
    )
    algorithm: str = Field(default="HS256", description="Token algorithm")
    access_token_expire_minutes: int = Field(
        default=30,
        ge=1,
        description="Access token expiration in minutes"
    )

    # Logging settings
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: Optional[str] = Field(default="logs/app.log", description="Log file path")

    # CORS settings
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000"],
        description="CORS allowed origins"
    )

    # Performance settings
    max_upload_memory: int = Field(
        default=104857600,
        description="Max memory for file uploads (100MB)"
    )
    chunk_size: int = Field(default=1048576, description="File upload chunk size (1MB)")

    # Resource cleanup settings
    temp_file_cleanup_interval: int = Field(
        default=3600,
        description="Temp file cleanup interval in seconds"
    )
    auto_delete_temp_files: bool = Field(default=True, description="Auto delete temp files")

    @validator("upload_dir", "log_file")
    def create_directories(cls, v):
        """Create directories if they don't exist."""
        if v:
            Path(v).parent.mkdir(parents=True, exist_ok=True)
        return v

    @validator("database_url")
    def validate_database_url(cls, v):
        """Validate database URL format."""
        if not v.startswith(("sqlite+aiosqlite://", "postgresql+asyncpg://", "mysql+aiomysql://")):
            raise ValueError("Database URL must use async driver (sqlite+aiosqlite, postgresql+asyncpg, mysql+aiomysql)")
        return v

    @validator("log_level")
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {', '.join(valid_levels)}")
        return v.upper()

    @validator("allowed_extensions")
    def validate_extensions(cls, v):
        """Validate file extensions."""
        if not isinstance(v, list):
            raise ValueError("allowed_extensions must be a list")
        for ext in v:
            if not ext.startswith("."):
                raise ValueError(f"File extension must start with '.': {ext}")
        return v

    @validator("default_gradle_tasks")
    def validate_gradle_tasks(cls, v):
        """Validate Gradle tasks."""
        if not isinstance(v, list):
            raise ValueError("default_gradle_tasks must be a list")
        for task in v:
            if not task or not isinstance(task, str):
                raise ValueError("Gradle tasks must be non-empty strings")
        return v

    @validator("cors_origins")
    def validate_cors_origins(cls, v):
        """Validate CORS origins."""
        if not isinstance(v, list):
            raise ValueError("cors_origins must be a list")
        for origin in v:
            if not isinstance(origin, str):
                raise ValueError("CORS origins must be strings")
            if not origin.startswith(("http://", "https://", "*")):
                raise ValueError(f"CORS origin must be a valid URL: {origin}")
        return v

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.debug

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return not self.debug

    @property
    def database_path(self) -> Path:
        """Get database file path."""
        if self.database_url.startswith("sqlite+aiosqlite://"):
            return Path(self.database_url.replace("sqlite+aiosqlite:///", ""))
        return Path("")

    @property
    def uploads_path(self) -> Path:
        """Get uploads directory path."""
        return Path(self.upload_dir)

    @property
    def upload_directory(self) -> str:
        """Get upload directory path as string."""
        return self.upload_dir

    def get_cors_origins(self) -> List[str]:
        """Get CORS origins for FastAPI middleware."""
        if self.debug and "*://localhost:*" not in self.cors_origins:
            return self.cors_origins + ["*://localhost:*"]
        return self.cors_origins


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get global settings instance.

    Returns:
        Settings: Application settings
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """
    Reload settings from environment variables.

    Returns:
        Settings: Fresh settings instance
    """
    global _settings
    _settings = Settings()
    return _settings


def get_database_url() -> str:
    """
    Get database URL.

    Returns:
        str: Database connection URL
    """
    return get_settings().database_url


def get_upload_config() -> dict:
    """
    Get upload configuration.

    Returns:
        dict: Upload configuration
    """
    settings = get_settings()
    return {
        "upload_dir": settings.upload_dir,
        "max_file_size": settings.max_file_size,
        "allowed_extensions": settings.allowed_extensions,
        "max_upload_memory": settings.max_upload_memory,
        "chunk_size": settings.chunk_size,
    }


def get_build_config() -> dict:
    """
    Get build configuration.

    Returns:
        dict: Build configuration
    """
    settings = get_settings()
    return {
        "gradle_timeout": settings.gradle_timeout,
        "max_concurrent_builds": settings.max_concurrent_builds,
        "default_gradle_tasks": settings.default_gradle_tasks,
    }


def get_git_config() -> dict:
    """
    Get Git configuration.

    Returns:
        dict: Git configuration
    """
    settings = get_settings()
    return {
        "auto_backup": settings.git_auto_backup,
        "commit_author": settings.git_commit_author,
        "max_commit_message_length": settings.git_max_commit_message_length,
    }


# Environment-specific settings
def is_development() -> bool:
    """Check if running in development environment."""
    return get_settings().is_development


def is_production() -> bool:
    """Check if running in production environment."""
    return get_settings().is_production