"""
Android项目构建工具 - 异步数据库核心模块

提供：
1. 异步SQLAlchemy集成
2. 高性能异步连接池管理
3. 异步事务管理
4. 异步迁移系统
5. 性能监控和优化
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, Generator, List, Optional, Type, TypeVar, Union
from functools import wraps
import time
import uuid

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base, DeferredReflection
from sqlalchemy.orm import relationship, sessionmaker, Session
from sqlalchemy.pool import StaticPool, QueuePool
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, JSON, ForeignKey, Index, select, update, delete, func
from pydantic import BaseModel

from .models import (
    Base, Project, Build, BuildLog, BuildArtifact, GitOperation,
    ProjectConfiguration, SystemMetrics,
    ProjectInDB, BuildInDB, BuildLogInDB, GitOperationInDB,
    DatabaseConfig
)

# 配置日志
logger = logging.getLogger(__name__)

# 泛型类型变量
ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class AsyncDatabaseManager:
    """异步数据库管理器"""

    def __init__(self, database_url: Optional[str] = None):
        """
        初始化异步数据库管理器

        Args:
            database_url: 数据库连接URL，如果为None则使用默认SQLite
        """
        self.database_url = database_url or "sqlite+aiosqlite:///android_build_tool.db"
        self.async_engine: Optional[Engine] = None
        self.sync_engine: Optional[Engine] = None  # 用于迁移等同步操作
        self.AsyncSessionLocal: Optional[async_sessionmaker] = None
        self.SessionLocal: Optional[sessionmaker] = None
        self._initialized = False
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """初始化数据库连接"""
        if self._initialized:
            return

        async with self._lock:
            if self._initialized:
                return

            logger.info(f"初始化异步数据库连接: {self.database_url}")

            # 创建异步引擎
            await self._create_async_engine()

            # 创建同步引擎（用于迁移）
            await self._create_sync_engine()

            # 创建会话工厂
            self._create_session_factories()

            # 应用性能优化
            await self._apply_optimizations()

            # 创建所有表
            await self._create_tables()

            self._initialized = True
            logger.info("异步数据库初始化完成")

    async def _create_async_engine(self):
        """创建异步引擎"""
        if self.database_url.startswith("sqlite"):
            self.async_engine = create_async_engine(
                self.database_url,
                echo=False,  # 生产环境关闭SQL日志
                pool_pre_ping=True,
                poolclass=StaticPool,
                connect_args={
                    "check_same_thread": False,
                    "timeout": 20,
                    "isolation_level": None,
                }
            )
        else:
            self.async_engine = create_async_engine(
                self.database_url,
                echo=False,
                pool_pre_ping=True,
                poolclass=QueuePool,
                pool_size=10,
                max_overflow=20,
                pool_timeout=30,
                pool_recycle=3600,
            )

    async def _create_sync_engine(self):
        """创建同步引擎"""
        sync_url = self.database_url.replace("+aiosqlite", "")
        self.sync_engine = create_engine(
            sync_url,
            echo=False,
            pool_pre_ping=True,
            poolclass=StaticPool,
            connect_args={
                "check_same_thread": False,
                "timeout": 20,
            }
        )

    def _create_session_factories(self):
        """创建会话工厂"""
        # 异步会话工厂
        self.AsyncSessionLocal = async_sessionmaker(
            bind=self.async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False
        )

        # 同步会话工厂
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.sync_engine
        )

    async def _apply_optimizations(self):
        """应用SQLite性能优化"""
        if not self.database_url.startswith("sqlite"):
            return

        async with self.async_engine.begin() as conn:
            # SQLite性能优化参数
            optimizations = [
                ("journal_mode", "WAL"),              # 写前日志模式
                ("synchronous", "NORMAL"),            # 平衡性能和安全性
                ("cache_size", "-64000"),             # 64MB缓存
                ("temp_store", "MEMORY"),             # 临时表存储在内存中
                ("mmap_size", "268435456"),          # 256MB内存映射
                ("locking_mode", "NORMAL"),           # 正常锁定模式
                ("foreign_keys", "ON"),               # 启用外键约束
                ("wal_autocheckpoint", "1000"),       # WAL自动检查点
                ("page_size", "4096"),                # 页面大小
                ("busy_timeout", "30000"),            # 锁超时
            ]

            for pragma, value in optimizations:
                await conn.execute(text(f"PRAGMA {pragma} = {value}"))

            logger.debug("SQLite性能优化配置已应用")

    async def _create_tables(self):
        """创建所有表"""
        async with self.async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def get_async_session(self) -> AsyncSession:
        """获取异步数据库会话"""
        if not self._initialized:
            await self.initialize()
        return self.AsyncSessionLocal()

    def get_sync_session(self) -> Session:
        """获取同步数据库会话"""
        if not self._initialized:
            raise RuntimeError("数据库未初始化，请先调用 initialize()")
        return self.SessionLocal()

    @asynccontextmanager
    async def get_async_db_session(self) -> Generator[AsyncSession, None, None]:
        """获取异步数据库会话的上下文管理器"""
        session = await self.get_async_session()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"异步数据库操作失败: {e}")
            raise
        finally:
            await session.close()

    async def close(self) -> None:
        """关闭数据库连接"""
        async with self._lock:
            if self.async_engine:
                await self.async_engine.dispose()
            if self.sync_engine:
                self.sync_engine.dispose()
            self._initialized = False
            logger.info("异步数据库连接已关闭")


class AsyncBaseRepository:
    """异步基础仓储类"""

    def __init__(self, model: Type[ModelType], db_manager: AsyncDatabaseManager):
        """
        初始化异步仓储

        Args:
            model: SQLAlchemy模型类
            db_manager: 异步数据库管理器
        """
        self.model = model
        self.db_manager = db_manager
        self.model_name = model.__name__

    async def create(self, obj_in: CreateSchemaType) -> ModelType:
        """
        创建新记录

        Args:
            obj_in: 创建数据的Pydantic模型

        Returns:
            创建的数据库模型实例
        """
        try:
            async with self.db_manager.get_async_db_session() as session:
                obj_data = obj_in.dict() if hasattr(obj_in, 'dict') else obj_in
                db_obj = self.model(**obj_data)
                session.add(db_obj)
                await session.flush()  # 不立即提交，但获取ID
                await session.refresh(db_obj)
                logger.info(f"创建{self.model_name}记录成功: ID={db_obj.id}")
                return db_obj
        except IntegrityError as e:
            logger.error(f"创建{self.model_name}失败 - 数据完整性错误: {e}")
            raise ValueError(f"数据完整性错误: {e}")
        except SQLAlchemyError as e:
            logger.error(f"创建{self.model_name}失败: {e}")
            raise

    async def get(self, id: int) -> Optional[ModelType]:
        """
        根据ID获取记录

        Args:
            id: 记录ID

        Returns:
            数据库模型实例或None
        """
        try:
            async with self.db_manager.get_async_db_session() as session:
                result = await session.execute(select(self.model).where(self.model.id == id))
                return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"查询{self.model_name}失败: {e}")
            return None

    async def get_multi(
        self,
        skip: int = 0,
        limit: int = 100,
        **filters
    ) -> List[ModelType]:
        """
        获取多条记录

        Args:
            skip: 跳过记录数
            limit: 限制记录数
            **filters: 过滤条件

        Returns:
            数据库模型实例列表
        """
        try:
            async with self.db_manager.get_async_db_session() as session:
                query = select(self.model)

                # 应用过滤条件
                for key, value in filters.items():
                    if hasattr(self.model, key) and value is not None:
                        query = query.where(getattr(self.model, key) == value)

                # 应用分页
                query = query.offset(skip).limit(limit)
                result = await session.execute(query)
                return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"查询{self.model_name}多条记录失败: {e}")
            return []

    async def update(
        self,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        """
        更新记录

        Args:
            db_obj: 要更新的数据库模型实例
            obj_in: 更新数据的Pydantic模型或字典

        Returns:
            更新后的数据库模型实例
        """
        try:
            async with self.db_manager.get_async_db_session() as session:
                # 获取最新的对象
                result = await session.execute(select(self.model).where(self.model.id == db_obj.id))
                current_obj = result.scalar_one_or_none()
                if not current_obj:
                    raise ValueError(f"{self.model_name}记录不存在: ID={db_obj.id}")

                # 更新字段
                if hasattr(obj_in, 'dict'):
                    update_data = obj_in.dict(exclude_unset=True)
                else:
                    update_data = obj_in

                for field, value in update_data.items():
                    if hasattr(current_obj, field):
                        setattr(current_obj, field, value)

                await session.flush()
                await session.refresh(current_obj)
                logger.info(f"更新{self.model_name}记录成功: ID={current_obj.id}")
                return current_obj
        except SQLAlchemyError as e:
            logger.error(f"更新{self.model_name}失败: {e}")
            raise

    async def delete(self, id: int) -> ModelType:
        """
        删除记录

        Args:
            id: 记录ID

        Returns:
            被删除的数据库模型实例
        """
        try:
            async with self.db_manager.get_async_db_session() as session:
                result = await session.execute(select(self.model).where(self.model.id == id))
                obj = result.scalar_one_or_none()
                if obj is None:
                    raise ValueError(f"{self.model_name}记录不存在: ID={id}")

                await session.delete(obj)
                await session.flush()
                logger.info(f"删除{self.model_name}记录成功: ID={id}")
                return obj
        except SQLAlchemyError as e:
            logger.error(f"删除{self.model_name}失败: {e}")
            raise

    async def count(self, **filters) -> int:
        """
        统计记录数量

        Args:
            **filters: 过滤条件

        Returns:
            记录数量
        """
        try:
            async with self.db_manager.get_async_db_session() as session:
                query = select(func.count(self.model.id))
                for key, value in filters.items():
                    if hasattr(self.model, key) and value is not None:
                        query = query.where(getattr(self.model, key) == value)
                result = await session.execute(query)
                return result.scalar()
        except SQLAlchemyError as e:
            logger.error(f"统计{self.model_name}记录失败: {e}")
            return 0

    async def exists(self, **filters) -> bool:
        """
        检查记录是否存在

        Args:
            **filters: 过滤条件

        Returns:
            是否存在
        """
        try:
            async with self.db_manager.get_async_db_session() as session:
                query = select(self.model).limit(1)
                for key, value in filters.items():
                    if hasattr(self.model, key) and value is not None:
                        query = query.where(getattr(self.model, key) == value)
                result = await session.execute(query)
                return result.scalar_one_or_none() is not None
        except SQLAlchemyError as e:
            logger.error(f"检查{self.model_name}记录存在性失败: {e}")
            return False


class AsyncProjectRepository(AsyncBaseRepository):
    """项目异步仓储类"""

    def __init__(self, db_manager: AsyncDatabaseManager):
        super().__init__(Project, db_manager)

    async def get_by_name(self, name: str) -> Optional[Project]:
        """根据名称获取项目"""
        try:
            async with self.db_manager.get_async_db_session() as session:
                result = await session.execute(select(Project).where(Project.name == name))
                return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"根据名称查询项目失败: {e}")
            return None

    async def get_active_projects(self) -> List[Project]:
        """获取所有活跃项目"""
        try:
            async with self.db_manager.get_async_db_session() as session:
                result = await session.execute(
                    select(Project)
                    .where(Project.is_active == True)
                    .order_by(Project.created_at.desc())
                )
                return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"查询活跃项目失败: {e}")
            return []

    async def get_by_type(self, project_type: str) -> List[Project]:
        """根据类型获取项目"""
        try:
            async with self.db_manager.get_async_db_session() as session:
                result = await session.execute(
                    select(Project).where(Project.project_type == project_type)
                )
                return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"根据类型查询项目失败: {e}")
            return []

    async def search_projects(self, keyword: str) -> List[Project]:
        """搜索项目（按名称或描述）"""
        try:
            async with self.db_manager.get_async_db_session() as session:
                result = await session.execute(
                    select(Project).where(
                        (Project.name.contains(keyword)) |
                        (Project.description.contains(keyword))
                    )
                )
                return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"搜索项目失败: {e}")
            return []

    async def get_projects_with_build_stats(self) -> List[Dict[str, Any]]:
        """获取项目及其构建统计"""
        try:
            async with self.db_manager.get_async_db_session() as session:
                result = await session.execute(text("""
                    SELECT
                        p.*,
                        COUNT(b.id) as total_builds,
                        COUNT(CASE WHEN b.status = 'success' THEN 1 END) as successful_builds,
                        MAX(b.started_at) as last_build_at
                    FROM projects p
                    LEFT JOIN builds b ON p.id = b.project_id
                    GROUP BY p.id
                    ORDER BY p.created_at DESC
                """))
                return [dict(row) for row in result]
        except SQLAlchemyError as e:
            logger.error(f"获取项目构建统计失败: {e}")
            return []


class AsyncBuildRepository(AsyncBaseRepository):
    """构建异步仓储类"""

    def __init__(self, db_manager: AsyncDatabaseManager):
        super().__init__(Build, db_manager)

    async def get_by_project(self, project_id: int, skip: int = 0, limit: int = 100) -> List[Build]:
        """获取项目的构建历史"""
        try:
            async with self.db_manager.get_async_db_session() as session:
                result = await session.execute(
                    select(Build)
                    .where(Build.project_id == project_id)
                    .order_by(Build.build_number.desc())
                    .offset(skip).limit(limit)
                )
                return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"查询项目构建历史失败: {e}")
            return []

    async def get_latest_build(self, project_id: int) -> Optional[Build]:
        """获取项目的最新构建"""
        try:
            async with self.db_manager.get_async_db_session() as session:
                result = await session.execute(
                    select(Build)
                    .where(Build.project_id == project_id)
                    .order_by(Build.build_number.desc())
                    .limit(1)
                )
                return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"查询最新构建失败: {e}")
            return None

    async def get_running_builds(self) -> List[Build]:
        """获取所有正在运行的构建"""
        try:
            async with self.db_manager.get_async_db_session() as session:
                result = await session.execute(
                    select(Build)
                    .where(Build.status == 'running')
                    .order_by(Build.started_at.asc())
                )
                return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"查询运行中的构建失败: {e}")
            return []

    async def get_builds_by_status(self, status: str, limit: int = 100) -> List[Build]:
        """根据状态获取构建"""
        try:
            async with self.db_manager.get_async_db_session() as session:
                result = await session.execute(
                    select(Build)
                    .where(Build.status == status)
                    .order_by(Build.started_at.desc())
                    .limit(limit)
                )
                return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"根据状态查询构建失败: {e}")
            return []

    async def update_build_status(self, build_id: int, status: str, **kwargs) -> bool:
        """更新构建状态"""
        try:
            async with self.db_manager.get_async_db_session() as session:
                update_data = {"status": status, **kwargs}

                if status in ["success", "failed", "cancelled"]:
                    update_data["completed_at"] = datetime.utcnow()

                result = await session.execute(
                    update(Build)
                    .where(Build.id == build_id)
                    .values(**update_data)
                )

                await session.flush()
                return result.rowcount > 0
        except SQLAlchemyError as e:
            logger.error(f"更新构建状态失败: {e}")
            return False

    async def get_build_statistics(self, project_id: Optional[int] = None, days: int = 30) -> Dict[str, Any]:
        """获取构建统计"""
        try:
            async with self.db_manager.get_async_db_session() as session:
                query = text(f"""
                    SELECT
                        COUNT(*) as total_builds,
                        COUNT(CASE WHEN status = 'success' THEN 1 END) as successful_builds,
                        COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_builds,
                        COUNT(CASE WHEN status = 'running' THEN 1 END) as running_builds,
                        AVG(CASE WHEN duration_seconds IS NOT NULL THEN duration_seconds END) as avg_duration,
                        MAX(CASE WHEN duration_seconds IS NOT NULL THEN duration_seconds END) as max_duration
                    FROM builds
                    WHERE started_at >= datetime('now', '-{days} days')
                    {f"AND project_id = {project_id}" if project_id else ""}
                """)

                result = await session.execute(query)
                stats = dict(result.first())

                # 计算成功率
                if stats["total_builds"] > 0:
                    stats["success_rate"] = (stats["successful_builds"] / stats["total_builds"]) * 100
                else:
                    stats["success_rate"] = 0

                return stats
        except SQLAlchemyError as e:
            logger.error(f"获取构建统计失败: {e}")
            return {}

    async def get_next_build_number(self, project_id: int) -> int:
        """获取下一个构建编号"""
        try:
            async with self.db_manager.get_async_db_session() as session:
                result = await session.execute(
                    select(func.coalesce(func.max(Build.build_number), 0))
                    .where(Build.project_id == project_id)
                )
                max_number = result.scalar() or 0
                return max_number + 1
        except SQLAlchemyError as e:
            logger.error(f"获取下一个构建编号失败: {e}")
            return 1


class AsyncBuildLogRepository(AsyncBaseRepository):
    """构建日志异步仓储类"""

    def __init__(self, db_manager: AsyncDatabaseManager):
        super().__init__(BuildLog, db_manager)

    async def get_build_logs(
        self,
        build_id: int,
        skip: int = 0,
        limit: int = 1000,
        level: Optional[str] = None
    ) -> List[BuildLog]:
        """获取构建日志（支持分页和过滤）"""
        try:
            async with self.db_manager.get_async_db_session() as session:
                query = select(BuildLog).where(BuildLog.build_id == build_id)

                if level:
                    query = query.where(BuildLog.level == level)

                query = query.order_by(BuildLog.sequence_number.asc()).offset(skip).limit(limit)
                result = await session.execute(query)
                return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"查询构建日志失败: {e}")
            return []

    async def get_logs_by_level(self, build_id: int, level: str) -> List[BuildLog]:
        """根据日志级别获取日志"""
        try:
            async with self.db_manager.get_async_db_session() as session:
                result = await session.execute(
                    select(BuildLog)
                    .where(
                        BuildLog.build_id == build_id,
                        BuildLog.level == level
                    )
                    .order_by(BuildLog.timestamp.asc())
                )
                return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"根据级别查询日志失败: {e}")
            return []

    async def batch_create_logs(self, logs: List[Dict[str, Any]]) -> bool:
        """批量创建构建日志（性能优化）"""
        try:
            async with self.db_manager.get_async_db_session() as session:
                # 使用bulk_insert_mappings提高性能
                session.bulk_insert_mappings(BuildLog, logs)
                await session.flush()
                logger.info(f"批量创建构建日志成功: {len(logs)}条")
                return True
        except SQLAlchemyError as e:
            logger.error(f"批量创建构建日志失败: {e}")
            return False

    async def get_next_sequence_number(self, build_id: int) -> int:
        """获取下一个日志序号"""
        try:
            async with self.db_manager.get_async_db_session() as session:
                result = await session.execute(
                    select(func.coalesce(func.max(BuildLog.sequence_number), 0))
                    .where(BuildLog.build_id == build_id)
                )
                max_sequence = result.scalar() or 0
                return max_sequence + 1
        except SQLAlchemyError as e:
            logger.error(f"获取下一个日志序号失败: {e}")
            return 1

    async def delete_old_logs(self, days: int = 90, limit: int = 10000) -> int:
        """删除旧日志"""
        try:
            async with self.db_manager.get_async_db_session() as session:
                cutoff_date = datetime.utcnow() - timedelta(days=days)

                result = await session.execute(
                    delete(BuildLog)
                    .where(BuildLog.timestamp < cutoff_date)
                    .limit(limit)
                )

                await session.flush()
                deleted_count = result.rowcount
                logger.info(f"删除旧日志: {deleted_count}条")
                return deleted_count
        except SQLAlchemyError as e:
            logger.error(f"删除旧日志失败: {e}")
            return 0


class AsyncGitOperationRepository(AsyncBaseRepository):
    """Git操作异步仓储类"""

    def __init__(self, db_manager: AsyncDatabaseManager):
        super().__init__(GitOperation, db_manager)

    async def get_project_git_history(self, project_id: int, limit: int = 100) -> List[GitOperation]:
        """获取项目的Git操作历史"""
        try:
            async with self.db_manager.get_async_db_session() as session:
                result = await session.execute(
                    select(GitOperation)
                    .where(GitOperation.project_id == project_id)
                    .order_by(GitOperation.started_at.desc())
                    .limit(limit)
                )
                return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"查询Git操作历史失败: {e}")
            return []

    async def get_operations_by_type(self, operation_type: str) -> List[GitOperation]:
        """根据操作类型获取Git操作"""
        try:
            async with self.db_manager.get_async_db_session() as session:
                result = await session.execute(
                    select(GitOperation)
                    .where(GitOperation.operation_type == operation_type)
                    .order_by(GitOperation.started_at.desc())
                )
                return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"根据类型查询Git操作失败: {e}")
            return []

    async def get_recent_operations(self, hours: int = 24, limit: int = 100) -> List[GitOperation]:
        """获取最近的Git操作"""
        try:
            async with self.db_manager.get_async_db_session() as session:
                cutoff_time = datetime.utcnow() - timedelta(hours=hours)

                result = await session.execute(
                    select(GitOperation)
                    .where(GitOperation.started_at >= cutoff_time)
                    .order_by(GitOperation.started_at.desc())
                    .limit(limit)
                )
                return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"查询最近Git操作失败: {e}")
            return []


class AsyncDatabaseService:
    """异步数据库服务类 - 提供高级数据库操作"""

    def __init__(self, db_manager: AsyncDatabaseManager):
        """
        初始化异步数据库服务

        Args:
            db_manager: 异步数据库管理器
        """
        self.db_manager = db_manager
        self.projects = AsyncProjectRepository(db_manager)
        self.builds = AsyncBuildRepository(db_manager)
        self.build_logs = AsyncBuildLogRepository(db_manager)
        self.git_operations = AsyncGitOperationRepository(db_manager)

    async def get_async_session(self) -> AsyncSession:
        """获取异步数据库会话"""
        return await self.db_manager.get_async_session()

    @asynccontextmanager
    async def transaction(self) -> Generator[AsyncSession, None, None]:
        """异步事务上下文管理器"""
        session = await self.get_async_session()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"异步事务执行失败: {e}")
            raise
        finally:
            await session.close()

    async def execute_with_retry(
        self,
        operation: callable,
        max_retries: int = 3,
        backoff_factor: float = 0.5
    ) -> Any:
        """带重试机制的异步操作执行"""
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                async with self.transaction() as session:
                    return await operation(session)
            except Exception as e:
                last_exception = e

                if attempt < max_retries:
                    wait_time = backoff_factor * (2 ** attempt)
                    logger.warning(f"数据库操作失败，{wait_time}s后重试 (尝试 {attempt + 1}/{max_retries + 1}): {e}")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"数据库操作最终失败: {e}")
                    break

        raise last_exception

    async def health_check(self) -> Dict[str, Any]:
        """数据库健康检查"""
        try:
            async with self.transaction() as session:
                # 检查数据库连接
                await session.execute(text("SELECT 1"))

                # 检查表是否存在
                inspector = inspect(session.bind.sync_engine if hasattr(session.bind, 'sync_engine') else session.bind)
                tables = inspector.get_table_names()

                # 统计记录数量
                stats = {}
                for table in ['projects', 'builds', 'build_logs', 'git_operations']:
                    if table in tables:
                        result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                        stats[table] = result.scalar()

                # 获取数据库性能指标
                performance_metrics = await self._get_performance_metrics(session)

                return {
                    'status': 'healthy',
                    'connection': 'ok',
                    'tables': tables,
                    'record_counts': stats,
                    'performance_metrics': performance_metrics
                }
        except Exception as e:
            logger.error(f"数据库健康检查失败: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e)
            }

    async def _get_performance_metrics(self, session: AsyncSession) -> Dict[str, Any]:
        """获取数据库性能指标"""
        metrics = {}

        try:
            # SQLite特定指标
            result = await session.execute(text("PRAGMA page_count"))
            metrics["page_count"] = result.scalar()

            result = await session.execute(text("PRAGMA page_size"))
            metrics["page_size"] = result.scalar()

            result = await session.execute(text("PRAGMA cache_size"))
            metrics["cache_size"] = abs(result.scalar()) * 1024  # 转换为字节

            result = await session.execute(text("PRAGMA journal_mode"))
            metrics["journal_mode"] = result.scalar()

            # 数据库大小
            result = await session.execute(text("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()"))
            metrics["database_size_bytes"] = result.scalar()

        except Exception as e:
            logger.warning(f"获取性能指标失败: {e}")

        return metrics

    async def cleanup_old_data(self, days: int = 90) -> Dict[str, int]:
        """清理旧数据"""
        cleanup_stats = {}

        try:
            # 清理构建日志
            deleted_logs = await self.build_logs.delete_old_logs(days)
            cleanup_stats["deleted_logs"] = deleted_logs

            # 清理系统指标
            async with self.transaction() as session:
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                result = await session.execute(
                    text("DELETE FROM system_metrics WHERE timestamp < :cutoff_date"),
                    {"cutoff_date": cutoff_date}
                )
                cleanup_stats["deleted_metrics"] = result.rowcount

            logger.info(f"数据清理完成: {cleanup_stats}")
            return cleanup_stats

        except Exception as e:
            logger.error(f"数据清理失败: {e}")
            return cleanup_stats

    async def get_database_statistics(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        try:
            async with self.transaction() as session:
                # 基础统计
                project_count = await session.execute(text("SELECT COUNT(*) FROM projects"))
                build_count = await session.execute(text("SELECT COUNT(*) FROM builds"))
                log_count = await session.execute(text("SELECT COUNT(*) FROM build_logs"))
                git_op_count = await session.execute(text("SELECT COUNT(*) FROM git_operations"))

                # 按状态统计构建
                build_stats = await session.execute(text("""
                    SELECT
                        status,
                        COUNT(*) as count,
                        AVG(duration_seconds) as avg_duration
                    FROM builds
                    WHERE duration_seconds IS NOT NULL
                    GROUP BY status
                """))

                # 最近活动统计
                recent_builds = await session.execute(text("""
                    SELECT COUNT(*) as count
                    FROM builds
                    WHERE started_at >= datetime('now', '-7 days')
                """))

                recent_logs = await session.execute(text("""
                    SELECT COUNT(*) as count
                    FROM build_logs
                    WHERE timestamp >= datetime('now', '-7 days')
                """))

                return {
                    "total_records": {
                        "projects": project_count.scalar(),
                        "builds": build_count.scalar(),
                        "build_logs": log_count.scalar(),
                        "git_operations": git_op_count.scalar()
                    },
                    "build_statistics": [dict(row) for row in build_stats],
                    "recent_activity": {
                        "builds_last_7_days": recent_builds.scalar(),
                        "logs_last_7_days": recent_logs.scalar()
                    }
                }
        except Exception as e:
            logger.error(f"获取数据库统计失败: {e}")
            return {}


# 性能监控装饰器
def monitor_async_query_performance(func):
    """监控异步查询性能的装饰器"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time

            if duration > 1.0:  # 超过1秒的查询记录警告
                logger.warning(f"慢查询检测: {func.__name__} 耗时 {duration:.2f}秒")
            else:
                logger.debug(f"查询 {func.__name__} 耗时 {duration:.3f}秒")

            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"查询失败: {func.__name__} 耗时 {duration:.3f}秒, 错误: {e}")
            raise

    return wrapper


# ================================
# 全局异步数据库实例
# ================================

# 创建全局异步数据库管理器
async_db_manager = AsyncDatabaseManager()

# 创建全局异步数据库服务
async_database_service = AsyncDatabaseService(async_db_manager)

# 导出常用函数
async def get_async_db_session() -> Generator[AsyncSession, None, None]:
    """获取异步数据库会话的依赖注入函数"""
    session = await async_db_manager.get_async_session()
    try:
        yield session
    finally:
        await session.close()

async def init_async_database():
    """初始化异步数据库"""
    await async_db_manager.initialize()

async def close_async_database():
    """关闭异步数据库连接"""
    await async_db_manager.close()