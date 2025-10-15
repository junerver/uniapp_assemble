"""
Android项目构建工具 - 数据库核心模块

提供：
1. SQLAlchemy数据库连接管理
2. Pydantic模型与SQLAlchemy模型集成
3. 高性能查询操作
4. 事务管理
5. 连接池优化
6. 性能监控
"""

import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional, Type, TypeVar, Union
from functools import wraps
import time

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
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


class DatabaseManager:
    """数据库管理器 - 负责连接、会话和性能优化"""

    def __init__(self, database_url: Optional[str] = None):
        """
        初始化数据库管理器

        Args:
            database_url: 数据库连接URL，如果为None则使用默认SQLite
        """
        self.database_url = database_url or DatabaseConfig.get_sqlite_uri()
        self.engine: Optional[Engine] = None
        self.SessionLocal: Optional[sessionmaker] = None
        self._initialized = False

    def initialize(self) -> None:
        """初始化数据库连接"""
        if self._initialized:
            return

        logger.info(f"初始化数据库连接: {self.database_url}")

        # 创建引擎，针对SQLite优化
        if self.database_url.startswith("sqlite"):
            self.engine = create_engine(
                self.database_url,
                poolclass=StaticPool,
                connect_args={
                    "check_same_thread": False,
                    "timeout": 20,
                    "isolation_level": None,
                },
                echo=False,  # 生产环境关闭SQL日志
                pool_pre_ping=True,
            )

            # 设置SQLite性能优化参数
            @event.listens_for(self.engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                for pragma, value in DatabaseConfig.PRAGMAS.items():
                    cursor.execute(f"PRAGMA {pragma} = {value}")
                cursor.close()

        else:
            # 其他数据库配置（MySQL、PostgreSQL等）
            self.engine = create_engine(
                self.database_url,
                **DatabaseConfig.POOL_CONFIG,
                echo=False,
                pool_pre_ping=True,
            )

        # 创建会话工厂
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )

        # 创建所有表
        Base.metadata.create_all(bind=self.engine)

        self._initialized = True
        logger.info("数据库初始化完成")

    def get_session(self) -> Session:
        """获取数据库会话"""
        if not self._initialized:
            self.initialize()
        return self.SessionLocal()

    @contextmanager
    def get_db_session(self) -> Generator[Session, None, None]:
        """获取数据库会话的上下文管理器"""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"数据库操作失败: {e}")
            raise
        finally:
            session.close()

    def close(self) -> None:
        """关闭数据库连接"""
        if self.engine:
            self.engine.dispose()
            self._initialized = False
            logger.info("数据库连接已关闭")


class BaseRepository:
    """基础仓储类 - 提供通用的CRUD操作"""

    def __init__(self, model: Type[ModelType], db_manager: DatabaseManager):
        """
        初始化仓储

        Args:
            model: SQLAlchemy模型类
            db_manager: 数据库管理器
        """
        self.model = model
        self.db_manager = db_manager
        self.model_name = model.__name__

    def create(self, db: Session, obj_in: CreateSchemaType) -> ModelType:
        """
        创建新记录

        Args:
            db: 数据库会话
            obj_in: 创建数据的Pydantic模型

        Returns:
            创建的数据库模型实例
        """
        try:
            obj_data = obj_in.dict()
            db_obj = self.model(**obj_data)
            db.add(db_obj)
            db.flush()  # 不立即提交，但获取ID
            logger.info(f"创建{self.model_name}记录成功: ID={db_obj.id}")
            return db_obj
        except IntegrityError as e:
            db.rollback()
            logger.error(f"创建{self.model_name}失败 - 数据完整性错误: {e}")
            raise ValueError(f"数据完整性错误: {e}")
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"创建{self.model_name}失败: {e}")
            raise

    def get(self, db: Session, id: int) -> Optional[ModelType]:
        """
        根据ID获取记录

        Args:
            db: 数据库会话
            id: 记录ID

        Returns:
            数据库模型实例或None
        """
        try:
            result = db.query(self.model).filter(self.model.id == id).first()
            logger.debug(f"查询{self.model_name}记录: ID={id}, 结果={result is not None}")
            return result
        except SQLAlchemyError as e:
            logger.error(f"查询{self.model_name}失败: {e}")
            return None

    def get_multi(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100,
        **filters
    ) -> List[ModelType]:
        """
        获取多条记录

        Args:
            db: 数据库会话
            skip: 跳过记录数
            limit: 限制记录数
            **filters: 过滤条件

        Returns:
            数据库模型实例列表
        """
        try:
            query = db.query(self.model)

            # 应用过滤条件
            for key, value in filters.items():
                if hasattr(self.model, key) and value is not None:
                    query = query.filter(getattr(self.model, key) == value)

            # 应用分页
            result = query.offset(skip).limit(limit).all()
            logger.debug(f"查询{self.model_name}多条记录: skip={skip}, limit={limit}, 结果数={len(result)}")
            return result
        except SQLAlchemyError as e:
            logger.error(f"查询{self.model_name}多条记录失败: {e}")
            return []

    def update(
        self,
        db: Session,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        """
        更新记录

        Args:
            db: 数据库会话
            db_obj: 要更新的数据库模型实例
            obj_in: 更新数据的Pydantic模型或字典

        Returns:
            更新后的数据库模型实例
        """
        try:
            if isinstance(obj_in, BaseModel):
                update_data = obj_in.dict(exclude_unset=True)
            else:
                update_data = obj_in

            for field, value in update_data.items():
                if hasattr(db_obj, field):
                    setattr(db_obj, field, value)

            db.add(db_obj)
            db.flush()
            logger.info(f"更新{self.model_name}记录成功: ID={db_obj.id}")
            return db_obj
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"更新{self.model_name}失败: {e}")
            raise

    def remove(self, db: Session, id: int) -> ModelType:
        """
        删除记录

        Args:
            db: 数据库会话
            id: 记录ID

        Returns:
            被删除的数据库模型实例
        """
        try:
            obj = db.query(self.model).get(id)
            if obj is None:
                raise ValueError(f"{self.model_name}记录不存在: ID={id}")

            db.delete(obj)
            db.flush()
            logger.info(f"删除{self.model_name}记录成功: ID={id}")
            return obj
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"删除{self.model_name}失败: {e}")
            raise

    def count(self, db: Session, **filters) -> int:
        """
        统计记录数量

        Args:
            db: 数据库会话
            **filters: 过滤条件

        Returns:
            记录数量
        """
        try:
            query = db.query(self.model)
            for key, value in filters.items():
                if hasattr(self.model, key) and value is not None:
                    query = query.filter(getattr(self.model, key) == value)
            return query.count()
        except SQLAlchemyError as e:
            logger.error(f"统计{self.model_name}记录失败: {e}")
            return 0


# ================================
# 专用仓储类
# ================================

class ProjectRepository(BaseRepository):
    """项目仓储类 - 提供项目特定的查询操作"""

    def __init__(self, db_manager: DatabaseManager):
        super().__init__(Project, db_manager)

    def get_by_name(self, db: Session, name: str) -> Optional[Project]:
        """根据名称获取项目"""
        try:
            return db.query(Project).filter(Project.name == name).first()
        except SQLAlchemyError as e:
            logger.error(f"根据名称查询项目失败: {e}")
            return None

    def get_active_projects(self, db: Session) -> List[Project]:
        """获取所有活跃项目"""
        try:
            return db.query(Project).filter(Project.is_active == True).all()
        except SQLAlchemyError as e:
            logger.error(f"查询活跃项目失败: {e}")
            return []

    def get_by_type(self, db: Session, project_type: str) -> List[Project]:
        """根据类型获取项目"""
        try:
            return db.query(Project).filter(Project.project_type == project_type).all()
        except SQLAlchemyError as e:
            logger.error(f"根据类型查询项目失败: {e}")
            return []

    def search_projects(self, db: Session, keyword: str) -> List[Project]:
        """搜索项目（按名称或描述）"""
        try:
            return db.query(Project).filter(
                (Project.name.contains(keyword)) |
                (Project.description.contains(keyword))
            ).all()
        except SQLAlchemyError as e:
            logger.error(f"搜索项目失败: {e}")
            return []


class BuildRepository(BaseRepository):
    """构建仓储类 - 提供构建特定的查询操作"""

    def __init__(self, db_manager: DatabaseManager):
        super().__init__(Build, db_manager)

    def get_by_project(self, db: Session, project_id: int, skip: int = 0, limit: int = 100) -> List[Build]:
        """获取项目的构建历史"""
        try:
            return db.query(Build).filter(
                Build.project_id == project_id
            ).order_by(Build.build_number.desc()).offset(skip).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"查询项目构建历史失败: {e}")
            return []

    def get_latest_build(self, db: Session, project_id: int) -> Optional[Build]:
        """获取项目的最新构建"""
        try:
            return db.query(Build).filter(
                Build.project_id == project_id
            ).order_by(Build.build_number.desc()).first()
        except SQLAlchemyError as e:
            logger.error(f"查询最新构建失败: {e}")
            return None

    def get_running_builds(self, db: Session) -> List[Build]:
        """获取所有正在运行的构建"""
        try:
            return db.query(Build).filter(
                Build.status == 'running'
            ).order_by(Build.started_at.asc()).all()
        except SQLAlchemyError as e:
            logger.error(f"查询运行中的构建失败: {e}")
            return []

    def get_builds_by_status(self, db: Session, status: str, limit: int = 100) -> List[Build]:
        """根据状态获取构建"""
        try:
            return db.query(Build).filter(
                Build.status == status
            ).order_by(Build.started_at.desc()).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"根据状态查询构建失败: {e}")
            return []

    def get_build_statistics(self, db: Session, project_id: int) -> Dict[str, Any]:
        """获取项目构建统计信息"""
        try:
            total = db.query(Build).filter(Build.project_id == project_id).count()
            successful = db.query(Build).filter(
                Build.project_id == project_id,
                Build.status == 'success'
            ).count()
            failed = db.query(Build).filter(
                Build.project_id == project_id,
                Build.status == 'failed'
            ).count()

            return {
                'total_builds': total,
                'successful_builds': successful,
                'failed_builds': failed,
                'success_rate': round(successful * 100.0 / total, 2) if total > 0 else 0,
                'pending_builds': total - successful - failed
            }
        except SQLAlchemyError as e:
            logger.error(f"获取构建统计失败: {e}")
            return {}


class BuildLogRepository(BaseRepository):
    """构建日志仓储类 - 提供日志特定的查询操作"""

    def __init__(self, db_manager: DatabaseManager):
        super().__init__(BuildLog, db_manager)

    def get_build_logs(
        self,
        db: Session,
        build_id: int,
        skip: int = 0,
        limit: int = 1000,
        level: Optional[str] = None
    ) -> List[BuildLog]:
        """获取构建日志（支持分页和过滤）"""
        try:
            query = db.query(BuildLog).filter(BuildLog.build_id == build_id)

            if level:
                query = query.filter(BuildLog.level == level)

            return query.order_by(BuildLog.sequence_number.asc()).offset(skip).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"查询构建日志失败: {e}")
            return []

    def get_logs_by_level(self, db: Session, build_id: int, level: str) -> List[BuildLog]:
        """根据日志级别获取日志"""
        try:
            return db.query(BuildLog).filter(
                BuildLog.build_id == build_id,
                BuildLog.level == level
            ).order_by(BuildLog.timestamp.asc()).all()
        except SQLAlchemyError as e:
            logger.error(f"根据级别查询日志失败: {e}")
            return []

    def batch_create_logs(self, db: Session, logs: List[Dict[str, Any]]) -> List[BuildLog]:
        """批量创建构建日志（性能优化）"""
        try:
            db.bulk_insert_mappings(BuildLog, logs)
            db.flush()
            logger.info(f"批量创建构建日志成功: {len(logs)}条")
            return []
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"批量创建构建日志失败: {e}")
            raise


class GitOperationRepository(BaseRepository):
    """Git操作仓储类"""

    def __init__(self, db_manager: DatabaseManager):
        super().__init__(GitOperation, db_manager)

    def get_project_git_history(self, db: Session, project_id: int, limit: int = 100) -> List[GitOperation]:
        """获取项目的Git操作历史"""
        try:
            return db.query(GitOperation).filter(
                GitOperation.project_id == project_id
            ).order_by(GitOperation.started_at.desc()).limit(limit).all()
        except SQLAlchemyError as e:
            logger.error(f"查询Git操作历史失败: {e}")
            return []

    def get_operations_by_type(self, db: Session, operation_type: str) -> List[GitOperation]:
        """根据操作类型获取Git操作"""
        try:
            return db.query(GitOperation).filter(
                GitOperation.operation_type == operation_type
            ).order_by(GitOperation.started_at.desc()).all()
        except SQLAlchemyError as e:
            logger.error(f"根据类型查询Git操作失败: {e}")
            return []


# ================================
# 数据库服务类
# ================================

class DatabaseService:
    """数据库服务类 - 提供高级数据库操作"""

    def __init__(self, db_manager: DatabaseManager):
        """
        初始化数据库服务

        Args:
            db_manager: 数据库管理器
        """
        self.db_manager = db_manager
        self.projects = ProjectRepository(db_manager)
        self.builds = BuildRepository(db_manager)
        self.build_logs = BuildLogRepository(db_manager)
        self.git_operations = GitOperationRepository(db_manager)

    def get_session(self) -> Session:
        """获取数据库会话"""
        return self.db_manager.get_session()

    @contextmanager
    def transaction(self) -> Generator[Session, None, None]:
        """事务上下文管理器"""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"事务执行失败: {e}")
            raise
        finally:
            session.close()

    def health_check(self) -> Dict[str, Any]:
        """数据库健康检查"""
        try:
            with self.transaction() as session:
                # 检查数据库连接
                session.execute("SELECT 1")

                # 检查表是否存在
                inspector = inspect(session.bind)
                tables = inspector.get_table_names()

                # 统计记录数量
                stats = {}
                for table in ['projects', 'builds', 'build_logs', 'git_operations']:
                    if table in tables:
                        result = session.execute(f"SELECT COUNT(*) FROM {table}")
                        stats[table] = result.scalar()

                return {
                    'status': 'healthy',
                    'connection': 'ok',
                    'tables': tables,
                    'record_counts': stats
                }
        except Exception as e:
            logger.error(f"数据库健康检查失败: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e)
            }


# ================================
# 性能监控装饰器
# ================================

def monitor_query_performance(func):
    """监控查询性能的装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
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
# 全局数据库实例
# ================================

# 创建全局数据库管理器
db_manager = DatabaseManager()

# 创建全局数据库服务
database_service = DatabaseService(db_manager)

# 导出常用函数
def get_db_session() -> Generator[Session, None, None]:
    """获取数据库会话的依赖注入函数（用于FastAPI）"""
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()

def init_database():
    """初始化数据库"""
    db_manager.initialize()

def close_database():
    """关闭数据库连接"""
    db_manager.close()