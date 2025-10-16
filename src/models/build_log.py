"""
Build日志数据模型。

用于存储构建过程中的详细日志信息。
"""

import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from uuid import UUID, uuid4

from ..config.database import Base

logger = logging.getLogger(__name__)


class LogLevel(str, Enum):
    """日志级别枚举。"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    DEBUG = "debug"


class BuildLog(Base):
    """构建日志模型。"""

    __tablename__ = "build_logs"

    # 基础字段
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    build_task_id = Column(String(36), ForeignKey("build_tasks.id", ondelete="CASCADE"), nullable=False)

    # 日志信息
    log_level = Column(String(10), nullable=False, comment="日志级别")
    timestamp = Column(DateTime(timezone=True), nullable=False, comment="时间戳")
    message = Column(Text, nullable=False, comment="日志消息")
    source = Column(String(100), nullable=True, comment="日志来源")
    line_number = Column(Integer, nullable=True, comment="行号")

    # 元数据
    log_metadata = Column(Text, nullable=True, comment="日志元数据JSON")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")

    # 关系
    build_task = relationship("BuildTask", back_populates="build_logs")

    def __repr__(self) -> str:
        return f"<BuildLog(id={self.id}, level={self.log_level}, task_id={self.build_task_id})>"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式。"""
        # 尝试解析log_metadata为JSON,如果失败则返回原始字符串
        metadata = None
        if self.log_metadata:
            try:
                metadata = json.loads(self.log_metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = self.log_metadata

        return {
            "id": str(self.id),
            "build_task_id": str(self.build_task_id),
            "log_level": self.log_level,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "message": self.message,
            "source": self.source,
            "line_number": self.line_number,
            "metadata": metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    @classmethod
    def create_log(
        cls,
        build_task_id: str,
        message: str,
        log_level: LogLevel = LogLevel.INFO,
        source: Optional[str] = None,
        line_number: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ) -> "BuildLog":
        """创建构建日志。"""
        return cls(
            build_task_id=build_task_id,
            log_level=log_level.value,
            timestamp=timestamp or datetime.utcnow(),
            message=message,
            source=source,
            line_number=line_number,
            log_metadata=json.dumps(metadata, ensure_ascii=False) if metadata else None
        )

    @classmethod
    def create_info_log(
        cls,
        build_task_id: str,
        message: str,
        source: Optional[str] = None,
        line_number: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "BuildLog":
        """创建信息级别日志。"""
        return cls.create_log(
            build_task_id=build_task_id,
            message=message,
            log_level=LogLevel.INFO,
            source=source,
            line_number=line_number,
            metadata=metadata
        )

    @classmethod
    def create_warning_log(
        cls,
        build_task_id: str,
        message: str,
        source: Optional[str] = None,
        line_number: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "BuildLog":
        """创建警告级别日志。"""
        return cls.create_log(
            build_task_id=build_task_id,
            message=message,
            log_level=LogLevel.WARNING,
            source=source,
            line_number=line_number,
            metadata=metadata
        )

    @classmethod
    def create_error_log(
        cls,
        build_task_id: str,
        message: str,
        source: Optional[str] = None,
        line_number: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "BuildLog":
        """创建错误级别日志。"""
        return cls.create_log(
            build_task_id=build_task_id,
            message=message,
            log_level=LogLevel.ERROR,
            source=source,
            line_number=line_number,
            metadata=metadata
        )

    @classmethod
    def create_debug_log(
        cls,
        build_task_id: str,
        message: str,
        source: Optional[str] = None,
        line_number: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "BuildLog":
        """创建调试级别日志。"""
        return cls.create_log(
            build_task_id=build_task_id,
            message=message,
            log_level=LogLevel.DEBUG,
            source=source,
            line_number=line_number,
            metadata=metadata
        )

    @classmethod
    def parse_gradle_output(
        cls,
        build_task_id: str,
        gradle_output: str,
        source: str = "gradle"
    ) -> list["BuildLog"]:
        """解析Gradle输出并创建日志记录。"""
        logs = []
        lines = gradle_output.split('\n')

        for line_number, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue

            # 解析日志级别
            log_level = LogLevel.INFO
            if line.startswith('FAILURE:'):
                log_level = LogLevel.ERROR
            elif line.startswith('WARNING:'):
                log_level = LogLevel.WARNING
            elif ':error:' in line.lower():
                log_level = LogLevel.ERROR
            elif ':warn:' in line.lower():
                log_level = LogLevel.WARNING
            elif ':debug:' in line.lower():
                log_level = LogLevel.DEBUG

            logs.append(cls.create_log(
                build_task_id=build_task_id,
                message=line,
                log_level=log_level,
                source=source,
                line_number=line_number
            ))

        return logs

    @classmethod
    def create_build_start_log(cls, build_task_id: str, build_type: str) -> "BuildLog":
        """创建构建开始日志。"""
        message = f"开始执行{build_type}任务"
        return cls.create_info_log(
            build_task_id=build_task_id,
            message=message,
            source="build_system",
            metadata={"build_type": build_type, "event": "build_start"}
        )

    @classmethod
    def create_build_complete_log(cls, build_task_id: str, build_type: str, success: bool = True) -> "BuildLog":
        """创建构建完成日志。"""
        status = "成功" if success else "失败"
        message = f"{build_type}任务执行{status}"
        log_level = LogLevel.INFO if success else LogLevel.ERROR

        metadata = {"build_type": build_type, "success": success, "event": "build_complete"}

        return cls(
            build_task_id=build_task_id,
            message=message,
            log_level=log_level.value,
            source="build_system",
            timestamp=datetime.utcnow(),
            log_metadata=json.dumps(metadata, ensure_ascii=False)
        )

    @classmethod
    def create_progress_log(cls, build_task_id: str, progress: int, step_description: str) -> "BuildLog":
        """创建进度日志。"""
        # 不添加 [progress%] 前缀，只输出步骤描述
        message = step_description
        return cls.create_info_log(
            build_task_id=build_task_id,
            message=message,
            source="progress_tracker",
            metadata={"progress": progress, "step": step_description, "event": "progress_update"}
        )