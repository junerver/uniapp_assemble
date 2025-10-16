"""
Android项目配置模型。

定义Android项目的基本配置信息和相关操作。
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy.orm import relationship
from ..config.database import Base


class AndroidProject(Base):
    """Android项目配置模型。

    管理Android项目的基本配置信息，包括项目名称、路径、描述等。
    """

    __tablename__ = "android_projects"

    # 主键
    id: str = Column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # 基本信息
    name: str = Column(String(255), nullable=False, unique=True, index=True)
    alias: Optional[str] = Column(String(255), nullable=True)
    path: str = Column(Text, nullable=False)
    description: Optional[str] = Column(Text, nullable=True)

    # 状态
    is_active: bool = Column(Boolean, default=True, index=True)

    # 时间戳
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    build_tasks = relationship("BuildTask", back_populates="project", cascade="all, delete-orphan")


    def __repr__(self) -> str:
        return f"<AndroidProject(id={self.id}, name='{self.name}', path='{self.path}')>"

    @property
    def display_name(self) -> str:
        """获取显示名称。"""
        return self.alias or self.name

    def to_dict(self) -> dict:
        """转换为字典格式。"""
        return {
            "id": str(self.id),
            "name": self.name,
            "alias": self.alias,
            "path": self.path,
            "description": self.description,
            "is_active": self.is_active,
            "display_name": self.display_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }