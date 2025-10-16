"""
Database configuration and connection management.

This module handles the SQLite database setup with async SQLAlchemy 2.0,
including connection pooling, session management, and configuration.
"""

import os
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import DeclarativeBase

from .settings import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    """SQLAlchemy Base class for all models."""
    pass


# Create async engine for SQLite
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    poolclass=StaticPool,
    connect_args={
        "check_same_thread": False,
        "timeout": 20,
    },
    pool_pre_ping=True,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get an async database session.

    Yields:
        AsyncSession: Database session for async operations

    Usage:
        async with get_async_session() as session:
            # Use session here
            pass

    Note:
        The session is automatically closed by the async context manager.
        Do not manually call session.close() as it will cause IllegalStateChangeError.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        # 注意：不需要手动关闭session，async with会自动处理


async def create_database_directory() -> None:
    """Create database directory if it doesn't exist."""
    db_path = Path(settings.database_url.replace("sqlite+aiosqlite:///", ""))
    if db_path != ":memory:":
        db_path.parent.mkdir(parents=True, exist_ok=True)


async def check_database_connection() -> bool:
    """
    Test database connection.

    Returns:
        bool: True if connection is successful, False otherwise
    """
    try:
        async with get_async_session() as session:
            await session.execute("SELECT 1")
            return True
    except Exception:
        return False


def get_engine():
    """Get the database engine instance."""
    return engine


def get_session_factory():
    """Get the session factory instance."""
    return AsyncSessionLocal