"""
Git操作记录模型。

用于跟踪对Git仓库执行的操作，包括提交、回滚、分支切换等。
"""

from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from ..config.database import Base


class OperationType(str, Enum):
    """Git操作类型枚举。"""
    COMMIT = "commit"
    ROLLBACK = "rollback"
    BRANCH_SWITCH = "branch_switch"
    BRANCH_CREATE = "branch_create"
    BRANCH_DELETE = "branch_delete"
    MERGE = "merge"
    STASH = "stash"
    STASH_POP = "stash_pop"


class OperationStatus(str, Enum):
    """操作状态枚举。"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GitOperation(Base):
    """Git操作记录模型。

    跟踪对Git仓库执行的所有操作，用于审计和回滚。
    """

    __tablename__ = "git_operations"

    # 基础字段
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(String(36), ForeignKey("android_projects.id", ondelete="CASCADE"), nullable=False)

    # 操作信息
    operation_type = Column(String(50), nullable=False, comment="操作类型")
    status = Column(String(20), nullable=False, default=OperationStatus.PENDING.value, comment="操作状态")

    # 操作详情
    description = Column(Text, nullable=True, comment="操作描述")
    commit_message = Column(Text, nullable=True, comment="提交消息")
    target_branch = Column(String(255), nullable=True, comment="目标分支")
    source_branch = Column(String(255), nullable=True, comment="源分支")
    commit_hash_before = Column(String(40), nullable=True, comment="操作前提交哈希")
    commit_hash_after = Column(String(40), nullable=True, comment="操作后提交哈希")

    # 结果信息
    result_data = Column(JSON, nullable=True, comment="操作结果数据")
    error_message = Column(Text, nullable=True, comment="错误信息")
    files_affected = Column(JSON, nullable=True, comment="受影响的文件列表")

    # 时间信息
    started_at = Column(DateTime, nullable=True, comment="开始时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    # 配置选项
    config_options = Column(JSON, nullable=True, comment="操作配置选项")

    # 关系
    project = relationship("AndroidProject", back_populates="git_operations")
    repository_backups = relationship("RepositoryBackup", back_populates="git_operation", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<GitOperation(id={self.id}, type={self.operation_type}, status={self.status})>"

    @property
    def is_completed(self) -> bool:
        """检查操作是否已完成。"""
        return self.status in [OperationStatus.COMPLETED.value, OperationStatus.FAILED.value, OperationStatus.CANCELLED.value]

    @property
    def is_running(self) -> bool:
        """检查操作是否正在运行。"""
        return self.status == OperationStatus.IN_PROGRESS.value

    @property
    def duration_seconds(self) -> Optional[int]:
        """获取操作执行时长（秒）。"""
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
            "operation_type": self.operation_type,
            "status": self.status,
            "description": self.description,
            "commit_message": self.commit_message,
            "target_branch": self.target_branch,
            "source_branch": self.source_branch,
            "commit_hash_before": self.commit_hash_before,
            "commit_hash_after": self.commit_hash_after,
            "result_data": self.result_data,
            "error_message": self.error_message,
            "files_affected": self.files_affected,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "config_options": self.config_options,
            "is_completed": self.is_completed,
            "is_running": self.is_running,
            "duration_seconds": self.duration_seconds
        }

    @classmethod
    def create_commit_operation(
        cls,
        project_id: str,
        commit_message: str,
        files_affected: Optional[list] = None,
        description: Optional[str] = None,
        config_options: Optional[Dict[str, Any]] = None
    ) -> "GitOperation":
        """创建提交操作记录。"""
        return cls(
            project_id=project_id,
            operation_type=OperationType.COMMIT.value,
            description=description or f"提交变更: {commit_message}",
            commit_message=commit_message,
            files_affected=files_affected or [],
            config_options=config_options or {}
        )

    @classmethod
    def create_rollback_operation(
        cls,
        project_id: str,
        target_commit_hash: str,
        description: Optional[str] = None,
        config_options: Optional[Dict[str, Any]] = None
    ) -> "GitOperation":
        """创建回滚操作记录。"""
        return cls(
            project_id=project_id,
            operation_type=OperationType.ROLLBACK.value,
            description=description or f"回滚到提交: {target_commit_hash}",
            commit_hash_after=target_commit_hash,
            config_options=config_options or {}
        )

    @classmethod
    def create_branch_operation(
        cls,
        project_id: str,
        operation_type: str,
        branch_name: str,
        source_branch: Optional[str] = None,
        description: Optional[str] = None,
        config_options: Optional[Dict[str, Any]] = None
    ) -> "GitOperation":
        """创建分支操作记录。"""
        return cls(
            project_id=project_id,
            operation_type=operation_type,
            description=description or f"分支操作: {operation_type} {branch_name}",
            target_branch=branch_name,
            source_branch=source_branch,
            config_options=config_options or {}
        )

    def start(self) -> None:
        """开始操作。"""
        self.status = OperationStatus.IN_PROGRESS.value
        self.started_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def complete(self, result_data: Optional[Dict[str, Any]] = None, commit_hash: Optional[str] = None) -> None:
        """完成操作。"""
        self.status = OperationStatus.COMPLETED.value
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

        if result_data:
            self.result_data = result_data
        if commit_hash:
            self.commit_hash_after = commit_hash

    def fail(self, error_message: str) -> None:
        """操作失败。"""
        self.status = OperationStatus.FAILED.value
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.error_message = error_message

    def cancel(self, reason: Optional[str] = None) -> None:
        """取消操作。"""
        self.status = OperationStatus.CANCELLED.value
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        if reason:
            self.error_message = f"操作已取消: {reason}"