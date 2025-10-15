# SQLite异步环境最佳实践指南

## 概述

本指南提供SQLite数据库在Python异步环境中的全面最佳实践，包括库选择、性能优化、连接池管理、ORM选择、数据迁移、事务管理等内容。

## 1. SQLite异步访问库对比

### 1.1 主要异步库对比

| 库 | 优势 | 劣势 | 适用场景 | 性能表现 |
|---|---|---|---|---|
| **aiosqlite** | 官方维护、轻量、兼容sqlite3 | 功能相对简单 | 中小型项目、快速原型 | ★★★★☆ |
| **asyncpg+sqlalchemy** | 功能强大、连接池完善 | 重量级、配置复杂 | 大型项目、高并发 | ★★★★★ |
| **sqlite3+threadpool** | 兼容性好、稳定 | 非真正异步 | 现有项目迁移 | ★★★☆☆ |
| **databases+aiosqlite** | 标准化接口、易迁移 | 额外抽象层 | 需要数据库无关性 | ★★★★☆ |

### 1.2 推荐选择方案

```python
# 方案1: aiosqlite (轻量级项目)
import aiosqlite
import asyncio

class AsyncSQLiteManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection = None

    async def connect(self):
        """建立连接并优化配置"""
        self.connection = await aiosqlite.connect(
            self.db_path,
            check_same_thread=False,
            timeout=30.0
        )

        # 性能优化配置
        await self.connection.execute("PRAGMA journal_mode = WAL")
        await self.connection.execute("PRAGMA synchronous = NORMAL")
        await self.connection.execute("PRAGMA cache_size = -64000")
        await self.connection.execute("PRAGMA temp_store = MEMORY")
        await self.connection.execute("PRAGMA mmap_size = 268435456")
        await self.connection.execute("PRAGMA foreign_keys = ON")

    async def execute_query(self, query: str, params=None):
        """执行查询"""
        async with self.connection.execute(query, params or ()) as cursor:
            return await cursor.fetchall()

    async def close(self):
        """关闭连接"""
        if self.connection:
            await self.connection.close()

# 方案2: SQLAlchemy 2.0 async (功能丰富)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import select, text

class AsyncSQLAlchemyManager:
    def __init__(self, db_url: str = "sqlite+aiosqlite:///android_build_tool.db"):
        self.db_url = db_url
        self.engine = None
        self.SessionLocal = None

    async def initialize(self):
        """初始化异步引擎"""
        self.engine = create_async_engine(
            self.db_url,
            echo=False,  # 生产环境关闭
            pool_pre_ping=True,
            connect_args={
                "check_same_thread": False,
                "timeout": 20,
            }
        )

        self.SessionLocal = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        # 设置SQLite优化参数
        async with self.engine.begin() as conn:
            await conn.execute(text("PRAGMA journal_mode = WAL"))
            await conn.execute(text("PRAGMA synchronous = NORMAL"))
            await conn.execute(text("PRAGMA cache_size = -64000"))
            await conn.execute(text("PRAGMA temp_store = MEMORY"))
            await conn.execute(text("PRAGMA mmap_size = 268435456"))

    async def get_session(self) -> AsyncSession:
        """获取异步会话"""
        return self.SessionLocal()

    async def close(self):
        """关闭引擎"""
        if self.engine:
            await self.engine.dispose()
```

### 1.3 性能基准测试

```python
import asyncio
import time
import random
from typing import List, Dict, Any

class DatabasePerformanceBenchmark:
    """数据库性能基准测试"""

    def __init__(self, db_manager):
        self.db_manager = db_manager

    async def benchmark_concurrent_reads(self, concurrency: int = 100, operations: int = 1000):
        """并发读取性能测试"""
        print(f"开始并发读取测试: {concurrency} 并发, {operations} 操作")

        async def read_operation(session_id: int):
            """单个读取操作"""
            start_time = time.time()
            try:
                async with self.db_manager.get_session() as session:
                    # 模拟复杂查询
                    result = await session.execute(text("""
                        SELECT COUNT(*) as count
                        FROM projects
                        WHERE is_active = 1
                    """))
                    count = result.scalar()

                    duration = time.time() - start_time
                    return {"session_id": session_id, "duration": duration, "success": True}
            except Exception as e:
                duration = time.time() - start_time
                return {"session_id": session_id, "duration": duration, "success": False, "error": str(e)}

        # 创建并发任务
        tasks = [read_operation(i) for i in range(operations)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 分析结果
        successful_results = [r for r in results if isinstance(r, dict) and r.get("success")]
        failed_results = [r for r in results if isinstance(r, dict) and not r.get("success")]

        if successful_results:
            durations = [r["duration"] for r in successful_results]
            avg_duration = sum(durations) / len(durations)
            min_duration = min(durations)
            max_duration = max(durations)

            print(f"并发读取测试结果:")
            print(f"  成功操作: {len(successful_results)}/{operations}")
            print(f"  平均耗时: {avg_duration:.3f}s")
            print(f"  最小耗时: {min_duration:.3f}s")
            print(f"  最大耗时: {max_duration:.3f}s")
            print(f"  失败操作: {len(failed_results)}")

        return results

    async def benchmark_concurrent_writes(self, concurrency: int = 50, operations: int = 500):
        """并发写入性能测试"""
        print(f"开始并发写入测试: {concurrency} 并发, {operations} 操作")

        async def write_operation(session_id: int):
            """单个写入操作"""
            start_time = time.time()
            try:
                async with self.db_manager.get_session() as session:
                    # 插入测试数据
                    await session.execute(text("""
                        INSERT INTO system_metrics (metric_name, metric_value, metric_unit, timestamp)
                        VALUES (:name, :value, :unit, datetime('now'))
                    """), {
                        "name": f"test_metric_{session_id}",
                        "value": random.randint(1, 1000),
                        "unit": "count"
                    })
                    await session.commit()

                    duration = time.time() - start_time
                    return {"session_id": session_id, "duration": duration, "success": True}
            except Exception as e:
                duration = time.time() - start_time
                return {"session_id": session_id, "duration": duration, "success": False, "error": str(e)}

        # 创建并发任务
        tasks = [write_operation(i) for i in range(operations)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 分析结果
        successful_results = [r for r in results if isinstance(r, dict) and r.get("success")]
        failed_results = [r for r in results if isinstance(r, dict) and not r.get("success")]

        if successful_results:
            durations = [r["duration"] for r in successful_results]
            avg_duration = sum(durations) / len(durations)
            min_duration = min(durations)
            max_duration = max(durations)

            print(f"并发写入测试结果:")
            print(f"  成功操作: {len(successful_results)}/{operations}")
            print(f"  平均耗时: {avg_duration:.3f}s")
            print(f"  最小耗时: {min_duration:.3f}s")
            print(f"  最大耗时: {max_duration:.3f}s")
            print(f"  失败操作: {len(failed_results)}")

        return results

    async def benchmark_mixed_workload(self, duration_seconds: int = 60):
        """混合工作负载测试"""
        print(f"开始混合工作负载测试，持续 {duration_seconds} 秒")

        end_time = time.time() + duration_seconds
        operation_count = 0
        error_count = 0

        async def mixed_operation():
            nonlocal operation_count, error_count
            operation_id = operation_count

            try:
                async with self.db_manager.get_session() as session:
                    # 随机选择操作类型
                    operation_type = random.choice(["read", "write", "update"])

                    if operation_type == "read":
                        await session.execute(text("SELECT COUNT(*) FROM projects"))
                    elif operation_type == "write":
                        await session.execute(text("""
                            INSERT INTO system_metrics (metric_name, metric_value, metric_unit, timestamp)
                            VALUES (:name, :value, :unit, datetime('now'))
                        """), {
                            "name": f"mixed_test_{operation_id}",
                            "value": random.randint(1, 100),
                            "unit": "test"
                        })
                    else:  # update
                        await session.execute(text("""
                            UPDATE system_metrics
                            SET metric_value = metric_value + 1
                            WHERE metric_name LIKE 'mixed_test_%'
                            LIMIT 1
                        """))

                    await session.commit()
                    operation_count += 1

            except Exception as e:
                error_count += 1
                print(f"操作失败: {e}")

        # 持续运行混合操作
        tasks = []
        while time.time() < end_time:
            task = asyncio.create_task(mixed_operation())
            tasks.append(task)

            # 控制并发数量
            if len(tasks) >= 20:
                completed, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                tasks = list(pending)
                await asyncio.sleep(0.01)  # 短暂休息

        # 等待剩余任务完成
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        throughput = operation_count / duration_seconds
        error_rate = (error_count / (operation_count + error_count)) * 100 if (operation_count + error_count) > 0 else 0

        print(f"混合工作负载测试结果:")
        print(f"  测试时长: {duration_seconds}s")
        print(f"  总操作数: {operation_count}")
        print(f"  错误数: {error_count}")
        print(f"  吞吐量: {throughput:.2f} ops/s")
        print(f"  错误率: {error_rate:.2f}%")
```

## 2. 连接池管理和并发访问策略

### 2.1 连接池配置最佳实践

```python
from sqlalchemy.pool import QueuePool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
import asyncio
import logging

class AsyncConnectionPoolManager:
    """异步连接池管理器"""

    def __init__(self, db_url: str = "sqlite+aiosqlite:///android_build_tool.db"):
        self.db_url = db_url
        self.engine = None
        self.SessionLocal = None
        self.pool_stats = {
            "total_connections": 0,
            "active_connections": 0,
            "idle_connections": 0,
            "checkout_count": 0,
            "checkin_count": 0
        }

    async def initialize(self):
        """初始化连接池"""
        self.engine = create_async_engine(
            self.db_url,
            # 连接池配置
            poolclass=QueuePool,
            pool_size=10,  # 基础连接池大小
            max_overflow=20,  # 最大溢出连接数
            pool_timeout=30,  # 获取连接超时时间
            pool_recycle=3600,  # 连接回收时间(秒)
            pool_pre_ping=True,  # 连接前检查

            # SQLite特定配置
            connect_args={
                "check_same_thread": False,
                "timeout": 20,
                "isolation_level": None,  # 自动提交模式
            },

            # 性能配置
            echo=False,
            future=True
        )

        self.SessionLocal = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False
        )

        # 连接池监控
        self._setup_pool_monitoring()

        # 优化SQLite配置
        await self._optimize_sqlite_settings()

    async def _optimize_sqlite_settings(self):
        """优化SQLite设置"""
        async with self.engine.begin() as conn:
            # 写前日志模式 - 提高并发性能
            await conn.execute(text("PRAGMA journal_mode = WAL"))

            # 同步模式 - 平衡性能和安全性
            await conn.execute(text("PRAGMA synchronous = NORMAL"))

            # 缓存配置
            await conn.execute(text("PRAGMA cache_size = -64000"))  # 64MB

            # 内存映射
            await conn.execute(text("PRAGMA mmap_size = 268435456"))  # 256MB

            # 临时表存储
            await conn.execute(text("PRAGMA temp_store = MEMORY"))

            # 外键约束
            await conn.execute(text("PRAGMA foreign_keys = ON"))

            # WAL检查点设置
            await conn.execute(text("PRAGMA wal_autocheckpoint = 1000"))

    def _setup_pool_monitoring(self):
        """设置连接池监控"""
        @event.listens_for(self.engine.sync_engine, "connect")
        def on_connect(dbapi_connection, connection_record):
            self.pool_stats["total_connections"] += 1
            logging.debug(f"新连接建立，总连接数: {self.pool_stats['total_connections']}")

        @event.listens_for(self.engine.sync_engine, "checkout")
        def on_checkout(dbapi_connection, connection_record, connection_proxy):
            self.pool_stats["checkout_count"] += 1
            self.pool_stats["active_connections"] += 1
            self.pool_stats["idle_connections"] -= 1
            logging.debug(f"连接签出，活跃连接: {self.pool_stats['active_connections']}")

        @event.listens_for(self.engine.sync_engine, "checkin")
        def on_checkin(dbapi_connection, connection_record):
            self.pool_stats["checkin_count"] += 1
            self.pool_stats["active_connections"] -= 1
            self.pool_stats["idle_connections"] += 1
            logging.debug(f"连接归还，活跃连接: {self.pool_stats['active_connections']}")

    async def get_session(self) -> AsyncSession:
        """获取数据库会话"""
        return self.SessionLocal()

    async def execute_with_retry(self, operation, max_retries=3, backoff_factor=0.5):
        """带重试机制的数据库操作"""
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                async with self.get_session() as session:
                    return await operation(session)
            except Exception as e:
                last_exception = e

                if attempt < max_retries:
                    wait_time = backoff_factor * (2 ** attempt)
                    logging.warning(f"数据库操作失败，{wait_time}s后重试 (尝试 {attempt + 1}/{max_retries + 1}): {e}")
                    await asyncio.sleep(wait_time)
                else:
                    logging.error(f"数据库操作最终失败: {e}")
                    raise

        raise last_exception

    async def get_pool_status(self) -> Dict[str, Any]:
        """获取连接池状态"""
        pool = self.engine.pool
        return {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "invalid": pool.invalid(),
            "stats": self.pool_stats.copy()
        }

    async def close(self):
        """关闭连接池"""
        if self.engine:
            await self.engine.dispose()
            logging.info("连接池已关闭")

# 并发访问策略实现
class ConcurrencyController:
    """并发访问控制器"""

    def __init__(self, pool_manager: AsyncConnectionPoolManager):
        self.pool_manager = pool_manager
        self.semaphore = asyncio.Semaphore(50)  # 限制最大并发数
        self.request_queue = asyncio.Queue(maxsize=1000)
        self.active_requests = 0
        self.request_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "avg_response_time": 0.0
        }

    async def execute_with_concurrency_control(self, operation, priority: int = 0):
        """带并发控制的操作执行"""
        # 创建请求对象
        request = {
            "operation": operation,
            "priority": priority,
            "future": asyncio.Future(),
            "created_at": time.time()
        }

        # 将请求加入队列
        await self.request_queue.put(request)

        # 等待结果
        return await request["future"]

    async def _worker(self):
        """工作协程 - 处理队列中的请求"""
        while True:
            try:
                # 获取请求
                request = await self.request_queue.get()

                async with self.semaphore:
                    start_time = time.time()
                    self.active_requests += 1

                    try:
                        # 执行操作
                        result = await self.pool_manager.execute_with_retry(request["operation"])

                        # 更新统计
                        duration = time.time() - start_time
                        self.request_stats["successful_requests"] += 1
                        self._update_avg_response_time(duration)

                        # 设置结果
                        request["future"].set_result(result)

                    except Exception as e:
                        self.request_stats["failed_requests"] += 1
                        request["future"].set_exception(e)

                    finally:
                        self.active_requests -= 1
                        self.request_stats["total_requests"] += 1

                    self.request_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"工作协程错误: {e}")

    def _update_avg_response_time(self, duration: float):
        """更新平均响应时间"""
        current_avg = self.request_stats["avg_response_time"]
        total_successful = self.request_stats["successful_requests"]

        if total_successful == 1:
            self.request_stats["avg_response_time"] = duration
        else:
            self.request_stats["avg_response_time"] = (
                (current_avg * (total_successful - 1) + duration) / total_successful
            )

    async def start_workers(self, worker_count: int = 5):
        """启动工作协程"""
        for i in range(worker_count):
            asyncio.create_task(self._worker())
        logging.info(f"启动了 {worker_count} 个工作协程")

    async def get_status(self) -> Dict[str, Any]:
        """获取控制器状态"""
        return {
            "active_requests": self.active_requests,
            "queue_size": self.request_queue.qsize(),
            "semaphore_available": self.semaphore._value,
            "request_stats": self.request_stats.copy()
        }
```

## 3. 异步ORM选择和配置

### 3.1 SQLAlchemy 2.0 async 配置

```python
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, Text, Boolean, JSON, select, update, delete
from sqlalchemy.sql import func
from typing import Optional, List, Dict, Any
from datetime import datetime
import asyncio

# 异步模型基类
class Base(AsyncAttrs, DeclarativeBase):
    """异步ORM基类"""

    # 通用字段
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

# 异步项目模型
class AsyncProject(Base):
    """异步项目模型"""
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    project_type: Mapped[str] = mapped_column(String(50), nullable=False)
    repository_url: Mapped[str] = mapped_column(String(500), nullable=False)
    local_path: Mapped[str] = mapped_column(String(500), nullable=False)
    branch: Mapped[str] = mapped_column(String(100), default="main")

    # 构建配置
    build_command: Mapped[Optional[str]] = mapped_column(String(1000))
    environment_vars: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    build_timeout: Mapped[int] = mapped_column(Integer, default=1800)

    # 状态
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    tags: Mapped[Optional[List[str]]] = mapped_column(JSON)

    # 关系
    builds: Mapped[List["AsyncBuild"]] = relationship("AsyncBuild", back_populates="project", cascade="all, delete-orphan")

    # 索引
    __table_args__ = (
        Index('idx_project_name_type', 'name', 'project_type'),
        Index('idx_project_active_created', 'is_active', 'created_at'),
    )

# 异步构建模型
class AsyncBuild(Base):
    """异步构建模型"""
    __tablename__ = "builds"

    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False)
    build_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)

    # 时间信息
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)

    # 构建信息
    commit_hash: Mapped[Optional[str]] = mapped_column(String(40), index=True)
    branch: Mapped[Optional[str]] = mapped_column(String(100))
    build_type: Mapped[Optional[str]] = mapped_column(String(50))
    triggered_by: Mapped[Optional[str]] = mapped_column(String(100))

    # 结果数据
    exit_code: Mapped[Optional[int]] = mapped_column(Integer)
    artifact_path: Mapped[Optional[str]] = mapped_column(String(500))
    artifact_size: Mapped[Optional[int]] = mapped_column(Integer)

    # 性能指标
    memory_usage_mb: Mapped[Optional[int]] = mapped_column(Integer)
    cpu_usage_percent: Mapped[Optional[int]] = mapped_column(Integer)

    # 元数据
    build_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)

    # 关系
    project: Mapped["AsyncProject"] = relationship("AsyncProject", back_populates="builds")
    logs: Mapped[List["AsyncBuildLog"]] = relationship("AsyncBuildLog", back_populates="build", cascade="all, delete-orphan")

    # 索引
    __table_args__ = (
        Index('idx_build_project_status', 'project_id', 'status'),
        Index('idx_build_started_status', 'started_at', 'status'),
        UniqueConstraint('project_id', 'build_number', name='uq_project_build_number'),
    )

# 异步构建日志模型
class AsyncBuildLog(Base):
    """异步构建日志模型"""
    __tablename__ = "build_logs"

    build_id: Mapped[int] = mapped_column(Integer, ForeignKey("builds.id"), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)
    message: Mapped[str] = mapped_column(Text)
    source: Mapped[Optional[str]] = mapped_column(String(100))

    # 关系
    build: Mapped["AsyncBuild"] = relationship("AsyncBuild", back_populates="logs")

    # 索引
    __table_args__ = (
        Index('idx_log_build_sequence', 'build_id', 'sequence_number'),
        Index('idx_log_level_timestamp', 'level', 'timestamp'),
        UniqueConstraint('build_id', 'sequence_number', name='uq_build_log_sequence'),
    )

# 异步仓储层
class AsyncRepository:
    """异步仓储基类"""

    def __init__(self, model_class, session_factory):
        self.model_class = model_class
        self.session_factory = session_factory

    async def create(self, **kwargs) -> Base:
        """创建记录"""
        async with self.session_factory() as session:
            instance = self.model_class(**kwargs)
            session.add(instance)
            await session.commit()
            await session.refresh(instance)
            return instance

    async def get_by_id(self, id: int) -> Optional[Base]:
        """根据ID获取记录"""
        async with self.session_factory() as session:
            result = await session.execute(select(self.model_class).where(self.model_class.id == id))
            return result.scalar_one_or_none()

    async def get_all(self, limit: int = 100, offset: int = 0, **filters) -> List[Base]:
        """获取所有记录"""
        async with self.session_factory() as session:
            query = select(self.model_class)

            # 应用过滤条件
            for key, value in filters.items():
                if hasattr(self.model_class, key):
                    query = query.where(getattr(self.model_class, key) == value)

            query = query.offset(offset).limit(limit)
            result = await session.execute(query)
            return result.scalars().all()

    async def update(self, id: int, **kwargs) -> Optional[Base]:
        """更新记录"""
        async with self.session_factory() as session:
            # 获取现有记录
            result = await session.execute(select(self.model_class).where(self.model_class.id == id))
            instance = result.scalar_one_or_none()

            if instance:
                # 更新字段
                for key, value in kwargs.items():
                    if hasattr(instance, key):
                        setattr(instance, key, value)

                await session.commit()
                await session.refresh(instance)

            return instance

    async def delete(self, id: int) -> bool:
        """删除记录"""
        async with self.session_factory() as session:
            result = await session.execute(select(self.model_class).where(self.model_class.id == id))
            instance = result.scalar_one_or_none()

            if instance:
                await session.delete(instance)
                await session.commit()
                return True

            return False

    async def count(self, **filters) -> int:
        """统计记录数量"""
        async with self.session_factory() as session:
            query = select(func.count(self.model_class.id))

            for key, value in filters.items():
                if hasattr(self.model_class, key):
                    query = query.where(getattr(self.model_class, key) == value)

            result = await session.execute(query)
            return result.scalar()

# 项目专用仓储
class AsyncProjectRepository(AsyncRepository):
    """项目异步仓储"""

    def __init__(self, session_factory):
        super().__init__(AsyncProject, session_factory)

    async def get_by_name(self, name: str) -> Optional[AsyncProject]:
        """根据名称获取项目"""
        async with self.session_factory() as session:
            result = await session.execute(
                select(AsyncProject).where(AsyncProject.name == name)
            )
            return result.scalar_one_or_none()

    async def get_active_projects(self) -> List[AsyncProject]:
        """获取活跃项目"""
        async with self.session_factory() as session:
            result = await session.execute(
                select(AsyncProject).where(AsyncProject.is_active == True)
                .order_by(AsyncProject.created_at.desc())
            )
            return result.scalars().all()

    async def search_projects(self, keyword: str) -> List[AsyncProject]:
        """搜索项目"""
        async with self.session_factory() as session:
            result = await session.execute(
                select(AsyncProject).where(
                    (AsyncProject.name.contains(keyword)) |
                    (AsyncProject.description.contains(keyword))
                )
            )
            return result.scalars().all()

    async def get_projects_with_build_stats(self) -> List[Dict[str, Any]]:
        """获取项目及其构建统计"""
        async with self.session_factory() as session:
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

# 构建专用仓储
class AsyncBuildRepository(AsyncRepository):
    """构建异步仓储"""

    def __init__(self, session_factory):
        super().__init__(AsyncBuild, session_factory)

    async def get_project_builds(self, project_id: int, limit: int = 50) -> List[AsyncBuild]:
        """获取项目构建历史"""
        async with self.session_factory() as session:
            result = await session.execute(
                select(AsyncBuild)
                .where(AsyncBuild.project_id == project_id)
                .order_by(AsyncBuild.build_number.desc())
                .limit(limit)
            )
            return result.scalars().all()

    async def get_running_builds(self) -> List[AsyncBuild]:
        """获取运行中的构建"""
        async with self.session_factory() as session:
            result = await session.execute(
                select(AsyncBuild)
                .where(AsyncBuild.status == 'running')
                .order_by(AsyncBuild.started_at.asc())
            )
            return result.scalars().all()

    async def update_build_status(self, build_id: int, status: str, **kwargs) -> bool:
        """更新构建状态"""
        async with self.session_factory() as session:
            update_data = {"status": status, **kwargs}

            if status in ["success", "failed", "cancelled"]:
                update_data["completed_at"] = func.now()

            result = await session.execute(
                update(AsyncBuild)
                .where(AsyncBuild.id == build_id)
                .values(**update_data)
            )

            await session.commit()
            return result.rowcount > 0

    async def get_build_statistics(self, project_id: Optional[int] = None, days: int = 30) -> Dict[str, Any]:
        """获取构建统计"""
        async with self.session_factory() as session:
            # 基础查询
            base_query = select(AsyncBuild).where(
                AsyncBuild.started_at >= func.datetime('now', f'-{days} days')
            )

            if project_id:
                base_query = base_query.where(AsyncBuild.project_id == project_id)

            # 执行查询获取统计
            result = await session.execute(text(f"""
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
            """))

            stats = dict(result.first())

            # 计算成功率
            if stats["total_builds"] > 0:
                stats["success_rate"] = (stats["successful_builds"] / stats["total_builds"]) * 100
            else:
                stats["success_rate"] = 0

            return stats

# 异步ORM服务
class AsyncORMService:
    """异步ORM服务"""

    def __init__(self, db_url: str = "sqlite+aiosqlite:///android_build_tool.db"):
        self.db_url = db_url
        self.engine = None
        self.session_factory = None

        # 仓储实例
        self.projects = None
        self.builds = None
        self.build_logs = None

    async def initialize(self):
        """初始化ORM服务"""
        self.engine = create_async_engine(
            self.db_url,
            echo=False,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False}
        )

        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        # 创建所有表
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # 初始化仓储
        self.projects = AsyncProjectRepository(self.session_factory)
        self.builds = AsyncBuildRepository(self.session_factory)
        self.build_logs = AsyncRepository(AsyncBuildLog, self.session_factory)

    async def close(self):
        """关闭ORM服务"""
        if self.engine:
            await self.engine.dispose()
```

## 4. 数据迁移和版本控制

### 4.1 异步迁移管理器

```python
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

class AsyncMigration:
    """异步迁移类"""

    def __init__(
        self,
        version: int,
        description: str,
        up_sql: str,
        down_sql: str,
        dependencies: Optional[List[int]] = None,
        timeout: int = 300
    ):
        self.version = version
        self.description = description
        self.up_sql = up_sql.strip()
        self.down_sql = down_sql.strip()
        self.dependencies = dependencies or []
        self.timeout = timeout
        self.created_at = datetime.utcnow()

    async def execute_up(self, session: AsyncSession) -> Tuple[bool, str]:
        """执行升级迁移"""
        try:
            start_time = datetime.utcnow()

            # 执行升级SQL
            if self.up_sql:
                # 分割SQL语句并逐个执行
                statements = [stmt.strip() for stmt in self.up_sql.split(';') if stmt.strip()]
                for statement in statements:
                    if statement:
                        await session.execute(text(statement))
                        await asyncio.sleep(0.01)  # 给其他协程执行机会

            # 记录迁移历史
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            await session.execute(text("""
                INSERT INTO migration_history
                (version, description, applied_at, execution_time_ms, success)
                VALUES (:version, :description, :applied_at, :execution_time_ms, TRUE)
            """), {
                'version': self.version,
                'description': self.description,
                'applied_at': start_time,
                'execution_time_ms': execution_time
            })

            await session.commit()
            return True, f"迁移 {self.version} 执行成功"

        except Exception as e:
            await session.rollback()
            return False, f"迁移 {self.version} 执行失败: {str(e)}"

    async def execute_down(self, session: AsyncSession) -> Tuple[bool, str]:
        """执行降级迁移"""
        try:
            start_time = datetime.utcnow()

            # 执行降级SQL
            if self.down_sql:
                statements = [stmt.strip() for stmt in self.down_sql.split(';') if stmt.strip()]
                for statement in statements:
                    if statement:
                        await session.execute(text(statement))
                        await asyncio.sleep(0.01)

            # 删除迁移历史记录
            await session.execute(
                text("DELETE FROM migration_history WHERE version = :version"),
                {'version': self.version}
            )

            await session.commit()
            return True, f"迁移 {self.version} 回滚成功"

        except Exception as e:
            await session.rollback()
            return False, f"迁移 {self.version} 回滚失败: {str(e)}"

class AsyncMigrationManager:
    """异步迁移管理器"""

    def __init__(self, session_factory, migrations_dir: str = "migrations"):
        self.session_factory = session_factory
        self.migrations_dir = Path(migrations_dir)
        self.migrations_dir.mkdir(exist_ok=True)
        self.migrations: Dict[int, AsyncMigration] = {}
        self._lock = asyncio.Lock()

    async def initialize(self):
        """初始化迁移管理器"""
        await self._create_migration_table()
        await self._load_migrations()

    async def _create_migration_table(self):
        """创建迁移历史表"""
        async with self.session_factory() as session:
            await session.execute(text("""
                CREATE TABLE IF NOT EXISTS migration_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version INTEGER NOT NULL UNIQUE,
                    description TEXT NOT NULL,
                    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    execution_time_ms INTEGER,
                    success BOOLEAN DEFAULT TRUE,
                    error_message TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_migration_version ON migration_history(version);
                CREATE INDEX IF NOT EXISTS idx_migration_applied ON migration_history(applied_at);
            """))
            await session.commit()

    async def _load_migrations(self):
        """加载迁移文件"""
        self.migrations.clear()

        # 加载内置迁移
        await self._register_builtin_migrations()

        # 加载文件系统迁移
        for migration_file in self.migrations_dir.glob("*.json"):
            try:
                with open(migration_file, 'r', encoding='utf-8') as f:
                    migration_data = json.load(f)
                    migration = AsyncMigration(**migration_data)
                    self.migrations[migration.version] = migration
                    logging.debug(f"加载迁移文件: {migration_file.name}")
            except Exception as e:
                logging.error(f"加载迁移文件失败 {migration_file}: {e}")

        logging.info(f"加载了 {len(self.migrations)} 个迁移")

    async def _register_builtin_migrations(self):
        """注册内置迁移"""

        # 版本1: 初始数据库schema
        migration_v1 = AsyncMigration(
            version=1,
            description="初始数据库schema创建",
            up_sql="""
                -- 创建项目表
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    project_type VARCHAR(50) NOT NULL,
                    repository_url VARCHAR(500) NOT NULL,
                    local_path VARCHAR(500) NOT NULL,
                    branch VARCHAR(100) DEFAULT 'main',
                    build_command VARCHAR(1000),
                    environment_vars JSON,
                    build_timeout INTEGER DEFAULT 1800,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    tags JSON
                );

                -- 创建构建表
                CREATE TABLE IF NOT EXISTS builds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    build_number INTEGER NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    started_at DATETIME,
                    completed_at DATETIME,
                    duration_seconds INTEGER,
                    commit_hash VARCHAR(40),
                    branch VARCHAR(100),
                    build_type VARCHAR(50),
                    triggered_by VARCHAR(100),
                    exit_code INTEGER,
                    artifact_path VARCHAR(500),
                    artifact_size INTEGER,
                    memory_usage_mb INTEGER,
                    cpu_usage_percent INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    build_metadata JSON,
                    FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
                );

                -- 创建索引
                CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name);
                CREATE INDEX IF NOT EXISTS idx_projects_type ON projects(project_type);
                CREATE INDEX IF NOT EXISTS idx_projects_active ON projects(is_active);
                CREATE INDEX IF NOT EXISTS idx_builds_project ON builds(project_id);
                CREATE INDEX IF NOT EXISTS idx_builds_status ON builds(status);
                CREATE INDEX IF NOT EXISTS idx_builds_started ON builds(started_at);
            """,
            down_sql="""
                DROP TABLE IF EXISTS builds;
                DROP TABLE IF EXISTS projects;
            """
        )
        self.migrations[1] = migration_v1

        # 版本2: 添加构建日志表
        migration_v2 = AsyncMigration(
            version=2,
            description="添加构建日志表",
            up_sql="""
                CREATE TABLE IF NOT EXISTS build_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    build_id INTEGER NOT NULL,
                    sequence_number INTEGER NOT NULL,
                    level VARCHAR(20),
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    message TEXT NOT NULL,
                    source VARCHAR(100),
                    FOREIGN KEY (build_id) REFERENCES builds (id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_build_logs_build ON build_logs(build_id);
                CREATE INDEX IF NOT EXISTS idx_build_logs_sequence ON build_logs(build_id, sequence_number);
                CREATE INDEX IF NOT EXISTS idx_build_logs_level ON build_logs(level);
                CREATE INDEX IF NOT EXISTS idx_build_logs_timestamp ON build_logs(timestamp);
            """,
            down_sql="""
                DROP TABLE IF EXISTS build_logs;
            """,
            dependencies=[1]
        )
        self.migrations[2] = migration_v2

        # 版本3: 添加性能优化
        migration_v3 = AsyncMigration(
            version=3,
            description="添加性能优化索引和视图",
            up_sql="""
                -- 添加复合索引
                CREATE INDEX IF NOT EXISTS idx_builds_project_status ON builds(project_id, status);
                CREATE INDEX IF NOT EXISTS idx_builds_status_started ON builds(status, started_at DESC);
                CREATE INDEX IF NOT EXISTS idx_projects_name_type ON projects(name, project_type);

                -- 添加性能统计视图
                CREATE VIEW IF NOT EXISTS build_performance_stats AS
                SELECT
                    p.id as project_id,
                    p.name as project_name,
                    COUNT(b.id) as total_builds,
                    COUNT(CASE WHEN b.status = 'success' THEN 1 END) as successful_builds,
                    AVG(b.duration_seconds) as avg_duration,
                    MAX(b.started_at) as last_build_at
                FROM projects p
                LEFT JOIN builds b ON p.id = b.project_id
                GROUP BY p.id, p.name;
            """,
            down_sql="""
                DROP VIEW IF EXISTS build_performance_stats;
                DROP INDEX IF EXISTS idx_projects_name_type;
                DROP INDEX IF EXISTS idx_builds_status_started;
                DROP INDEX IF EXISTS idx_builds_project_status;
            """,
            dependencies=[2]
        )
        self.migrations[3] = migration_v3

    async def get_current_version(self) -> int:
        """获取当前数据库版本"""
        async with self.session_factory() as session:
            result = await session.execute(
                text("SELECT MAX(version) FROM migration_history WHERE success = TRUE")
            )
            current_version = result.scalar() or 0
            return current_version

    async def get_pending_migrations(self) -> List[AsyncMigration]:
        """获取待执行的迁移"""
        async with self._lock:
            current_version = await self.get_current_version()
            pending = []

            for version, migration in sorted(self.migrations.items()):
                if version > current_version:
                    # 检查依赖
                    dependencies_met = all(
                        dep <= current_version for dep in migration.dependencies
                    )
                    if dependencies_met:
                        pending.append(migration)

            return pending

    async def migrate_up(self, target_version: Optional[int] = None) -> Tuple[bool, str]:
        """执行升级迁移"""
        async with self._lock:
            current_version = await self.get_current_version()
            pending_migrations = await self.get_pending_migrations()

            if not pending_migrations:
                return True, "没有待执行的迁移"

            # 过滤到目标版本
            if target_version is not None:
                pending_migrations = [m for m in pending_migrations if m.version <= target_version]

            if not pending_migrations:
                return True, f"已经是目标版本 {target_version}"

            logging.info(f"开始执行 {len(pending_migrations)} 个迁移，当前版本: {current_version}")

            for migration in pending_migrations:
                async with self.session_factory() as session:
                    success, message = await migration.execute_up(session)

                    if not success:
                        return False, f"迁移 {migration.version} 失败: {message}"

                    logging.info(f"迁移 {migration.version} 完成: {migration.description}")

            final_version = await self.get_current_version()
            logging.info(f"迁移完成，最终版本: {final_version}")
            return True, f"迁移完成，最终版本: {final_version}"

    async def migrate_down(self, target_version: int) -> Tuple[bool, str]:
        """执行降级迁移"""
        async with self._lock:
            current_version = await self.get_current_version()

            if target_version >= current_version:
                return False, f"目标版本 {target_version} 大于等于当前版本 {current_version}"

            # 获取需要回滚的迁移
            migrations_to_rollback = []
            for version in sorted(self.migrations.keys(), reverse=True):
                if target_version < version <= current_version:
                    migrations_to_rollback.append(self.migrations[version])

            if not migrations_to_rollback:
                return True, f"已经是目标版本 {target_version}"

            logging.info(f"开始回滚到版本 {target_version}，需要回滚 {len(migrations_to_rollback)} 个迁移")

            for migration in migrations_to_rollback:
                async with self.session_factory() as session:
                    success, message = await migration.execute_down(session)

                    if not success:
                        return False, f"回滚迁移 {migration.version} 失败: {message}"

                    logging.info(f"回滚迁移 {migration.version} 完成: {migration.description}")

            logging.info(f"回滚完成，当前版本: {target_version}")
            return True, f"回滚完成，当前版本: {target_version}"

    async def get_migration_history(self) -> List[Dict[str, Any]]:
        """获取迁移历史"""
        async with self.session_factory() as session:
            result = await session.execute(text("""
                SELECT version, description, applied_at, execution_time_ms, success, error_message
                FROM migration_history
                ORDER BY version DESC
            """))
            return [dict(row) for row in result]

    async def validate_migrations(self) -> Tuple[bool, List[str]]:
        """验证迁移完整性"""
        errors = []

        # 检查版本连续性
        versions = sorted(self.migrations.keys())
        for i in range(1, len(versions)):
            if versions[i] != versions[i-1] + 1:
                errors.append(f"版本不连续: {versions[i-1]} -> {versions[i]}")

        # 检查依赖关系
        for version, migration in self.migrations.items():
            for dep in migration.dependencies:
                if dep not in self.migrations:
                    errors.append(f"迁移 {version} 依赖不存在的版本 {dep}")

        # 检查当前数据库状态
        current_version = await self.get_current_version()
        applied_versions = set()

        try:
            async with self.session_factory() as session:
                result = await session.execute(
                    text("SELECT version FROM migration_history WHERE success = TRUE")
                )
                applied_versions = {row[0] for row in result}
        except Exception as e:
            errors.append(f"无法获取已应用的迁移版本: {e}")

        # 检查是否有未应用的迁移
        for version in range(1, current_version + 1):
            if version not in applied_versions:
                errors.append(f"版本 {version} 在数据库中缺失")

        return len(errors) == 0, errors
```

## 5. 事务管理和并发控制

### 5.1 异步事务管理器

```python
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Callable, Optional, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import text
from datetime import datetime, timedelta
import uuid

class AsyncTransactionManager:
    """异步事务管理器"""

    def __init__(self, session_factory: async_sessionmaker):
        self.session_factory = session_factory
        self.active_transactions: Dict[str, Dict[str, Any]] = {}
        self.transaction_stats = {
            "total_transactions": 0,
            "successful_transactions": 0,
            "failed_transactions": 0,
            "avg_duration": 0.0,
            "concurrent_transactions": 0
        }

    @asynccontextmanager
    async def transaction(self, isolation_level: Optional[str] = None, timeout: int = 300):
        """事务上下文管理器"""
        transaction_id = str(uuid.uuid4())
        start_time = datetime.utcnow()

        try:
            async with self.session_factory() as session:
                # 设置隔离级别
                if isolation_level:
                    await session.execute(text(f"SET TRANSACTION ISOLATION LEVEL {isolation_level}"))

                # 记录事务开始
                self.active_transactions[transaction_id] = {
                    "session": session,
                    "start_time": start_time,
                    "isolation_level": isolation_level,
                    "status": "active"
                }
                self.transaction_stats["concurrent_transactions"] += 1

                try:
                    yield session

                    # 提交事务
                    await session.commit()

                    # 更新统计
                    duration = (datetime.utcnow() - start_time).total_seconds()
                    self._update_transaction_stats(duration, success=True)

                    logging.debug(f"事务 {transaction_id} 提交成功，耗时 {duration:.3f}s")

                except Exception as e:
                    # 回滚事务
                    await session.rollback()

                    # 更新统计
                    duration = (datetime.utcnow() - start_time).total_seconds()
                    self._update_transaction_stats(duration, success=False)

                    logging.error(f"事务 {transaction_id} 回滚，错误: {e}")
                    raise

                finally:
                    # 清理事务记录
                    self.active_transactions.pop(transaction_id, None)
                    self.transaction_stats["concurrent_transactions"] -= 1

        except Exception as e:
            logging.error(f"事务 {transaction_id} 创建失败: {e}")
            raise

    async def execute_in_transaction(
        self,
        operation: Callable[[AsyncSession], Any],
        isolation_level: Optional[str] = None,
        timeout: int = 300,
        max_retries: int = 3
    ) -> Any:
        """在事务中执行操作"""
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                async with self.transaction(isolation_level, timeout) as session:
                    return await operation(session)

            except Exception as e:
                last_exception = e

                if attempt < max_retries:
                    wait_time = 0.5 * (2 ** attempt)  # 指数退避
                    logging.warning(f"事务操作失败，{wait_time}s后重试 (尝试 {attempt + 1}/{max_retries + 1}): {e}")
                    await asyncio.sleep(wait_time)
                else:
                    logging.error(f"事务操作最终失败: {e}")
                    break

        raise last_exception

    async def execute_batch_operations(
        self,
        operations: List[Callable[[AsyncSession], Any]],
        batch_size: int = 100,
        isolation_level: Optional[str] = None
    ) -> List[Any]:
        """批量执行操作"""
        results = []
        total_operations = len(operations)

        logging.info(f"开始批量执行 {total_operations} 个操作，批次大小: {batch_size}")

        for i in range(0, total_operations, batch_size):
            batch = operations[i:i + batch_size]
            batch_start_time = datetime.utcnow()

            try:
                async with self.transaction(isolation_level) as session:
                    batch_results = []
                    for operation in batch:
                        result = await operation(session)
                        batch_results.append(result)

                    results.extend(batch_results)

                    batch_duration = (datetime.utcnow() - batch_start_time).total_seconds()
                    logging.debug(f"批次 {i//batch_size + 1} 完成，耗时 {batch_duration:.3f}s")

            except Exception as e:
                logging.error(f"批次 {i//batch_size + 1} 执行失败: {e}")
                # 可以选择继续下一批次或中断
                break

        logging.info(f"批量执行完成，成功执行 {len(results)}/{total_operations} 个操作")
        return results

    def _update_transaction_stats(self, duration: float, success: bool):
        """更新事务统计"""
        self.transaction_stats["total_transactions"] += 1

        if success:
            self.transaction_stats["successful_transactions"] += 1
        else:
            self.transaction_stats["failed_transactions"] += 1

        # 更新平均耗时
        total = self.transaction_stats["total_transactions"]
        current_avg = self.transaction_stats["avg_duration"]
        self.transaction_stats["avg_duration"] = (current_avg * (total - 1) + duration) / total

    async def get_transaction_status(self) -> Dict[str, Any]:
        """获取事务状态"""
        return {
            "active_transactions": len(self.active_transactions),
            "concurrent_transactions": self.transaction_stats["concurrent_transactions"],
            "stats": self.transaction_stats.copy(),
            "transaction_details": {
                tid: {
                    "start_time": info["start_time"].isoformat(),
                    "duration": (datetime.utcnow() - info["start_time"]).total_seconds(),
                    "isolation_level": info["isolation_level"],
                    "status": info["status"]
                }
                for tid, info in self.active_transactions.items()
            }
        }

    async def cleanup_expired_transactions(self, max_duration: int = 3600):
        """清理过期事务"""
        current_time = datetime.utcnow()
        expired_transactions = []

        for tid, info in self.active_transactions.items():
            duration = (current_time - info["start_time"]).total_seconds()
            if duration > max_duration:
                expired_transactions.append(tid)

        for tid in expired_transactions:
            info = self.active_transactions.pop(tid, None)
            if info:
                try:
                    # 尝试回滚过期事务
                    await info["session"].rollback()
                    logging.warning(f"清理过期事务: {tid}")
                except Exception as e:
                    logging.error(f"清理过期事务失败 {tid}: {e}")

# 并发控制锁管理器
class AsyncLockManager:
    """异步锁管理器"""

    def __init__(self):
        self.locks: Dict[str, asyncio.Lock] = {}
        self.semaphores: Dict[str, asyncio.Semaphore] = {}
        self.lock_stats = {
            "total_locks_created": 0,
            "active_locks": 0,
            "lock_acquisitions": 0,
            "lock_timeouts": 0
        }

    def get_lock(self, resource_id: str) -> asyncio.Lock:
        """获取或创建锁"""
        if resource_id not in self.locks:
            self.locks[resource_id] = asyncio.Lock()
            self.lock_stats["total_locks_created"] += 1

        return self.locks[resource_id]

    def get_semaphore(self, resource_id: str, max_concurrent: int) -> asyncio.Semaphore:
        """获取或创建信号量"""
        key = f"{resource_id}:{max_concurrent}"
        if key not in self.semaphores:
            self.semaphores[key] = asyncio.Semaphore(max_concurrent)

        return self.semaphores[key]

    @asynccontextmanager
    async def acquire_lock(self, resource_id: str, timeout: float = 30.0):
        """获取锁的上下文管理器"""
        lock = self.get_lock(resource_id)

        try:
            # 尝试获取锁
            await asyncio.wait_for(lock.acquire(), timeout=timeout)
            self.lock_stats["lock_acquisitions"] += 1
            self.lock_stats["active_locks"] += 1

            yield

        except asyncio.TimeoutError:
            self.lock_stats["lock_timeouts"] += 1
            raise TimeoutError(f"获取锁超时: {resource_id}")

        finally:
            lock.release()
            self.lock_stats["active_locks"] -= 1

    @asynccontextmanager
    async def acquire_semaphore(self, resource_id: str, max_concurrent: int, timeout: float = 30.0):
        """获取信号量的上下文管理器"""
        semaphore = self.get_semaphore(resource_id, max_concurrent)

        try:
            await asyncio.wait_for(semaphore.acquire(), timeout=timeout)
            yield

        except asyncio.TimeoutError:
            raise TimeoutError(f"获取信号量超时: {resource_id}")

        finally:
            semaphore.release()

    def get_lock_stats(self) -> Dict[str, Any]:
        """获取锁统计信息"""
        return {
            **self.lock_stats,
            "total_locks": len(self.locks),
            "total_semaphores": len(self.semaphores),
            "active_locks": self.lock_stats["active_locks"]
        }

# 分布式锁管理器 (基于数据库)
class AsyncDistributedLockManager:
    """基于数据库的分布式锁管理器"""

    def __init__(self, session_factory: async_sessionmaker, lock_timeout: int = 300):
        self.session_factory = session_factory
        self.lock_timeout = lock_timeout
        self.local_locks: Dict[str, asyncio.Lock] = {}

    async def _create_lock_table(self):
        """创建锁表"""
        async with self.session_factory() as session:
            await session.execute(text("""
                CREATE TABLE IF NOT EXISTS distributed_locks (
                    resource_id VARCHAR(255) PRIMARY KEY,
                    lock_holder VARCHAR(255) NOT NULL,
                    acquired_at DATETIME NOT NULL,
                    expires_at DATETIME NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_locks_expires_at ON distributed_locks(expires_at);
            """))
            await session.commit()

    @asynccontextmanager
    async def acquire_distributed_lock(self, resource_id: str, holder_id: str, timeout: float = 30.0):
        """获取分布式锁"""
        await self._create_lock_table()

        # 本地锁优化
        if resource_id not in self.local_locks:
            self.local_locks[resource_id] = asyncio.Lock()

        async with self.local_locks[resource_id]:
            # 清理过期锁
            await self._cleanup_expired_locks()

            # 尝试获取分布式锁
            start_time = datetime.utcnow()
            while (datetime.utcnow() - start_time).total_seconds() < timeout:
                if await self._try_acquire_lock(resource_id, holder_id):
                    try:
                        yield
                        return
                    finally:
                        await self._release_lock(resource_id, holder_id)

                # 等待一段时间后重试
                await asyncio.sleep(0.1)

            raise TimeoutError(f"获取分布式锁超时: {resource_id}")

    async def _try_acquire_lock(self, resource_id: str, holder_id: str) -> bool:
        """尝试获取锁"""
        async with self.session_factory() as session:
            now = datetime.utcnow()
            expires_at = now + timedelta(seconds=self.lock_timeout)

            try:
                # 尝试插入锁记录
                await session.execute(text("""
                    INSERT INTO distributed_locks (resource_id, lock_holder, acquired_at, expires_at)
                    VALUES (:resource_id, :holder_id, :acquired_at, :expires_at)
                """), {
                    'resource_id': resource_id,
                    'holder_id': holder_id,
                    'acquired_at': now,
                    'expires_at': expires_at
                })

                await session.commit()
                return True

            except Exception:
                # 锁已存在，检查是否过期
                result = await session.execute(text("""
                    SELECT lock_holder, expires_at FROM distributed_locks
                    WHERE resource_id = :resource_id
                """), {'resource_id': resource_id})

                row = result.first()
                if row and row.expires_at < datetime.utcnow():
                    # 锁已过期，尝试删除并重新获取
                    await session.execute(text("""
                        DELETE FROM distributed_locks WHERE resource_id = :resource_id
                    """), {'resource_id': resource_id})

                    await session.commit()

                    # 重新尝试获取
                    return await self._try_acquire_lock(resource_id, holder_id)

                return False

    async def _release_lock(self, resource_id: str, holder_id: str):
        """释放锁"""
        async with self.session_factory() as session:
            await session.execute(text("""
                DELETE FROM distributed_locks
                WHERE resource_id = :resource_id AND lock_holder = :holder_id
            """), {
                'resource_id': resource_id,
                'holder_id': holder_id
            })
            await session.commit()

    async def _cleanup_expired_locks(self):
        """清理过期锁"""
        async with self.session_factory() as session:
            await session.execute(text("""
                DELETE FROM distributed_locks WHERE expires_at < datetime('now')
            """))
            await session.commit()

    async def get_lock_info(self, resource_id: str) -> Optional[Dict[str, Any]]:
        """获取锁信息"""
        async with self.session_factory() as session:
            result = await session.execute(text("""
                SELECT lock_holder, acquired_at, expires_at FROM distributed_locks
                WHERE resource_id = :resource_id
            """), {'resource_id': resource_id})

            row = result.first()
            if row:
                return {
                    'resource_id': resource_id,
                    'lock_holder': row.lock_holder,
                    'acquired_at': row.acquired_at.isoformat(),
                    'expires_at': row.expires_at.isoformat(),
                    'is_expired': row.expires_at < datetime.utcnow()
                }

            return None
```

## 6. 性能优化建议

### 6.1 SQLite异步性能优化配置

```python
class AsyncSQLitePerformanceOptimizer:
    """SQLite异步性能优化器"""

    def __init__(self, engine):
        self.engine = engine

    async def apply_optimizations(self):
        """应用性能优化配置"""
        async with self.engine.begin() as conn:
            # 1. 写前日志模式 (WAL) - 提高并发性能
            await conn.execute(text("PRAGMA journal_mode = WAL"))

            # 2. 同步模式 - 平衡性能和安全性
            await conn.execute(text("PRAGMA synchronous = NORMAL"))

            # 3. 缓存配置 - 增加缓存大小
            await conn.execute(text("PRAGMA cache_size = -64000"))  # 64MB

            # 4. 内存映射 - 大文件访问优化
            await conn.execute(text("PRAGMA mmap_size = 268435456"))  # 256MB

            # 5. 临时表存储在内存中
            await conn.execute(text("PRAGMA temp_store = MEMORY"))

            # 6. 启用外键约束
            await conn.execute(text("PRAGMA foreign_keys = ON"))

            # 7. WAL自动检查点设置
            await conn.execute(text("PRAGMA wal_autocheckpoint = 1000"))

            # 8. 查询优化器设置
            await conn.execute(text("PRAGMA optimize"))

            # 9. 页面大小设置 (4KB - 16KB)
            await conn.execute(text("PRAGMA page_size = 4096"))

            # 10. 设置锁超时
            await conn.execute(text("PRAGMA busy_timeout = 30000"))

    async def analyze_database(self):
        """分析数据库统计信息"""
        async with self.engine.begin() as conn:
            # 分析所有表
            await conn.execute(text("ANALYZE"))

            # 重建索引以提高查询性能
            await conn.execute(text("REINDEX"))

    async def vacuum_database(self):
        """清理数据库碎片"""
        async with self.engine.begin() as conn:
            await conn.execute(text("VACUUM"))

    async def checkpoint_wal(self):
        """手动执行WAL检查点"""
        async with self.engine.begin() as conn:
            await conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        metrics = {}

        async with self.engine.begin() as conn:
            # 获取页面统计
            result = await conn.execute(text("PRAGMA page_count"))
            metrics["page_count"] = result.scalar()

            result = await conn.execute(text("PRAGMA page_size"))
            metrics["page_size"] = result.scalar()

            # 获取缓存统计
            result = await conn.execute(text("PRAGMA cache_size"))
            metrics["cache_size"] = abs(result.scalar()) * 1024  # 转换为字节

            # 获取WAL统计
            result = await conn.execute(text("PRAGMA journal_mode"))
            metrics["journal_mode"] = result.scalar()

            # 获取内存映射大小
            result = await conn.execute(text("PRAGMA mmap_size"))
            metrics["mmap_size"] = result.scalar()

            # 获取数据库大小
            result = await conn.execute(text("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()"))
            metrics["database_size_bytes"] = result.scalar()

        return metrics

    async def get_table_statistics(self) -> List[Dict[str, Any]]:
        """获取表统计信息"""
        tables = []

        async with self.engine.begin() as conn:
            # 获取所有表名
            result = await conn.execute(text("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """))

            table_names = [row[0] for row in result]

            for table_name in table_names:
                # 获取记录数
                count_result = await conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                record_count = count_result.scalar()

                # 获取表大小估算
                size_result = await conn.execute(text(f"""
                    SELECT SUM(CASE WHEN rootpage = 0 THEN 0 ELSE 1 END) * 4096 as estimated_size
                    FROM sqlite_master
                    WHERE tbl_name = '{table_name}' OR sql LIKE '%{table_name}%'
                """))
                estimated_size = size_result.scalar() or 0

                tables.append({
                    "table_name": table_name,
                    "record_count": record_count,
                    "estimated_size_bytes": estimated_size,
                    "estimated_size_mb": estimated_size / (1024 * 1024)
                })

        return tables

    async def recommend_optimizations(self) -> List[str]:
        """推荐优化建议"""
        recommendations = []

        metrics = await self.get_performance_metrics()
        table_stats = await self.get_table_statistics()

        # 检查数据库大小
        db_size_mb = metrics.get("database_size_bytes", 0) / (1024 * 1024)
        if db_size_mb > 1000:  # 超过1GB
            recommendations.append("数据库较大，建议考虑数据归档或分区")

        # 检查缓存设置
        cache_size_mb = metrics.get("cache_size", 0) / (1024 * 1024)
        if cache_size_mb < 50:
            recommendations.append("建议增加缓存大小到至少64MB")

        # 检查WAL模式
        if metrics.get("journal_mode") != "wal":
            recommendations.append("建议启用WAL模式以提高并发性能")

        # 检查大表
        large_tables = [t for t in table_stats if t["estimated_size_mb"] > 100]
        if large_tables:
            recommendations.append(f"发现大表: {', '.join([t['table_name'] for t in large_tables])}，建议优化索引")

        # 检查内存映射
        if metrics.get("mmap_size", 0) < 100 * 1024 * 1024:  # 小于100MB
            recommendations.append("建议增加内存映射大小以提高大文件访问性能")

        if not recommendations:
            recommendations.append("当前配置良好，无需额外优化")

        return recommendations
```

## 总结

本指南提供了SQLite在Python异步环境中的全面最佳实践：

### 核心要点：

1. **库选择**：对于中小型项目推荐aiosqlite，大型项目推荐SQLAlchemy 2.0 async
2. **连接池管理**：合理配置连接池大小，实现并发控制和重试机制
3. **ORM选择**：SQLAlchemy 2.0 async提供最佳的性能和功能平衡
4. **数据迁移**：实现版本化迁移系统，支持回滚和依赖管理
5. **事务管理**：使用异步事务管理器，实现超时控制和错误恢复
6. **性能优化**：合理配置SQLite参数，定期维护数据库

### 性能优化建议：

- 启用WAL模式提高并发性能
- 增加缓存大小到64MB以上
- 使用内存映射提高大文件访问性能
- 合理设计索引避免过度索引
- 实现批量操作减少数据库往返
- 使用连接池管理数据库连接
- 定期执行VACUUM和ANALYZE维护数据库

这些实践将帮助您在异步环境中充分利用SQLite的性能优势，同时保证数据的一致性和可靠性。