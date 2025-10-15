"""
Base repository pattern for async database operations.

This module provides the base repository class and common database operations
using SQLAlchemy 2.0 async patterns.
"""

from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from ..config.database import get_async_session

# Generic type for model classes
ModelType = TypeVar("ModelType", bound=DeclarativeBase)
CreateSchemaType = TypeVar("CreateSchemaType")
UpdateSchemaType = TypeVar("UpdateSchemaType")


class BaseAsyncRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """
    Base repository for async database operations.

    Provides common CRUD operations and can be extended for specific models.
    """

    def __init__(self, model: Type[ModelType]) -> None:
        """
        Initialize repository with model class.

        Args:
            model: SQLAlchemy model class
        """
        self.model = model

    async def get(
        self,
        db: AsyncSession,
        *,
        id: Union[UUID, int, str]
    ) -> Optional[ModelType]:
        """
        Get a single record by ID.

        Args:
            db: Database session
            id: Record identifier

        Returns:
            Model instance or None if not found
        """
        statement = select(self.model).where(self.model.id == id)
        result = await db.execute(statement)
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        **filters: Any
    ) -> List[ModelType]:
        """
        Get multiple records with optional filtering and pagination.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            **filters: Additional filter criteria

        Returns:
            List of model instances
        """
        statement = select(self.model)

        # Apply filters
        for key, value in filters.items():
            if hasattr(self.model, key) and value is not None:
                statement = statement.where(getattr(self.model, key) == value)

        # Apply pagination
        statement = statement.offset(skip).limit(limit)

        result = await db.execute(statement)
        return result.scalars().all()

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: CreateSchemaType
    ) -> ModelType:
        """
        Create a new record.

        Args:
            db: Database session
            obj_in: Creation schema/data

        Returns:
            Created model instance
        """
        if hasattr(obj_in, "model_dump"):
            create_data = obj_in.model_dump()
        else:
            create_data = obj_in

        db_obj = self.model(**create_data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        """
        Update an existing record.

        Args:
            db: Database session
            db_obj: Existing model instance to update
            obj_in: Update schema/data

        Returns:
            Updated model instance
        """
        if hasattr(obj_in, "model_dump"):
            update_data = obj_in.model_dump(exclude_unset=True)
        else:
            update_data = obj_in

        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def delete(
        self,
        db: AsyncSession,
        *,
        id: Union[UUID, int, str]
    ) -> Optional[ModelType]:
        """
        Delete a record by ID.

        Args:
            db: Database session
            id: Record identifier

        Returns:
            Deleted model instance or None if not found
        """
        obj = await self.get(db, id=id)
        if obj:
            await db.delete(obj)
            await db.commit()
        return obj

    async def delete_by_filters(
        self,
        db: AsyncSession,
        **filters: Any
    ) -> int:
        """
        Delete records matching given filters.

        Args:
            db: Database session
            **filters: Filter criteria

        Returns:
            Number of deleted records
        """
        statement = delete(self.model)

        for key, value in filters.items():
            if hasattr(self.model, key) and value is not None:
                statement = statement.where(getattr(self.model, key) == value)

        result = await db.execute(statement)
        await db.commit()
        return result.rowcount

    async def count(
        self,
        db: AsyncSession,
        **filters: Any
    ) -> int:
        """
        Count records matching given filters.

        Args:
            db: Database session
            **filters: Filter criteria

        Returns:
            Number of matching records
        """
        from sqlalchemy import func

        statement = select(func.count(self.model.id))

        for key, value in filters.items():
            if hasattr(self.model, key) and value is not None:
                statement = statement.where(getattr(self.model, key) == value)

        result = await db.execute(statement)
        return result.scalar()

    async def exists(
        self,
        db: AsyncSession,
        **filters: Any
    ) -> bool:
        """
        Check if a record exists matching given filters.

        Args:
            db: Database session
            **filters: Filter criteria

        Returns:
            True if record exists, False otherwise
        """
        count = await self.count(db, **filters)
        return count > 0

    async def get_or_create(
        self,
        db: AsyncSession,
        *,
        defaults: Optional[Dict[str, Any]] = None,
        **filters: Any
    ) -> tuple[ModelType, bool]:
        """
        Get a record by filters or create it if it doesn't exist.

        Args:
            db: Database session
            defaults: Default values for creation
            **filters: Filter criteria to find existing record

        Returns:
            Tuple of (model_instance, created_flag)
        """
        # Try to find existing record
        existing = await self.get_multi(db, limit=1, **filters)
        if existing:
            return existing[0], False

        # Create new record with defaults and filters
        create_data = defaults or {}
        create_data.update(filters)

        return await self.create(db, obj_in=create_data), True


class DatabaseManager:
    """Utility class for database operations across repositories."""

    @staticmethod
    async def with_session(
        operation_func,
        *args,
        **kwargs
    ):
        """
        Execute a database operation with a session.

        Args:
            operation_func: Function that takes a session as first argument
            *args: Additional arguments to pass to operation_func
            **kwargs: Additional keyword arguments

        Returns:
            Result of the operation
        """
        async with get_async_session() as session:
            return await operation_func(session, *args, **kwargs)

    @staticmethod
    async def execute_raw_sql(
        db: AsyncSession,
        sql: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Execute raw SQL statement.

        Args:
            db: Database session
            sql: SQL statement to execute
            params: Parameters for the SQL statement

        Returns:
            Execution result
        """
        from sqlalchemy import text

        statement = text(sql)
        if params:
            result = await db.execute(statement, params)
        else:
            result = await db.execute(statement)

        return result