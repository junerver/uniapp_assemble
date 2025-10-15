#!/usr/bin/env python3
"""
数据库初始化脚本。

创建所有必需的数据库表。
"""

import asyncio
import sys
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config.database import engine, AsyncSessionLocal
from src.models.base import BaseSQLModel
from src.models.android_project import AndroidProject
from src.models.project_config import ProjectConfig


async def init_database():
    """初始化数据库表。"""
    print("正在初始化数据库...")

    # 导入所有模型以确保它们被注册到BaseSQLModel.metadata
    print("导入模型...")

    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(BaseSQLModel.metadata.create_all)

    print("数据库初始化完成！")

    # 验证表是否创建成功
    from sqlalchemy import text
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        tables = result.fetchall()
        print(f"创建的表: {[table[0] for table in tables]}")


if __name__ == "__main__":
    asyncio.run(init_database())