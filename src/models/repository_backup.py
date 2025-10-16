"""
Repository备份模型。

用于管理Git仓库的备份，支持安全操作和恢复。
"""

from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from ..config.database import Base


class BackupType(str, Enum):
    """备份类型枚举。"""
    FULL = "full"
    INCREMENTAL = "incremental"
    SNAPSHOT = "snapshot"


class BackupStatus(str, Enum):
    """备份状态枚举。"""
    CREATING = "creating"
    COMPLETED = "completed"
    FAILED = "failed"
    DELETED = "deleted"


class RepositoryBackup(Base):
    """Repository备份模型。

    在执行危险操作前创建备份，支持快速恢复。
    """

    __tablename__ = "repository_backups"

    # 基础字段
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(String(36), ForeignKey("android_projects.id", ondelete="CASCADE"), nullable=False)
    git_operation_id = Column(String(36), ForeignKey("git_operations.id", ondelete="CASCADE"), nullable=False)

    # 备份信息
    backup_type = Column(String(20), nullable=False, default=BackupType.SNAPSHOT.value, comment="备份类型")
    status = Column(String(20), nullable=False, default=BackupStatus.CREATING.value, comment="备份状态")
    description = Column(Text, nullable=True, comment="备份描述")

    # 备份内容
    backup_path = Column(String(500), nullable=False, comment="备份文件路径")
    backup_size = Column(Integer, nullable=True, comment="备份大小(字节)")
    compression_method = Column(String(50), nullable=True, comment="压缩方法")

    # Git状态信息
    commit_hash = Column(String(40), nullable=True, comment="备份时的提交哈希")
    branch_name = Column(String(255), nullable=True, comment="备份时的分支名称")
    tracked_files_count = Column(Integer, nullable=True, comment="跟踪的文件数量")
    untracked_files_count = Column(Integer, nullable=True, comment="未跟踪的文件数量")
    modified_files_count = Column(Integer, nullable=True, comment="修改的文件数量")

    # 元数据
    backup_metadata = Column(JSON, nullable=True, comment="备份元数据")
    file_list = Column(JSON, nullable=True, comment="备份文件列表")
    git_status = Column(JSON, nullable=True, comment="Git状态快照")

    # 时间信息
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    expires_at = Column(DateTime, nullable=True, comment="过期时间")

    # 配置选项
    backup_config = Column(JSON, nullable=True, comment="备份配置")

    # 关系
    project = relationship("AndroidProject")
    git_operation = relationship("GitOperation", back_populates="repository_backups")

    def __repr__(self) -> str:
        return f"<RepositoryBackup(id={self.id}, type={self.backup_type}, status={self.status})>"

    @property
    def is_completed(self) -> bool:
        """检查备份是否已完成。"""
        return self.status == BackupStatus.COMPLETED.value

    @property
    def is_expired(self) -> bool:
        """检查备份是否已过期。"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at

    @property
    def duration_seconds(self) -> Optional[int]:
        """获取备份创建时长（秒）。"""
        if self.completed_at:
            return int((self.completed_at - self.created_at).total_seconds())
        return int((datetime.utcnow() - self.created_at).total_seconds())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式。"""
        return {
            "id": str(self.id),
            "project_id": str(self.project_id),
            "git_operation_id": str(self.git_operation_id),
            "backup_type": self.backup_type,
            "status": self.status,
            "description": self.description,
            "backup_path": self.backup_path,
            "backup_size": self.backup_size,
            "compression_method": self.compression_method,
            "commit_hash": self.commit_hash,
            "branch_name": self.branch_name,
            "tracked_files_count": self.tracked_files_count,
            "untracked_files_count": self.untracked_files_count,
            "modified_files_count": self.modified_files_count,
            "backup_metadata": self.backup_metadata,
            "file_list": self.file_list,
            "git_status": self.git_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "backup_config": self.backup_config,
            "is_completed": self.is_completed,
            "is_expired": self.is_expired,
            "duration_seconds": self.duration_seconds
        }

    @classmethod
    def create_snapshot_backup(
        cls,
        project_id: str,
        git_operation_id: str,
        backup_path: str,
        commit_hash: str,
        branch_name: str,
        description: Optional[str] = None,
        backup_config: Optional[Dict[str, Any]] = None
    ) -> "RepositoryBackup":
        """创建快照备份记录。"""
        return cls(
            project_id=project_id,
            git_operation_id=git_operation_id,
            backup_type=BackupType.SNAPSHOT.value,
            description=description or f"操作前快照备份",
            backup_path=backup_path,
            commit_hash=commit_hash,
            branch_name=branch_name,
            backup_config=backup_config or {}
        )

    @classmethod
    def create_full_backup(
        cls,
        project_id: str,
        git_operation_id: str,
        backup_path: str,
        description: Optional[str] = None,
        compression_method: Optional[str] = None,
        backup_config: Optional[Dict[str, Any]] = None
    ) -> "RepositoryBackup":
        """创建完整备份记录。"""
        return cls(
            project_id=project_id,
            git_operation_id=git_operation_id,
            backup_type=BackupType.FULL.value,
            description=description or "完整仓库备份",
            backup_path=backup_path,
            compression_method=compression_method,
            backup_config=backup_config or {}
        )

    def complete(self, backup_size: Optional[int] = None, backup_metadata: Optional[Dict[str, Any]] = None) -> None:
        """标记备份完成。"""
        self.status = BackupStatus.COMPLETED.value
        self.completed_at = datetime.utcnow()

        if backup_size is not None:
            self.backup_size = backup_size
        if backup_metadata:
            self.backup_metadata = backup_metadata

    def fail(self, error_message: str) -> None:
        """标记备份失败。"""
        self.status = BackupStatus.FAILED.value
        if not self.backup_metadata:
            self.backup_metadata = {}
        self.backup_metadata["error"] = error_message

    def set_expiry(self, days: int = 30) -> None:
        """设置备份过期时间。"""
        from datetime import timedelta
        self.expires_at = datetime.utcnow() + timedelta(days=days)

    def add_file_info(
        self,
        tracked_count: int,
        untracked_count: int,
        modified_count: int,
        file_list: Optional[list] = None
    ) -> None:
        """添加文件信息。"""
        self.tracked_files_count = tracked_count
        self.untracked_files_count = untracked_count
        self.modified_files_count = modified_count
        if file_list:
            self.file_list = file_list

    def set_git_status(self, git_status: Dict[str, Any]) -> None:
        """设置Git状态快照。"""
        self.git_status = git_status