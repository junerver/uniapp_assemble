"""
Build任务数据模型。

用于跟踪构建任务的状态、进度和结果信息。
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from uuid import UUID, uuid4

from ..config.database import Base

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """任务类型枚举。"""
    RESOURCE_REPLACE = "resource_replace"
    BUILD = "build"
    EXTRACT_APK = "extract_apk"


class TaskStatus(str, Enum):
    """任务状态枚举。"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BuildTask(Base):
    """构建任务模型。"""

    __tablename__ = "build_tasks"

    # 基础字段
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(String(36), ForeignKey("android_projects.id", ondelete="CASCADE"), nullable=False)

    # 任务信息
    task_type = Column(String(50), nullable=False, comment="任务类型")
    status = Column(String(20), nullable=False, default=TaskStatus.PENDING.value, comment="任务状态")
    progress = Column(Integer, default=0, comment="进度百分比")

    # 时间信息
    started_at = Column(DateTime(timezone=True), nullable=True, comment="开始时间")
    completed_at = Column(DateTime(timezone=True), nullable=True, comment="完成时间")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 结果信息
    error_message = Column(Text, nullable=True, comment="错误信息")
    result_data = Column(JSON, nullable=True, comment="结果数据")

    # 构建相关
    resource_package_path = Column(Text, nullable=True, comment="资源包路径")
    git_branch = Column(String(255), nullable=True, comment="Git分支名称")
    commit_hash = Column(String(40), nullable=True, comment="提交哈希")

    # 配置选项
    config_options = Column(JSON, nullable=True, comment="构建配置选项")

    # 关系
    project = relationship("AndroidProject", back_populates="build_tasks")
    build_results = relationship("BuildResult", back_populates="build_task", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<BuildTask(id={self.id}, type={self.task_type}, status={self.status})>"

    @property
    def is_completed(self) -> bool:
        """检查任务是否已完成。"""
        return self.status in [TaskStatus.COMPLETED.value, TaskStatus.FAILED.value, TaskStatus.CANCELLED.value]

    @property
    def is_running(self) -> bool:
        """检查任务是否正在运行。"""
        return self.status == TaskStatus.RUNNING.value

    @property
    def duration_seconds(self) -> Optional[int]:
        """获取任务执行时长（秒）。"""
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds())
        elif self.started_at:
            return int((datetime.utcnow() - self.started_at).total_seconds())
        return None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式。"""
        return {
            "id": str(self.id),
            "project_id": str(self.project_id),
            "task_type": self.task_type,
            "status": self.status,
            "progress": self.progress,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "error_message": self.error_message,
            "result_data": self.result_data,
            "resource_package_path": self.resource_package_path,
            "git_branch": self.git_branch,
            "commit_hash": self.commit_hash,
            "config_options": self.config_options,
            "is_completed": self.is_completed,
            "is_running": self.is_running,
            "duration_seconds": self.duration_seconds
        }

    @classmethod
    def create_resource_replace_task(
        cls,
        project_id: str,
        resource_package_path: str,
        git_branch: str,
        config_options: Optional[Dict[str, Any]] = None
    ) -> "BuildTask":
        """创建资源替换任务。"""
        return cls(
            project_id=project_id,
            task_type=TaskType.RESOURCE_REPLACE.value,
            resource_package_path=resource_package_path,
            git_branch=git_branch,
            config_options=config_options or {}
        )

    @classmethod
    def create_build_task(
        cls,
        project_id: str,
        git_branch: str,
        resource_package_path: Optional[str] = None,
        config_options: Optional[Dict[str, Any]] = None
    ) -> "BuildTask":
        """创建构建任务。"""
        return cls(
            project_id=project_id,
            task_type=TaskType.BUILD.value,
            git_branch=git_branch,
            resource_package_path=resource_package_path,
            config_options=config_options or {}
        )

    @classmethod
    def create_extract_apk_task(
        cls,
        project_id: str,
        build_task_id: str,
        config_options: Optional[Dict[str, Any]] = None
    ) -> "BuildTask":
        """创建APK提取任务。"""
        return cls(
            project_id=project_id,
            task_type=TaskType.EXTRACT_APK.value,
            config_options=config_options or {}
        )

    def start(self) -> None:
        """开始任务。"""
        self.status = TaskStatus.RUNNING.value
        self.started_at = datetime.utcnow()
        self.progress = 0
        logger.info(f"BuildTask {self.id} started")

    def complete(self, result_data: Optional[Dict[str, Any]] = None) -> None:
        """完成任务。"""
        self.status = TaskStatus.COMPLETED.value
        self.completed_at = datetime.utcnow()
        self.progress = 100
        if result_data:
            self.result_data = result_data
        logger.info(f"BuildTask {self.id} completed successfully")

    def fail(self, error_message: str) -> None:
        """任务失败。"""
        self.status = TaskStatus.FAILED.value
        self.completed_at = datetime.utcnow()
        self.error_message = error_message
        logger.error(f"BuildTask {self.id} failed: {error_message}")

    def cancel(self) -> None:
        """取消任务。"""
        self.status = TaskStatus.CANCELLED.value
        self.completed_at = datetime.utcnow()
        logger.info(f"BuildTask {self.id} cancelled")

    def update_progress(self, progress: int, message: Optional[str] = None) -> None:
        """更新任务进度。"""
        self.progress = max(0, min(100, progress))
        if message and self.result_data is None:
            self.result_data = {}
        if message:
            self.result_data["status_message"] = message
        logger.debug(f"BuildTask {self.id} progress updated to {self.progress}%")