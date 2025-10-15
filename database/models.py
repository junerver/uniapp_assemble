"""
Android项目构建工具 - 核心数据模型设计

本文档定义了Android项目构建工具的核心数据模型，包括：
- 项目配置管理
- 构建历史记录
- Git操作追踪
- 性能监控数据
- 用户操作审计
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, JSON, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON

Base = declarative_base()


# ================================
# 枚举类型定义
# ================================

class BuildStatus(str, Enum):
    """构建状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class GitOperationType(str, Enum):
    """Git操作类型枚举"""
    CLONE = "clone"
    PULL = "pull"
    PUSH = "push"
    COMMIT = "commit"
    BRANCH = "branch"
    MERGE = "merge"
    RESET = "reset"
    STASH = "stash"
    TAG = "tag"


class ProjectType(str, Enum):
    """项目类型枚举"""
    ANDROID_NATIVE = "android_native"
    REACT_NATIVE = "react_native"
    FLUTTER = "flutter"
    IONIC = "ionic"
    XAMARIN = "xamarin"
    CORDOVA = "cordova"


# ================================
# SQLAlchemy 表模型定义
# ================================

class Project(Base):
    """项目配置表"""
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, comment="项目名称")
    description = Column(Text, comment="项目描述")
    project_type = Column(String(50), nullable=False, comment="项目类型")
    repository_url = Column(String(500), nullable=False, comment="Git仓库URL")
    local_path = Column(String(500), nullable=False, comment="本地路径")
    branch = Column(String(100), default="main", comment="默认分支")

    # 构建配置
    build_command = Column(String(1000), comment="构建命令")
    environment_vars = Column(JSON, comment="环境变量")
    build_timeout = Column(Integer, default=1800, comment="构建超时时间(秒)")

    # 元数据
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    is_active = Column(Boolean, default=True, comment="是否激活")
    tags = Column(JSON, comment="项目标签")

    # 关系
    builds = relationship("Build", back_populates="project", cascade="all, delete-orphan")
    git_operations = relationship("GitOperation", back_populates="project", cascade="all, delete-orphan")
    configurations = relationship("ProjectConfiguration", back_populates="project", cascade="all, delete-orphan")

    # 索引
    __table_args__ = (
        Index('idx_project_name', 'name'),
        Index('idx_project_type', 'project_type'),
        Index('idx_project_active', 'is_active'),
        Index('idx_project_created', 'created_at'),
    )


class Build(Base):
    """构建记录表"""
    __tablename__ = "builds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, comment="项目ID")
    build_number = Column(Integer, nullable=False, comment="构建编号")
    status = Column(String(20), nullable=False, default=BuildStatus.PENDING, comment="构建状态")

    # 时间信息
    started_at = Column(DateTime, comment="开始时间")
    completed_at = Column(DateTime, comment="完成时间")
    duration_seconds = Column(Integer, comment="持续时间(秒)")

    # 构建信息
    commit_hash = Column(String(40), comment="Git提交哈希")
    branch = Column(String(100), comment="构建分支")
    build_type = Column(String(50), comment="构建类型(debug/release)")
    triggered_by = Column(String(100), comment="触发者")

    # 结果数据
    exit_code = Column(Integer, comment="退出代码")
    artifact_path = Column(String(500), comment="构建产物路径")
    artifact_size = Column(Integer, comment="构建产物大小(字节)")

    # 性能指标
    memory_usage_mb = Column(Integer, comment="内存使用(MB)")
    cpu_usage_percent = Column(Integer, comment="CPU使用率(%)")

    # 元数据
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    build_metadata = Column(JSON, comment="构建元数据")

    # 关系
    project = relationship("Project", back_populates="builds")
    logs = relationship("BuildLog", back_populates="build", cascade="all, delete-orphan")
    artifacts = relationship("BuildArtifact", back_populates="build", cascade="all, delete-orphan")

    # 索引
    __table_args__ = (
        Index('idx_build_project_status', 'project_id', 'status'),
        Index('idx_build_number', 'project_id', 'build_number'),
        Index('idx_build_started', 'started_at'),
        Index('idx_build_commit', 'commit_hash'),
        Index('idx_build_status', 'status'),
        UniqueConstraint('project_id', 'build_number', name='uq_project_build_number'),
    )


class BuildLog(Base):
    """构建日志表（大文本优化存储）"""
    __tablename__ = "build_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    build_id = Column(Integer, ForeignKey("builds.id"), nullable=False, comment="构建ID")
    sequence_number = Column(Integer, nullable=False, comment="日志序号")
    level = Column(String(20), comment="日志级别(DEBUG/INFO/WARN/ERROR)")
    timestamp = Column(DateTime, default=datetime.utcnow, comment="时间戳")
    message = Column(Text, comment="日志消息")
    source = Column(String(100), comment="日志来源")

    # 关系
    build = relationship("Build", back_populates="logs")

    # 索引
    __table_args__ = (
        Index('idx_log_build_sequence', 'build_id', 'sequence_number'),
        Index('idx_log_timestamp', 'timestamp'),
        Index('idx_log_level', 'level'),
        UniqueConstraint('build_id', 'sequence_number', name='uq_build_log_sequence'),
    )


class BuildArtifact(Base):
    """构建产物表"""
    __tablename__ = "build_artifacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    build_id = Column(Integer, ForeignKey("builds.id"), nullable=False, comment="构建ID")
    name = Column(String(255), nullable=False, comment="产物名称")
    file_path = Column(String(500), nullable=False, comment="文件路径")
    file_size = Column(Integer, comment="文件大小(字节)")
    file_type = Column(String(50), comment="文件类型")
    checksum = Column(String(64), comment="文件校验和")

    # 元数据
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    metadata = Column(JSON, comment="产物元数据")

    # 关系
    build = relationship("Build", back_populates="artifacts")

    # 索引
    __table_args__ = (
        Index('idx_artifact_build', 'build_id'),
        Index('idx_artifact_type', 'file_type'),
        Index('idx_artifact_checksum', 'checksum'),
    )


class GitOperation(Base):
    """Git操作记录表"""
    __tablename__ = "git_operations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, comment="项目ID")
    operation_type = Column(String(50), nullable=False, comment="操作类型")
    status = Column(String(20), nullable=False, comment="操作状态")

    # 操作信息
    from_branch = Column(String(100), comment="源分支")
    to_branch = Column(String(100), comment="目标分支")
    commit_hash = Column(String(40), comment="提交哈希")
    commit_message = Column(Text, comment="提交消息")

    # 时间信息
    started_at = Column(DateTime, default=datetime.utcnow, comment="开始时间")
    completed_at = Column(DateTime, comment="完成时间")
    duration_seconds = Column(Integer, comment="持续时间(秒)")

    # 结果信息
    success = Column(Boolean, comment="是否成功")
    error_message = Column(Text, comment="错误消息")
    files_changed = Column(Integer, comment="变更文件数")
    insertions = Column(Integer, comment="新增行数")
    deletions = Column(Integer, comment="删除行数")

    # 元数据
    operation_metadata = Column(JSON, comment="操作元数据")

    # 关系
    project = relationship("Project", back_populates="git_operations")

    # 索引
    __table_args__ = (
        Index('idx_git_project_type', 'project_id', 'operation_type'),
        Index('idx_git_status', 'status'),
        Index('idx_git_started', 'started_at'),
        Index('idx_git_commit', 'commit_hash'),
    )


class ProjectConfiguration(Base):
    """项目配置表"""
    __tablename__ = "project_configurations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, comment="项目ID")
    config_key = Column(String(255), nullable=False, comment="配置键")
    config_value = Column(Text, comment="配置值")
    config_type = Column(String(50), comment="配置类型(string/json/boolean/integer)")
    is_encrypted = Column(Boolean, default=False, comment="是否加密")

    # 元数据
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    created_by = Column(String(100), comment="创建者")

    # 关系
    project = relationship("Project", back_populates="configurations")

    # 索引
    __table_args__ = (
        Index('idx_config_project_key', 'project_id', 'config_key'),
        Index('idx_config_type', 'config_type'),
        UniqueConstraint('project_id', 'config_key', name='uq_project_config_key'),
    )


class SystemMetrics(Base):
    """系统性能指标表"""
    __tablename__ = "system_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_name = Column(String(100), nullable=False, comment="指标名称")
    metric_value = Column(Integer, nullable=False, comment="指标值")
    metric_unit = Column(String(20), comment="指标单位")

    # 关联信息
    build_id = Column(Integer, ForeignKey("builds.id"), comment="关联构建ID")
    project_id = Column(Integer, ForeignKey("projects.id"), comment="关联项目ID")

    # 时间信息
    timestamp = Column(DateTime, default=datetime.utcnow, comment="时间戳")

    # 元数据
    metadata = Column(JSON, comment="指标元数据")

    # 索引
    __table_args__ = (
        Index('idx_metrics_name_timestamp', 'metric_name', 'timestamp'),
        Index('idx_metrics_build', 'build_id'),
        Index('idx_metrics_project', 'project_id'),
    )


# ================================
# Pydantic 模型定义
# ================================

class ProjectBase(BaseModel):
    """项目基础模型"""
    name: str = Field(..., min_length=1, max_length=255, description="项目名称")
    description: Optional[str] = Field(None, description="项目描述")
    project_type: ProjectType = Field(..., description="项目类型")
    repository_url: str = Field(..., min_length=1, max_length=500, description="Git仓库URL")
    local_path: str = Field(..., min_length=1, max_length=500, description="本地路径")
    branch: str = Field("main", max_length=100, description="默认分支")
    build_command: Optional[str] = Field(None, max_length=1000, description="构建命令")
    environment_vars: Optional[Dict[str, Any]] = Field(None, description="环境变量")
    build_timeout: int = Field(1800, gt=0, description="构建超时时间(秒)")
    tags: Optional[List[str]] = Field(None, description="项目标签")

    @validator('repository_url')
    def validate_repo_url(cls, v):
        """验证Git仓库URL格式"""
        if not (v.startswith('http') or v.startswith('git')):
            raise ValueError('无效的Git仓库URL格式')
        return v


class ProjectCreate(ProjectBase):
    """创建项目模型"""
    pass


class ProjectUpdate(BaseModel):
    """更新项目模型"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    build_command: Optional[str] = Field(None, max_length=1000)
    environment_vars: Optional[Dict[str, Any]] = None
    build_timeout: Optional[int] = Field(None, gt=0)
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None


class ProjectInDB(ProjectBase):
    """数据库中的项目模型"""
    id: int
    created_at: datetime
    updated_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class BuildBase(BaseModel):
    """构建基础模型"""
    build_type: Optional[str] = Field(None, max_length=50, description="构建类型")
    triggered_by: Optional[str] = Field(None, max_length=100, description="触发者")
    commit_hash: Optional[str] = Field(None, max_length=40, description="提交哈希")
    branch: Optional[str] = Field(None, max_length=100, description="构建分支")


class BuildCreate(BuildBase):
    """创建构建模型"""
    project_id: int = Field(..., gt=0, description="项目ID")


class BuildUpdate(BaseModel):
    """更新构建模型"""
    status: Optional[BuildStatus] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    exit_code: Optional[int] = None
    artifact_path: Optional[str] = None
    artifact_size: Optional[int] = None
    memory_usage_mb: Optional[int] = None
    cpu_usage_percent: Optional[int] = None


class BuildInDB(BuildBase):
    """数据库中的构建模型"""
    id: int
    project_id: int
    build_number: int
    status: BuildStatus
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[int]
    exit_code: Optional[int]
    artifact_path: Optional[str]
    artifact_size: Optional[int]
    memory_usage_mb: Optional[int]
    cpu_usage_percent: Optional[int]
    created_at: datetime
    build_metadata: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True


class BuildLogBase(BaseModel):
    """构建日志基础模型"""
    level: Optional[str] = Field(None, max_length=20, description="日志级别")
    message: str = Field(..., description="日志消息")
    source: Optional[str] = Field(None, max_length=100, description="日志来源")


class BuildLogCreate(BuildLogBase):
    """创建构建日志模型"""
    build_id: int = Field(..., gt=0)
    sequence_number: int = Field(..., ge=0)


class BuildLogInDB(BuildLogBase):
    """数据库中的构建日志模型"""
    id: int
    build_id: int
    sequence_number: int
    timestamp: datetime

    class Config:
        from_attributes = True


class GitOperationBase(BaseModel):
    """Git操作基础模型"""
    operation_type: GitOperationType = Field(..., description="操作类型")
    from_branch: Optional[str] = Field(None, max_length=100, description="源分支")
    to_branch: Optional[str] = Field(None, max_length=100, description="目标分支")
    commit_hash: Optional[str] = Field(None, max_length=40, description="提交哈希")
    commit_message: Optional[str] = Field(None, description="提交消息")


class GitOperationCreate(GitOperationBase):
    """创建Git操作模型"""
    project_id: int = Field(..., gt=0, description="项目ID")


class GitOperationInDB(GitOperationBase):
    """数据库中的Git操作模型"""
    id: int
    project_id: int
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    duration_seconds: Optional[int]
    success: Optional[bool]
    error_message: Optional[str]
    files_changed: Optional[int]
    insertions: Optional[int]
    deletions: Optional[int]
    operation_metadata: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True


# ================================
# 查询优化配置
# ================================

class DatabaseConfig:
    """数据库配置类"""

    # SQLite性能优化设置
    PRAGMAS = {
        'journal_mode': 'WAL',  # 写前日志模式，提高并发性能
        'synchronous': 'NORMAL',  # 平衡性能和安全性
        'cache_size': '-64000',  # 64MB缓存
        'temp_store': 'MEMORY',  # 临时表存储在内存中
        'mmap_size': '268435456',  # 256MB内存映射
        'locking_mode': 'NORMAL',  # 正常锁定模式
        'foreign_keys': 'ON',  # 启用外键约束
    }

    # 连接池配置
    POOL_CONFIG = {
        'pool_size': 5,
        'max_overflow': 10,
        'pool_timeout': 30,
        'pool_recycle': 3600,
    }

    # 查询优化配置
    QUERY_TIMEOUT = 300  # 5分钟查询超时
    BATCH_SIZE = 1000  # 批量操作大小

    @staticmethod
    def get_sqlite_uri(db_path: str = "android_build_tool.db") -> str:
        """获取SQLite连接URI"""
        return f"sqlite:///{db_path}"


# ================================
# 数据验证规则
# ================================

class ValidationRules:
    """数据验证规则类"""

    # 项目名称验证规则
    PROJECT_NAME_PATTERN = r'^[a-zA-Z0-9_-]+$'
    PROJECT_NAME_MIN_LENGTH = 1
    PROJECT_NAME_MAX_LENGTH = 255

    # Git仓库URL验证规则
    GIT_URL_PATTERN = r'^(https?|git)://.+'
    GIT_URL_MAX_LENGTH = 500

    # 构建超时时间限制
    BUILD_TIMEOUT_MIN = 60  # 最少1分钟
    BUILD_TIMEOUT_MAX = 86400  # 最多24小时

    # 日志消息长度限制
    LOG_MESSAGE_MAX_LENGTH = 10000

    # 提交消息长度限制
    COMMIT_MESSAGE_MAX_LENGTH = 2000

    @classmethod
    def validate_project_name(cls, name: str) -> bool:
        """验证项目名称"""
        import re
        pattern = re.compile(cls.PROJECT_NAME_PATTERN)
        return (
            cls.PROJECT_NAME_MIN_LENGTH <= len(name) <= cls.PROJECT_NAME_MAX_LENGTH
            and bool(pattern.match(name))
        )

    @classmethod
    def validate_git_url(cls, url: str) -> bool:
        """验证Git仓库URL"""
        import re
        pattern = re.compile(cls.GIT_URL_PATTERN)
        return len(url) <= cls.GIT_URL_MAX_LENGTH and bool(pattern.match(url))

    @classmethod
    def validate_build_timeout(cls, timeout: int) -> bool:
        """验证构建超时时间"""
        return cls.BUILD_TIMEOUT_MIN <= timeout <= cls.BUILD_TIMEOUT_MAX