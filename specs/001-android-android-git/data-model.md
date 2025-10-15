# Data Model Design - Android项目资源包替换构建工具

**Created**: 2025-10-15
**Phase**: Phase 1 - Design & Contracts
**Research**: Based on Phase 0 research findings

## Overview

本文档定义了Android项目资源包替换构建工具的数据模型，基于SQLAlchemy 2.0 async ORM设计，支持异步操作和高并发访问。

## Entity Relationship Diagram

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  AndroidProject │    │   BuildTask    │    │  GitOperation   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                      │                      │
         │                      │                      │
         │                      │                      │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ ProjectConfig   │    │  BuildResult   │    │ RepositoryBackup│
└─────────────────┘    └─────────┬─────┘    └─────────────────┘
         │                      │    │
         └──────────────────────┘    │
                                   │
                           ┌─────────────────┐
                           │   BuildLog      │
                           └─────────────────┘
```

## Core Entities

### 1. AndroidProject (Android项目配置)

**Purpose**: 管理Android项目的基本配置信息

**Fields**:
- `id`: Primary Key (UUID)
- `name`: 项目名称 (String, unique)
- `alias`: 项目别名 (String, nullable)
- `path`: 项目绝对路径 (Path)
- `description`: 项目描述 (Text, nullable)
- `is_active`: 是否激活 (Boolean, default=True)
- `created_at`: 创建时间 (DateTime)
- `updated_at`: 更新时间 (DateTime)

**Relationships**:
- One-to-Many: BuildTask (构建任务)
- One-to-Many: ProjectConfig (项目配置)
- One-to-Many: GitOperation (Git操作记录)

**Constraints**:
- `name` must be unique
- `path` must be a valid directory path
- `alias` must be unique if provided

### 2. ProjectConfig (项目配置)

**Purpose**: 存储项目的详细配置信息

**Fields**:
- `id`: Primary Key (UUID)
- `project_id`: Foreign Key to AndroidProject
- `config_type`: 配置类型 (Enum: git, build, custom)
- `config_data`: 配置数据 (JSON)
- `is_default`: 是否默认配置 (Boolean, default=False)
- `created_at`: 创建时间 (DateTime)
- `updated_at`: 更新时间 (DateTime)

**Relationships**:
- Many-to-One: AndroidProject

**Config Types**:
- `git`: Git仓库相关配置
- `build`: 构建相关配置
- `custom`: 自定义配置

### 3. BuildTask (构建任务)

**Purpose**: 跟踪构建任务的状态和结果

**Fields**:
- `id`: Primary Key (UUID)
- `project_id`: Foreign Key to AndroidProject
- `task_type`: 任务类型 (Enum: resource_replace, build, extract_apk)
- `status`: 任务状态 (Enum: pending, running, completed, failed, cancelled)
- `progress`: 进度百分比 (Integer, 0-100)
- `started_at`: 开始时间 (DateTime, nullable)
- `completed_at`: 完成时间 (DateTime, nullable)
- `error_message`: 错误信息 (Text, nullable)
- `result_data`: 结果数据 (JSON, nullable)
- `resource_package_path`: 资源包路径 (Path, nullable)
- `git_branch`: Git分支名称 (String)
- `commit_hash`: 提交哈希 (String, nullable)
- `created_at`: 创建时间 (DateTime)
- `updated_at`: 更新时间 (DateTime)

**Relationships**:
- Many-to-One: AndroidProject
- One-to-Many: BuildResult (构建结果)
- One-to-Many: BuildLog (构建日志)

**Task Types**:
- `resource_replace`: 资源替换
- `build`: Gradle构建
- `extract_apk`: 提取APK文件

### 4. BuildResult (构建结果)

**Purpose**: 存储构建的产出文件信息

**Fields**:
- `id`: Primary Key (UUID)
- `build_task_id`: Foreign Key to BuildTask
- `file_type`: 文件类型 (Enum: apk, log, metadata)
- `file_path`: 文件路径 (Path)
- `file_size`: 文件大小 (Integer)
- `file_hash`: 文件哈希 (String)
- `metadata`: 文件元数据 (JSON, nullable)
- `created_at`: 创建时间 (DateTime)

**Relationships**:
- Many-to-One: BuildTask

**File Types**:
- `apk`: APK文件
- `log`: 构建日志文件
- `metadata`: 元数据文件

### 5. BuildLog (构建日志)

**Purpose**: 存储构建过程中的详细日志

**Fields**:
- `id`: Primary Key (UUID)
- `build_task_id`: Foreign Key to BuildTask
- `log_level`: 日志级别 (Enum: info, warning, error, debug)
- `timestamp`: 时间戳 (DateTime)
- `message`: 日志消息 (Text)
- `source`: 日志来源 (String)
- `line_number`: 行号 (Integer, nullable)
- `created_at`: 创建时间 (DateTime)

**Relationships**:
- Many-to-One: BuildTask

### 6. GitOperation (Git操作记录)

**Purpose**: 记录Git操作的历史和状态

**Fields**:
- `id`: Primary Key (UUID)
- `project_id`: Foreign Key to AndroidProject
- `operation_type`: 操作类型 (Enum: commit, rollback, branch_switch, backup)
- `status`: 操作状态 (Enum: pending, in_progress, completed, failed)
- `commit_hash`: 提交哈希 (String, nullable)
- `commit_message`: 提交信息 (Text, nullable)
- `branch_name`: 分支名称 (String, nullable)
- `backup_path`: 备份路径 (Path, nullable)
- `error_message`: 错误信息 (Text, nullable)
- `operation_data`: 操作数据 (JSON, nullable)
- `created_at`: 创建时间 (DateTime)
- `completed_at`: 完成时间 (DateTime, nullable)

**Relationships**:
- Many-to-One: AndroidProject

**Operation Types**:
- `commit`: Git提交
- `rollback`: Git回滚
- `branch_switch`: 分支切换
- `backup`: 备份操作

### 7. RepositoryBackup (仓库状态备份)

**Purpose**: 存储仓库状态备份信息

**Fields**:
- `id`: Primary Key (UUID)
- `project_id`: Foreign Key to AndroidProject
- `backup_id`: 备份ID (String, unique)
- `backup_path`: 备份路径 (Path)
- `backup_type`: 备份类型 (Enum: full, incremental)
- `file_count`: 文件数量 (Integer)
- `total_size`: 总大小 (Integer)
- `created_at`: 创建时间 (DateTime)
- `is_active`: 是否有效 (Boolean, default=True)
- `expires_at`: 过期时间 (DateTime, nullable)

**Relationships**:
- Many-to-One: AndroidProject

## Enums Definition

### TaskType
```python
from enum import Enum

class TaskType(str, Enum):
    RESOURCE_REPLACE = "resource_replace"
    BUILD = "build"
    EXTRACT_APK = "extract_apk"
```

### TaskStatus
```python
class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

### GitOperationType
```python
class GitOperationType(str, Enum):
    COMMIT = "commit"
    ROLLBACK = "rollback"
    BRANCH_SWITCH = "branch_switch"
    BACKUP = "backup"
```

### LogLevel
```python
class LogLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    DEBUG = "debug"
```

## Database Schema

### Tables Structure

```sql
-- Android Project Table
CREATE TABLE android_projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    alias VARCHAR(255),
    path TEXT NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Project Config Table
CREATE TABLE project_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES android_projects(id) ON DELETE CASCADE,
    config_type VARCHAR(50) NOT NULL,
    config_data JSONB NOT NULL,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Build Task Table
CREATE TABLE build_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES android_projects(id) ON DELETE CASCADE,
    task_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    result_data JSONB,
    resource_package_path TEXT,
    git_branch VARCHAR(255),
    commit_hash VARCHAR(40),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Build Result Table
CREATE TABLE build_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    build_task_id UUID NOT NULL REFERENCES build_tasks(id) ON DELETE CASCADE,
    file_type VARCHAR(20) NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER,
    file_hash VARCHAR(64),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Build Log Table
CREATE TABLE build_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    build_task_id UUID NOT NULL REFERENCES build_tasks(id) ON DELETE CASCADE,
    log_level VARCHAR(10) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    message TEXT NOT NULL,
    source VARCHAR(100),
    line_number INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Git Operation Table
CREATE TABLE git_operations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES android_projects(id) ON DELETE CASCADE,
    operation_type VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    commit_hash VARCHAR(40),
    commit_message TEXT,
    branch_name VARCHAR(255),
    backup_path TEXT,
    error_message TEXT,
    operation_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Repository Backup Table
CREATE TABLE repository_backups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES android_projects(id) ON DELETE CASCADE,
    backup_id VARCHAR(100) NOT NULL UNIQUE,
    backup_path TEXT NOT NULL,
    backup_type VARCHAR(20) NOT NULL,
    file_count INTEGER DEFAULT 0,
    total_size INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    expires_at TIMESTAMP
);
```

### Indexes

```sql
-- Performance Indexes
CREATE INDEX idx_android_projects_name ON android_projects(name);
CREATE INDEX idx_android_projects_active ON android_projects(is_active);
CREATE INDEX idx_project_configs_project_id ON project_configs(project_id);
CREATE INDEX idx_project_configs_type ON project_configs(config_type);
CREATE INDEX idx_build_tasks_project_id ON build_tasks(project_id);
CREATE INDEX idx_build_tasks_status ON build_tasks(status);
CREATE INDEX idx_build_tasks_created_at ON build_tasks(created_at);
CREATE INDEX idx_build_results_task_id ON build_results(build_task_id);
CREATE INDEX idx_build_logs_task_id ON build_logs(build_task_id);
CREATE INDEX idx_build_logs_timestamp ON build_logs(timestamp);
CREATE INDEX idx_git_operations_project_id ON git_operations(project_id);
CREATE INDEX idx_git_operations_type ON git_operations(operation_type);
CREATE INDEX idx_repository_backups_project_id ON repository_backups(project_id);
CREATE INDEX idx_repository_backups_active ON repository_backups(is_active);
```

## Data Validation Rules

### Business Rules
1. **Project Uniqueness**: Project names must be unique across the system
2. **Path Validation**: Project paths must be valid and accessible
3. **Task Status Progression**: Tasks must follow proper state transitions
4. **Backup Expiration**: Repository backups automatically expire after 7 days
5. **File Size Limits**: Resource packages limited to 500MB
6. **Concurrent Operations**: Maximum 5 concurrent build tasks per project

### Data Integrity
1. **Referential Integrity**: All foreign keys properly constrained
2. **Cascade Deletion**: Related records cleaned up on project deletion
3. **Unique Constraints**: Critical fields have uniqueness constraints
4. **Non-Null Constraints**: Required fields properly validated

## Async Repository Pattern

### Base Repository
```python
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

class BaseRepository(ABC):
    """异步仓储基类"""

    def __init__(self, session: AsyncSession):
        self.session = session

    @abstractmethod
    async def create(self, **kwargs) -> Any:
        """创建实体"""
        pass

    @abstractmethod
    async def get_by_id(self, id: str) -> Optional[Any]:
        """根据ID获取实体"""
        pass

    @abstractmethod
    async def update(self, id: str, **kwargs) -> Optional[Any]:
        """更新实体"""
        pass

    @abstractmethod
    async def delete(self, id: str) -> bool:
        """删除实体"""
        pass

    @abstractmethod
    async def list(self, **filters) -> List[Any]:
        """列出实体"""
        pass
```

### Specific Repository Example
```python
class AndroidProjectRepository(BaseRepository):
    """Android项目仓储"""

    async def create(self, **kwargs) -> AndroidProject:
        project = AndroidProject(**kwargs)
        self.session.add(project)
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def get_by_name(self, name: str) -> Optional[AndroidProject]:
        result = await self.session.execute(
            select(AndroidProject).where(AndroidProject.name == name)
        )
        return result.scalar_one_or_none()

    async def get_active_projects(self) -> List[AndroidProject]:
        result = await self.session.execute(
            select(AndroidProject).where(AndroidProject.is_active == True)
        )
        return result.scalars().all()

    async def update_status(self, id: str, is_active: bool) -> bool:
        result = await self.session.execute(
            update(AndroidProject)
            .where(AndroidProject.id == id)
            .values(is_active=is_active)
        )
        await self.session.commit()
        return result.rowcount > 0
```

## Migration Strategy

### Versioning
- Use Alembic for database migrations
- Version control for schema changes
- Rollback capabilities for failed migrations
- Automatic migration on application startup

### Migration Scripts
- Create initial schema
- Add new columns/tables as needed
- Data transformation scripts
- Index creation and optimization

This data model provides a solid foundation for the Android project resource replacement and build tool, supporting all required features while maintaining data integrity and performance.