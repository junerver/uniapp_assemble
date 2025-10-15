"""
Database initialization and migration utilities.

This module handles database schema creation, migrations, and initial data setup
for the Android build tool application.
"""

import logging
from pathlib import Path
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config.database import get_async_session, get_engine
from ..config.settings import get_settings

logger = logging.getLogger(__name__)

# Database schema SQL statements
CREATE_TABLES_SQL = """
-- Android项目表
CREATE TABLE IF NOT EXISTS android_projects (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    alias TEXT,
    path TEXT NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 项目配置表
CREATE TABLE IF NOT EXISTS project_configs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    config_type TEXT NOT NULL CHECK (config_type IN ('git', 'build', 'custom')),
    config_data TEXT NOT NULL,  -- JSON data
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES android_projects(id) ON DELETE CASCADE
);

-- 构建任务表
CREATE TABLE IF NOT EXISTS build_tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    task_type TEXT NOT NULL CHECK (task_type IN ('resource_replace', 'build', 'extract_apk')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    progress INTEGER DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    result_data TEXT,  -- JSON data
    resource_package_path TEXT,
    git_branch TEXT,
    commit_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES android_projects(id) ON DELETE CASCADE
);

-- 构建日志表
CREATE TABLE IF NOT EXISTS build_logs (
    id TEXT PRIMARY KEY,
    build_task_id TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    level TEXT NOT NULL CHECK (level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR')),
    message TEXT NOT NULL,
    source TEXT,
    FOREIGN KEY (build_task_id) REFERENCES build_tasks(id) ON DELETE CASCADE
);

-- 构建结果表
CREATE TABLE IF NOT EXISTS build_results (
    id TEXT PRIMARY KEY,
    build_task_id TEXT NOT NULL,
    apk_files TEXT,  -- JSON array of APK file info
    build_size INTEGER,
    build_time_seconds INTEGER,
    success BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (build_task_id) REFERENCES build_tasks(id) ON DELETE CASCADE
);

-- Git操作记录表
CREATE TABLE IF NOT EXISTS git_operations (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    operation_type TEXT NOT NULL CHECK (operation_type IN ('commit', 'rollback', 'branch_checkout', 'merge')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    commit_hash TEXT,
    branch_name TEXT,
    commit_message TEXT,
    error_message TEXT,
    backup_path TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES android_projects(id) ON DELETE CASCADE
);

-- 仓库备份表
CREATE TABLE IF NOT EXISTS repository_backups (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    backup_path TEXT NOT NULL,
    backup_type TEXT NOT NULL CHECK (backup_type IN ('pre_operation', 'manual', 'auto')),
    commit_hash TEXT,
    branch_name TEXT,
    description TEXT,
    file_size INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES android_projects(id) ON DELETE CASCADE
);

-- APK文件表
CREATE TABLE IF NOT EXISTS apk_files (
    id TEXT PRIMARY KEY,
    build_result_id TEXT,
    project_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_size INTEGER,
    version_name TEXT,
    version_code INTEGER,
    package_name TEXT,
    min_sdk_version INTEGER,
    target_sdk_version INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (build_result_id) REFERENCES build_results(id) ON DELETE CASCADE,
    FOREIGN KEY (project_id) REFERENCES android_projects(id) ON DELETE CASCADE
);
"""

# Index creation statements
CREATE_INDEXES_SQL = """
-- 项目相关索引
CREATE INDEX IF NOT EXISTS idx_android_projects_name ON android_projects(name);
CREATE INDEX IF NOT EXISTS idx_android_projects_active ON android_projects(is_active);
CREATE INDEX IF NOT EXISTS idx_android_projects_created ON android_projects(created_at);

-- 项目配置索引
CREATE INDEX IF NOT EXISTS idx_project_configs_project_id ON project_configs(project_id);
CREATE INDEX IF NOT EXISTS idx_project_configs_type ON project_configs(config_type);
CREATE INDEX IF NOT EXISTS idx_project_configs_default ON project_configs(is_default);

-- 构建任务索引
CREATE INDEX IF NOT EXISTS idx_build_tasks_project_id ON build_tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_build_tasks_status ON build_tasks(status);
CREATE INDEX IF NOT EXISTS idx_build_tasks_type ON build_tasks(task_type);
CREATE INDEX IF NOT EXISTS idx_build_tasks_created ON build_tasks(created_at);
CREATE INDEX IF NOT EXISTS idx_build_tasks_branch ON build_tasks(git_branch);

-- 构建日志索引
CREATE INDEX IF NOT EXISTS idx_build_logs_task_id ON build_logs(build_task_id);
CREATE INDEX IF NOT EXISTS idx_build_logs_timestamp ON build_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_build_logs_level ON build_logs(level);

-- 构建结果索引
CREATE INDEX IF NOT EXISTS idx_build_results_task_id ON build_results(build_task_id);
CREATE INDEX IF NOT EXISTS idx_build_results_success ON build_results(success);

-- Git操作索引
CREATE INDEX IF NOT EXISTS idx_git_operations_project_id ON git_operations(project_id);
CREATE INDEX IF NOT EXISTS idx_git_operations_type ON git_operations(operation_type);
CREATE INDEX IF NOT EXISTS idx_git_operations_status ON git_operations(status);
CREATE INDEX IF NOT EXISTS idx_git_operations_created ON git_operations(created_at);

-- 仓库备份索引
CREATE INDEX IF NOT EXISTS idx_repository_backups_project_id ON repository_backups(project_id);
CREATE INDEX IF NOT EXISTS idx_repository_backups_type ON repository_backups(backup_type);
CREATE INDEX IF NOT EXISTS idx_repository_backups_expires ON repository_backups(expires_at);

-- APK文件索引
CREATE INDEX IF NOT EXISTS idx_apk_files_build_result_id ON apk_files(build_result_id);
CREATE INDEX IF NOT EXISTS idx_apk_files_project_id ON apk_files(project_id);
CREATE INDEX IF NOT EXISTS idx_apk_files_package_name ON apk_files(package_name);
CREATE INDEX IF NOT EXISTS idx_apk_files_created ON apk_files(created_at);
"""

# Triggers for automatic timestamp updates
CREATE_TRIGGERS_SQL = """
-- Android项目更新时间触发器
CREATE TRIGGER IF NOT EXISTS update_android_projects_timestamp
    AFTER UPDATE ON android_projects
    FOR EACH ROW
    BEGIN
        UPDATE android_projects SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

-- 项目配置更新时间触发器
CREATE TRIGGER IF NOT EXISTS update_project_configs_timestamp
    AFTER UPDATE ON project_configs
    FOR EACH ROW
    BEGIN
        UPDATE project_configs SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

-- 构建任务更新时间触发器
CREATE TRIGGER IF NOT EXISTS update_build_tasks_timestamp
    AFTER UPDATE ON build_tasks
    FOR EACH ROW
    BEGIN
        UPDATE build_tasks SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;

-- Git操作更新时间触发器
CREATE TRIGGER IF NOT EXISTS update_git_operations_timestamp
    AFTER UPDATE ON git_operations
    FOR EACH ROW
    BEGIN
        UPDATE git_operations SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;
"""


async def create_database_tables() -> bool:
    """
    Create all database tables and indexes.

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        async with get_async_session() as session:
            logger.info("Creating database tables...")

            # Create tables
            await session.execute(text(CREATE_TABLES_SQL))
            logger.info("Database tables created successfully")

            # Create indexes
            await session.execute(text(CREATE_INDEXES_SQL))
            logger.info("Database indexes created successfully")

            # Create triggers
            await session.execute(text(CREATE_TRIGGERS_SQL))
            logger.info("Database triggers created successfully")

            await session.commit()
            return True

    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        return False


async def check_database_exists() -> bool:
    """
    Check if database tables exist.

    Returns:
        bool: True if tables exist, False otherwise
    """
    try:
        async with get_async_session() as session:
            result = await session.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='android_projects'"
            ))
            return result.fetchone() is not None

    except Exception as e:
        logger.error(f"Failed to check database existence: {e}")
        return False


async def initialize_database() -> bool:
    """
    Initialize the database with all necessary tables and data.

    Returns:
        bool: True if initialization successful, False otherwise
    """
    logger.info("Initializing database...")

    try:
        # Check if database already exists
        if await check_database_exists():
            logger.info("Database already exists, checking schema...")
            # TODO: Add schema migration logic here if needed
            return True

        # Create database tables
        success = await create_database_tables()
        if success:
            logger.info("Database initialization completed successfully")
        else:
            logger.error("Database initialization failed")

        return success

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False


async def reset_database() -> bool:
    """
    Reset the database by dropping all tables and recreating them.

    WARNING: This will delete all data!

    Returns:
        bool: True if reset successful, False otherwise
    """
    logger.warning("Resetting database - all data will be deleted!")

    try:
        async with get_async_session() as session:
            # Get all table names
            result = await session.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ))
            tables = [row[0] for row in result.fetchall()]

            # Drop all tables
            for table in tables:
                await session.execute(text(f"DROP TABLE IF EXISTS {table}"))
                logger.info(f"Dropped table: {table}")

            await session.commit()

            # Recreate tables
            return await create_database_tables()

    except Exception as e:
        logger.error(f"Failed to reset database: {e}")
        return False


async def get_database_info() -> dict:
    """
    Get database information and statistics.

    Returns:
        dict: Database information
    """
    try:
        async with get_async_session() as session:
            info = {}

            # Get table counts
            tables = [
                "android_projects",
                "project_configs",
                "build_tasks",
                "build_logs",
                "build_results",
                "git_operations",
                "repository_backups",
                "apk_files"
            ]

            for table in tables:
                try:
                    result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar()
                    info[f"{table}_count"] = count
                except Exception:
                    info[f"{table}_count"] = 0

            # Get database size
            settings = get_settings()
            db_path = settings.database_path
            if db_path.exists():
                info["database_size_bytes"] = db_path.stat().st_size
                info["database_size_mb"] = round(info["database_size_bytes"] / (1024 * 1024), 2)

            return info

    except Exception as e:
        logger.error(f"Failed to get database info: {e}")
        return {}


async def cleanup_expired_backups() -> int:
    """
    Clean up expired repository backups.

    Returns:
        int: Number of backups cleaned up
    """
    try:
        async with get_async_session() as session:
            result = await session.execute(text("""
                DELETE FROM repository_backups
                WHERE expires_at IS NOT NULL AND expires_at < CURRENT_TIMESTAMP
            """))

            await session.commit()
            cleaned_count = result.rowcount

            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} expired backups")

            return cleaned_count

    except Exception as e:
        logger.error(f"Failed to cleanup expired backups: {e}")
        return 0


async def validate_database_schema() -> bool:
    """
    Validate that all required tables and columns exist.

    Returns:
        bool: True if schema is valid, False otherwise
    """
    try:
        async with get_async_session() as session:
            # Check if all required tables exist
            required_tables = [
                "android_projects",
                "project_configs",
                "build_tasks",
                "build_logs",
                "git_operations"
            ]

            for table in required_tables:
                result = await session.execute(text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
                ), (table,))

                if not result.fetchone():
                    logger.error(f"Missing required table: {table}")
                    return False

            logger.info("Database schema validation passed")
            return True

    except Exception as e:
        logger.error(f"Database schema validation failed: {e}")
        return False


# CLI functions for standalone execution
async def init_database_command() -> None:
    """Initialize database from command line."""
    success = await initialize_database()
    if success:
        print("✅ Database initialized successfully")
    else:
        print("❌ Database initialization failed")
        exit(1)


async def reset_database_command() -> None:
    """Reset database from command line."""
    confirm = input("⚠️  This will delete ALL data. Are you sure? (yes/no): ")
    if confirm.lower() != "yes":
        print("Operation cancelled")
        return

    success = await reset_database()
    if success:
        print("✅ Database reset successfully")
    else:
        print("❌ Database reset failed")
        exit(1)


async def info_database_command() -> None:
    """Show database information from command line."""
    info = await get_database_info()

    print("📊 Database Information:")
    for key, value in info.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    import asyncio
    import sys

    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "init":
            asyncio.run(init_database_command())
        elif command == "reset":
            asyncio.run(reset_database_command())
        elif command == "info":
            asyncio.run(info_database_command())
        else:
            print("Usage: python init_db.py [init|reset|info]")
    else:
        asyncio.run(init_database_command())