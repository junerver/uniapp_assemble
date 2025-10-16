"""构建结果模型。"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any
import uuid

from sqlalchemy import Column, String, Integer, JSON, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship

from ..config.database import Base


class FileType(str, Enum):
    """文件类型枚举。"""
    APK = "apk"
    LOG = "log"
    METADATA = "metadata"


class BuildResult(Base):
    """构建结果模型。

    存储构建的产出文件信息，包括APK文件、构建日志和元数据文件。
    """

    __tablename__ = "build_results"

    # 基本字段
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    build_task_id = Column(String(36), ForeignKey("build_tasks.id"), nullable=False, index=True)

    # 文件信息
    file_type = Column(SQLEnum(FileType), nullable=False, comment="文件类型")
    file_path = Column(String(500), nullable=False, comment="文件路径")
    file_size = Column(Integer, nullable=False, comment="文件大小(字节)")
    file_hash = Column(String(64), nullable=True, comment="文件SHA256哈希")

    # 元数据
    file_metadata = Column(JSON, nullable=True, comment="文件元数据")

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

    # 关系
    build_task = relationship("BuildTask", back_populates="build_results")

    def __repr__(self) -> str:
        return f"<BuildResult(id={self.id}, type={self.file_type}, path={self.file_path})>"

    @property
    def filename(self) -> str:
        """获取文件名。"""
        return Path(self.file_path).name

    @property
    def file_size_mb(self) -> float:
        """获取文件大小（MB）。"""
        return round(self.file_size / (1024 * 1024), 2)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return {
            "id": self.id,
            "build_task_id": self.build_task_id,
            "file_type": self.file_type.value if self.file_type else None,
            "file_path": self.file_path,
            "filename": self.filename,
            "file_size": self.file_size,
            "file_size_mb": self.file_size_mb,
            "file_hash": self.file_hash,
            "metadata": self.file_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    @classmethod
    def create_apk_result(
        cls,
        build_task_id: str,
        file_path: str,
        file_size: int,
        file_hash: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "BuildResult":
        """创建APK文件结果。"""
        return cls(
            build_task_id=build_task_id,
            file_type=FileType.APK,
            file_path=file_path,
            file_size=file_size,
            file_hash=file_hash,
            file_metadata=metadata or {}
        )

    @classmethod
    def create_log_result(
        cls,
        build_task_id: str,
        file_path: str,
        file_size: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "BuildResult":
        """创建日志文件结果。"""
        return cls(
            build_task_id=build_task_id,
            file_type=FileType.LOG,
            file_path=file_path,
            file_size=file_size,
            file_metadata=metadata or {}
        )

    @classmethod
    def create_metadata_result(
        cls,
        build_task_id: str,
        file_path: str,
        file_size: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "BuildResult":
        """创建元数据文件结果。"""
        return cls(
            build_task_id=build_task_id,
            file_type=FileType.METADATA,
            file_path=file_path,
            file_size=file_size,
            file_metadata=metadata or {}
        )
