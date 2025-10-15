"""
项目配置模型。

定义Android项目的详细配置信息，包括Git配置、构建配置等。
"""

import json
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from .base import BaseSQLModel


class ConfigType(str, Enum):
    """配置类型枚举。"""
    GIT = "git"
    BUILD = "build"
    CUSTOM = "custom"


class ProjectConfig(BaseSQLModel):
    """项目配置模型。

    存储项目的详细配置信息，支持多种配置类型。
    """

    __tablename__ = "project_configs"

    # 主键
    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # 外键
    project_id: str = Column(String(36), ForeignKey("android_projects.id", ondelete="CASCADE"), nullable=False)

    # 配置信息
    config_type: ConfigType = Column(String(50), nullable=False, index=True)
    _config_data: str = Column("config_data", Text, nullable=False, default="{}")
    is_default: bool = Column(Boolean, default=False)

    # 时间戳
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

  
    def __repr__(self) -> str:
        return f"<ProjectConfig(id={self.id}, project_id={self.project_id}, type='{self.config_type}')>"

    @hybrid_property
    def config_data(self) -> Dict[str, Any]:
        """获取配置数据（从JSON字符串解析）。"""
        try:
            if self._config_data:
                return json.loads(self._config_data)
            return {}
        except (json.JSONDecodeError, TypeError):
            return {}

    @config_data.setter
    def config_data(self, value: Dict[str, Any]) -> None:
        """设置配置数据（序列化为JSON字符串）。"""
        self._config_data = json.dumps(value, ensure_ascii=False)
        self.updated_at = datetime.utcnow()

    @property
    def config_name(self) -> str:
        """获取配置名称。"""
        return f"{self.config_type.value}_config"

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """获取配置值。"""
        return self.config_data.get(key, default)

    def set_config_value(self, key: str, value: Any) -> None:
        """设置配置值。"""
        current_data = self.config_data
        current_data[key] = value
        self.config_data = current_data

    def to_dict(self) -> dict:
        """转换为字典格式。"""
        return {
            "id": str(self.id),
            "project_id": str(self.project_id),
            "config_type": self.config_type.value,
            "config_data": self.config_data,
            "is_default": self.is_default,
            "config_name": self.config_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def create_git_config(cls, project_id: UUID, git_url: str, main_branch: str = "main", **kwargs) -> "ProjectConfig":
        """创建Git配置。"""
        config_data = {
            "git_url": git_url,
            "main_branch": main_branch,
            "auto_backup": kwargs.get("auto_backup", True),
            "commit_author": kwargs.get("commit_author", "Android Builder <builder@example.com>"),
            "max_commit_message_length": kwargs.get("max_commit_message_length", 1000),
        }
        return cls(
            project_id=project_id,
            config_type=ConfigType.GIT,
            config_data=config_data,
            is_default=kwargs.get("is_default", False),
        )

    @classmethod
    def create_build_config(cls, project_id: UUID, gradle_tasks: list, **kwargs) -> "ProjectConfig":
        """创建构建配置。"""
        config_data = {
            "gradle_tasks": gradle_tasks,
            "timeout": kwargs.get("timeout", 1800),  # 30分钟
            "max_concurrent_builds": kwargs.get("max_concurrent_builds", 3),
            "build_type": kwargs.get("build_type", "debug"),
            "output_dir": kwargs.get("output_dir", "build/outputs/apk/debug"),
        }
        return cls(
            project_id=project_id,
            config_type=ConfigType.BUILD,
            config_data=config_data,
            is_default=kwargs.get("is_default", False),
        )

    @classmethod
    def create_custom_config(cls, project_id: UUID, config_name: str, config_data: Dict[str, Any], **kwargs) -> "ProjectConfig":
        """创建自定义配置。"""
        return cls(
            project_id=project_id,
            config_type=ConfigType.CUSTOM,
            config_data={"name": config_name, **config_data},
            is_default=kwargs.get("is_default", False),
        )