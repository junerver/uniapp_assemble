"""
Android项目构建工具 - 数据库迁移和版本管理

提供：
1. 数据库版本控制系统
2. 自动化迁移脚本
3. 回滚机制
4. 迁移历史追踪
5. 数据备份和恢复
6. 数据一致性检查
"""

import json
import logging
import os
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

from sqlalchemy import text, inspect
from sqlalchemy.orm import Session

from .database import db_manager, DatabaseService
from .models import Base

logger = logging.getLogger(__name__)


class Migration:
    """单个迁移类"""

    def __init__(
        self,
        version: int,
        description: str,
        up_sql: str,
        down_sql: str,
        dependencies: Optional[List[int]] = None,
        pre_check: Optional[str] = None,
        post_check: Optional[str] = None
    ):
        """
        初始化迁移

        Args:
            version: 迁移版本号
            description: 迁移描述
            up_sql: 升级SQL
            down_sql: 回滚SQL
            dependencies: 依赖的迁移版本
            pre_check: 前置检查SQL
            post_check: 后置检查SQL
        """
        self.version = version
        self.description = description
        self.up_sql = up_sql.strip()
        self.down_sql = down_sql.strip()
        self.dependencies = dependencies or []
        self.pre_check = pre_check
        self.post_check = post_check
        self.created_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'version': self.version,
            'description': self.description,
            'up_sql': self.up_sql,
            'down_sql': self.down_sql,
            'dependencies': self.dependencies,
            'pre_check': self.pre_check,
            'post_check': self.post_check,
            'created_at': self.created_at.isoformat()
        }


class MigrationManager:
    """迁移管理器 - 负责数据库版本控制和迁移执行"""

    def __init__(self, db_service: DatabaseService, migrations_dir: str = "migrations"):
        """
        初始化迁移管理器

        Args:
            db_service: 数据库服务
            migrations_dir: 迁移文件目录
        """
        self.db_service = db_service
        self.migrations_dir = Path(migrations_dir)
        self.migrations_dir.mkdir(exist_ok=True)
        self._migrations: Dict[int, Migration] = {}
        self._initialize_migration_table()
        self._load_migrations()

    def _initialize_migration_table(self) -> None:
        """初始化迁移记录表"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS migration_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version INTEGER NOT NULL UNIQUE,
            description TEXT NOT NULL,
            applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            execution_time_ms INTEGER,
            success BOOLEAN DEFAULT TRUE,
            error_message TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_migration_version ON migration_history(version);
        CREATE INDEX IF NOT EXISTS idx_migration_applied ON migration_history(applied_at);
        """

        try:
            with self.db_service.transaction() as session:
                session.execute(text(create_table_sql))
            logger.info("迁移记录表初始化完成")
        except Exception as e:
            logger.error(f"初始化迁移记录表失败: {e}")
            raise

    def _load_migrations(self) -> None:
        """加载所有迁移文件"""
        self._migrations.clear()

        # 加载内置迁移
        self._register_builtin_migrations()

        # 加载文件系统中的迁移
        for migration_file in self.migrations_dir.glob("*.json"):
            try:
                with open(migration_file, 'r', encoding='utf-8') as f:
                    migration_data = json.load(f)
                    migration = Migration(**migration_data)
                    self._migrations[migration.version] = migration
                    logger.debug(f"加载迁移文件: {migration_file.name}")
            except Exception as e:
                logger.error(f"加载迁移文件失败 {migration_file}: {e}")

        logger.info(f"加载了 {len(self._migrations)} 个迁移")

    def _register_builtin_migrations(self) -> None:
        """注册内置迁移"""

        # 版本1: 初始数据库schema
        migration_v1 = Migration(
            version=1,
            description="初始数据库schema创建",
            up_sql="""
            -- 创建所有基础表
            -- 这里已经通过schema.sql创建了基础表
            -- 只记录版本信息
            INSERT OR IGNORE INTO schema_version (version, description) VALUES (1, '初始数据库schema');
            """,
            down_sql="""
            -- 删除所有表（危险操作，仅用于开发环境）
            DROP TABLE IF EXISTS system_metrics;
            DROP TABLE IF EXISTS project_configurations;
            DROP TABLE IF EXISTS git_operations;
            DROP TABLE IF EXISTS build_artifacts;
            DROP TABLE IF EXISTS build_logs;
            DROP TABLE IF EXISTS builds;
            DROP TABLE IF EXISTS projects;
            DROP TABLE IF EXISTS schema_version;
            """,
            pre_check="""
            SELECT COUNT(*) as table_count FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'migration_%';
            """,
            post_check="""
            SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;
            """
        )
        self._migrations[1] = migration_v1

        # 版本2: 添加构建优化索引
        migration_v2 = Migration(
            version=2,
            description="添加构建性能优化索引",
            up_sql="""
            -- 为构建表添加复合索引
            CREATE INDEX IF NOT EXISTS idx_builds_performance_1 ON builds(status, started_at DESC);
            CREATE INDEX IF NOT EXISTS idx_builds_performance_2 ON builds(project_id, status, started_at DESC);

            -- 为构建日志表添加分区索引
            CREATE INDEX IF NOT EXISTS idx_build_logs_partition_1 ON build_logs(build_id, timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_build_logs_partition_2 ON build_logs(level, timestamp DESC);

            -- 添加数据库统计视图
            CREATE VIEW IF NOT EXISTS build_performance_stats AS
            SELECT
                project_id,
                AVG(duration_seconds) as avg_duration,
                MAX(duration_seconds) as max_duration,
                MIN(duration_seconds) as min_duration,
                COUNT(*) as total_builds,
                COUNT(CASE WHEN status = 'success' THEN 1 END) as success_count
            FROM builds
            WHERE duration_seconds IS NOT NULL
            GROUP BY project_id;
            """,
            down_sql="""
            DROP VIEW IF EXISTS build_performance_stats;
            DROP INDEX IF EXISTS idx_build_logs_partition_2;
            DROP INDEX IF EXISTS idx_build_logs_partition_1;
            DROP INDEX IF EXISTS idx_builds_performance_2;
            DROP INDEX IF EXISTS idx_builds_performance_1;
            """,
            dependencies=[1]
        )
        self._migrations[2] = migration_v2

        # 版本3: 添加数据清理机制
        migration_v3 = Migration(
            version=3,
            description="添加数据清理和维护机制",
            up_sql="""
            -- 创建数据清理配置表
            CREATE TABLE IF NOT EXISTS cleanup_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name VARCHAR(100) NOT NULL,
                retention_days INTEGER NOT NULL DEFAULT 90,
                cleanup_column VARCHAR(100) NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            -- 插入默认清理配置
            INSERT OR IGNORE INTO cleanup_config (table_name, retention_days, cleanup_column) VALUES
            ('build_logs', 90, 'timestamp'),
            ('system_metrics', 30, 'timestamp'),
            ('builds', 180, 'completed_at');

            -- 创建清理历史记录表
            CREATE TABLE IF NOT EXISTS cleanup_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name VARCHAR(100) NOT NULL,
                records_deleted INTEGER NOT NULL,
                cleanup_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                retention_days INTEGER
            );

            -- 添加清理触发器
            CREATE TRIGGER IF NOT EXISTS auto_cleanup_build_logs
            AFTER INSERT ON build_logs
            WHEN (SELECT COUNT(*) FROM build_logs) > 100000
            BEGIN
                DELETE FROM build_logs
                WHERE timestamp < datetime('now', '-90 days')
                AND id NOT IN (
                    SELECT id FROM build_logs
                    ORDER BY timestamp DESC
                    LIMIT 50000
                );
            END;
            """,
            down_sql="""
            DROP TRIGGER IF EXISTS auto_cleanup_build_logs;
            DROP TABLE IF EXISTS cleanup_history;
            DROP TABLE IF EXISTS cleanup_config;
            """,
            dependencies=[2]
        )
        self._migrations[3] = migration_v3

    def get_current_version(self) -> int:
        """获取当前数据库版本"""
        try:
            with self.db_service.transaction() as session:
                result = session.execute(
                    text("SELECT MAX(version) FROM migration_history WHERE success = TRUE")
                )
                current_version = result.scalar() or 0
                logger.debug(f"当前数据库版本: {current_version}")
                return current_version
        except Exception as e:
            logger.error(f"获取当前数据库版本失败: {e}")
            return 0

    def get_pending_migrations(self) -> List[Migration]:
        """获取待执行的迁移"""
        current_version = self.get_current_version()
        pending = []

        for version, migration in sorted(self._migrations.items()):
            if version > current_version:
                # 检查依赖是否满足
                dependencies_met = all(
                    dep <= current_version for dep in migration.dependencies
                )
                if dependencies_met:
                    pending.append(migration)
                else:
                    logger.warning(f"迁移 {version} 的依赖未满足: {migration.dependencies}")

        return pending

    def execute_migration(self, migration: Migration) -> Tuple[bool, str]:
        """
        执行单个迁移

        Args:
            migration: 要执行的迁移

        Returns:
            (是否成功, 错误消息)
        """
        start_time = datetime.utcnow()

        try:
            with self.db_service.transaction() as session:
                # 前置检查
                if migration.pre_check:
                    try:
                        result = session.execute(text(migration.pre_check))
                        logger.debug(f"迁移 {migration.version} 前置检查通过")
                    except Exception as e:
                        error_msg = f"前置检查失败: {e}"
                        logger.error(error_msg)
                        return False, error_msg

                # 执行迁移SQL
                if migration.up_sql:
                    session.execute(text(migration.up_sql))
                    logger.info(f"执行迁移 {migration.version}: {migration.description}")

                # 记录迁移历史
                execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                session.execute(
                    text("""
                    INSERT INTO migration_history
                    (version, description, applied_at, execution_time_ms, success)
                    VALUES (:version, :description, :applied_at, :execution_time_ms, TRUE)
                    """),
                    {
                        'version': migration.version,
                        'description': migration.description,
                        'applied_at': start_time,
                        'execution_time_ms': execution_time
                    }
                )

                # 后置检查
                if migration.post_check:
                    try:
                        result = session.execute(text(migration.post_check))
                        logger.debug(f"迁移 {migration.version} 后置检查通过")
                    except Exception as e:
                        error_msg = f"后置检查失败: {e}"
                        logger.error(error_msg)
                        return False, error_msg

                logger.info(f"迁移 {migration.version} 执行成功，耗时 {execution_time:.2f}ms")
                return True, ""

        except Exception as e:
            error_msg = f"迁移执行失败: {e}"
            logger.error(error_msg)

            # 记录失败历史
            try:
                with self.db_service.transaction() as session:
                    execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                    session.execute(
                        text("""
                        INSERT INTO migration_history
                        (version, description, applied_at, execution_time_ms, success, error_message)
                        VALUES (:version, :description, :applied_at, :execution_time_ms, FALSE, :error_message)
                        """),
                        {
                            'version': migration.version,
                            'description': migration.description,
                            'applied_at': start_time,
                            'execution_time_ms': execution_time,
                            'error_message': error_msg
                        }
                    )
            except Exception as record_error:
                logger.error(f"记录迁移失败历史时出错: {record_error}")

            return False, error_msg

    def rollback_migration(self, version: int) -> Tuple[bool, str]:
        """
        回滚迁移

        Args:
            version: 要回滚的版本号

        Returns:
            (是否成功, 错误消息)
        """
        if version not in self._migrations:
            return False, f"迁移版本 {version} 不存在"

        migration = self._migrations[version]

        if not migration.down_sql:
            return False, f"迁移版本 {version} 不支持回滚"

        try:
            with self.db_service.transaction() as session:
                # 检查是否可以回滚
                current_version = self.get_current_version()
                if version > current_version:
                    return False, f"无法回滚未来版本 {version}，当前版本 {current_version}"

                # 检查是否有更新的迁移依赖此迁移
                for v, m in self._migrations.items():
                    if v > version and version in m.dependencies:
                        return False, f"迁移 {v} 依赖此迁移，无法回滚"

                # 执行回滚SQL
                session.execute(text(migration.down_sql))

                # 删除迁移历史记录
                session.execute(
                    text("DELETE FROM migration_history WHERE version = :version"),
                    {'version': version}
                )

                logger.info(f"成功回滚迁移 {version}: {migration.description}")
                return True, ""

        except Exception as e:
            error_msg = f"回滚迁移失败: {e}"
            logger.error(error_msg)
            return False, error_msg

    def migrate_up(self, target_version: Optional[int] = None) -> Tuple[bool, str]:
        """
        执行升级迁移

        Args:
            target_version: 目标版本，None表示升级到最新版本

        Returns:
            (是否成功, 错误消息)
        """
        current_version = self.get_current_version()
        pending_migrations = self.get_pending_migrations()

        if not pending_migrations:
            logger.info("没有待执行的迁移")
            return True, ""

        # 过滤到目标版本
        if target_version is not None:
            pending_migrations = [m for m in pending_migrations if m.version <= target_version]

        logger.info(f"开始执行 {len(pending_migrations)} 个迁移，当前版本: {current_version}")

        for migration in pending_migrations:
            success, error_msg = self.execute_migration(migration)
            if not success:
                return False, f"迁移 {migration.version} 失败: {error_msg}"

        final_version = self.get_current_version()
        logger.info(f"迁移完成，最终版本: {final_version}")
        return True, ""

    def migrate_down(self, target_version: int) -> Tuple[bool, str]:
        """
        执行降级迁移

        Args:
            target_version: 目标版本

        Returns:
            (是否成功, 错误消息)
        """
        current_version = self.get_current_version()

        if target_version >= current_version:
            return False, f"目标版本 {target_version} 大于等于当前版本 {current_version}"

        # 获取需要回滚的迁移（按版本降序）
        migrations_to_rollback = []
        for version in sorted(self._migrations.keys(), reverse=True):
            if target_version < version <= current_version:
                migrations_to_rollback.append(self._migrations[version])

        logger.info(f"开始回滚到版本 {target_version}，需要回滚 {len(migrations_to_rollback)} 个迁移")

        for migration in migrations_to_rollback:
            success, error_msg = self.rollback_migration(migration.version)
            if not success:
                return False, f"回滚迁移 {migration.version} 失败: {error_msg}"

        logger.info(f"回滚完成，当前版本: {target_version}")
        return True, ""

    def get_migration_history(self) -> List[Dict[str, Any]]:
        """获取迁移历史"""
        try:
            with self.db_service.transaction() as session:
                result = session.execute(
                    text("""
                    SELECT version, description, applied_at, execution_time_ms, success, error_message
                    FROM migration_history
                    ORDER BY version DESC
                    """)
                )
                return [dict(row) for row in result]
        except Exception as e:
            logger.error(f"获取迁移历史失败: {e}")
            return []

    def validate_migrations(self) -> Tuple[bool, List[str]]:
        """
        验证迁移完整性

        Returns:
            (是否有效, 错误消息列表)
        """
        errors = []

        try:
            # 检查版本连续性
            versions = sorted(self._migrations.keys())
            for i in range(1, len(versions)):
                if versions[i] != versions[i-1] + 1:
                    errors.append(f"版本不连续: {versions[i-1]} -> {versions[i]}")

            # 检查依赖关系
            for version, migration in self._migrations.items():
                for dep in migration.dependencies:
                    if dep not in self._migrations:
                        errors.append(f"迁移 {version} 依赖不存在的版本 {dep}")

            # 检查当前数据库状态
            current_version = self.get_current_version()
            applied_versions = set()
            try:
                with self.db_service.transaction() as session:
                    result = session.execute(
                        text("SELECT version FROM migration_history WHERE success = TRUE")
                    )
                    applied_versions = {row[0] for row in result}
            except Exception as e:
                errors.append(f"无法获取已应用的迁移版本: {e}")

            # 检查是否有未应用的迁移
            for version in range(1, current_version + 1):
                if version not in applied_versions:
                    errors.append(f"版本 {version} 在数据库中缺失")

            return len(errors) == 0, errors

        except Exception as e:
            return False, [f"验证迁移时出错: {e}"]

    def export_migrations(self, export_path: str) -> bool:
        """导出迁移配置到文件"""
        try:
            export_data = {
                'exported_at': datetime.utcnow().isoformat(),
                'current_version': self.get_current_version(),
                'migrations': {v: m.to_dict() for v, m in self._migrations.items()}
            }

            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            logger.info(f"迁移配置已导出到: {export_path}")
            return True

        except Exception as e:
            logger.error(f"导出迁移配置失败: {e}")
            return False

    def import_migrations(self, import_path: str) -> bool:
        """从文件导入迁移配置"""
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)

            imported_migrations = {}
            for version_str, migration_data in import_data['migrations'].items():
                version = int(version_str)
                migration = Migration(**migration_data)
                imported_migrations[version] = migration

            # 保存到文件系统
            for version, migration in imported_migrations.items():
                migration_file = self.migrations_dir / f"migration_{version:04d}.json"
                with open(migration_file, 'w', encoding='utf-8') as f:
                    json.dump(migration.to_dict(), f, indent=2, ensure_ascii=False)

            # 重新加载迁移
            self._load_migrations()

            logger.info(f"从 {import_path} 导入了 {len(imported_migrations)} 个迁移")
            return True

        except Exception as e:
            logger.error(f"导入迁移配置失败: {e}")
            return False


# ================================
# 数据备份和恢复
# ================================

class BackupManager:
    """数据备份管理器"""

    def __init__(self, db_service: DatabaseService, backup_dir: str = "backups"):
        """
        初始化备份管理器

        Args:
            db_service: 数据库服务
            backup_dir: 备份目录
        """
        self.db_service = db_service
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)

    def create_backup(self, backup_name: Optional[str] = None) -> Optional[str]:
        """
        创建数据库备份

        Args:
            backup_name: 备份名称，None表示使用时间戳

        Returns:
            备份文件路径，失败返回None
        """
        if backup_name is None:
            backup_name = f"backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        backup_file = self.backup_dir / f"{backup_name}.db"

        try:
            # 对于SQLite，直接复制文件
            if hasattr(db_manager.engine, 'url') and db_manager.engine.url.drivername == 'sqlite':
                source_db = db_manager.engine.url.database
                if source_db and os.path.exists(source_db):
                    shutil.copy2(source_db, backup_file)
                    logger.info(f"数据库备份完成: {backup_file}")
                    return str(backup_file)
                else:
                    logger.error("源数据库文件不存在")
                    return None
            else:
                # 对于其他数据库，使用SQL导出
                return self._sql_export_backup(backup_file)

        except Exception as e:
            logger.error(f"创建备份失败: {e}")
            return None

    def _sql_export_backup(self, backup_file: Path) -> Optional[str]:
        """使用SQL导出方式创建备份"""
        try:
            with self.db_service.transaction() as session:
                # 获取所有表
                inspector = inspect(session.bind)
                tables = inspector.get_table_names()

                backup_data = {
                    'backup_time': datetime.utcnow().isoformat(),
                    'tables': {}
                }

                for table in tables:
                    try:
                        result = session.execute(text(f"SELECT * FROM {table}"))
                        backup_data['tables'][table] = [dict(row) for row in result]
                        logger.debug(f"备份表 {table}: {len(backup_data['tables'][table])} 条记录")
                    except Exception as e:
                        logger.warning(f"备份表 {table} 失败: {e}")

                # 保存为JSON格式
                backup_file_json = backup_file.with_suffix('.json')
                with open(backup_file_json, 'w', encoding='utf-8') as f:
                    json.dump(backup_data, f, indent=2, ensure_ascii=False)

                logger.info(f"数据库备份完成: {backup_file_json}")
                return str(backup_file_json)

        except Exception as e:
            logger.error(f"SQL导出备份失败: {e}")
            return None

    def restore_backup(self, backup_path: str) -> bool:
        """
        恢复数据库备份

        Args:
            backup_path: 备份文件路径

        Returns:
            是否成功
        """
        backup_file = Path(backup_path)

        if not backup_file.exists():
            logger.error(f"备份文件不存在: {backup_path}")
            return False

        try:
            # 关闭当前数据库连接
            db_manager.close()

            if backup_file.suffix == '.db':
                # SQLite文件备份
                target_db = db_manager.engine.url.database
                if target_db:
                    shutil.copy2(backup_file, target_db)
                    logger.info(f"数据库恢复完成: {target_db}")
                    return True
                else:
                    logger.error("无法确定目标数据库路径")
                    return False

            elif backup_file.suffix == '.json':
                # JSON格式备份
                return self._sql_import_restore(backup_file)

            else:
                logger.error(f"不支持的备份文件格式: {backup_file.suffix}")
                return False

        except Exception as e:
            logger.error(f"恢复备份失败: {e}")
            return False

    def _sql_import_restore(self, backup_file: Path) -> bool:
        """从JSON备份恢复数据库"""
        try:
            with open(backup_file, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)

            # 重新初始化数据库连接
            db_manager.initialize()

            with self.db_service.transaction() as session:
                # 清空所有表（除了迁移历史）
                inspector = inspect(session.bind)
                tables = inspector.get_table_names()

                for table in tables:
                    if table != 'migration_history':
                        try:
                            session.execute(text(f"DELETE FROM {table}"))
                            logger.debug(f"清空表 {table}")
                        except Exception as e:
                            logger.warning(f"清空表 {table} 失败: {e}")

                # 恢复数据
                for table_name, records in backup_data['tables'].items():
                    if records and table_name != 'migration_history':
                        try:
                            # 获取表结构
                            columns = list(records[0].keys())
                            placeholders = ', '.join([f':{col}' for col in columns])
                            columns_str = ', '.join(columns)

                            # 批量插入
                            session.execute(
                                text(f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"),
                                records
                            )
                            logger.debug(f"恢复表 {table_name}: {len(records)} 条记录")
                        except Exception as e:
                            logger.error(f"恢复表 {table_name} 失败: {e}")

            logger.info(f"数据库恢复完成: {backup_file}")
            return True

        except Exception as e:
            logger.error(f"JSON备份恢复失败: {e}")
            return False

    def list_backups(self) -> List[Dict[str, Any]]:
        """列出所有备份文件"""
        backups = []

        for backup_file in self.backup_dir.glob("*"):
            if backup_file.is_file():
                stat = backup_file.stat()
                backups.append({
                    'name': backup_file.name,
                    'path': str(backup_file),
                    'size': stat.st_size,
                    'created_at': datetime.fromtimestamp(stat.st_ctime),
                    'modified_at': datetime.fromtimestamp(stat.st_mtime)
                })

        return sorted(backups, key=lambda x: x['created_at'], reverse=True)

    def cleanup_old_backups(self, keep_days: int = 30, keep_count: int = 10) -> int:
        """
        清理旧备份

        Args:
            keep_days: 保留天数
            keep_count: 最少保留数量

        Returns:
            删除的文件数量
        """
        cutoff_time = datetime.now().timestamp() - (keep_days * 24 * 3600)
        backups = self.list_backups()

        # 按时间排序，保留最新的keep_count个
        backups_to_keep = set()
        for backup in backups[:keep_count]:
            backups_to_keep.add(backup['path'])

        deleted_count = 0
        for backup in backups[keep_count:]:
            if backup['created_at'].timestamp() < cutoff_time and backup['path'] not in backups_to_keep:
                try:
                    os.remove(backup['path'])
                    deleted_count += 1
                    logger.info(f"删除旧备份: {backup['name']}")
                except Exception as e:
                    logger.error(f"删除备份文件失败 {backup['name']}: {e}")

        logger.info(f"清理完成，删除了 {deleted_count} 个旧备份")
        return deleted_count


# ================================
# 全局实例
# ================================

# 创建全局迁移管理器
migration_manager = MigrationManager(database_service)

# 创建全局备份管理器
backup_manager = BackupManager(database_service)

# 导出常用函数
def migrate_to_latest() -> bool:
    """迁移到最新版本"""
    success, error_msg = migration_manager.migrate_up()
    if not success:
        logger.error(f"迁移失败: {error_msg}")
    return success

def check_database_health() -> Dict[str, Any]:
    """检查数据库健康状态"""
    health = database_service.health_check()

    # 添加迁移状态
    current_version = migration_manager.get_current_version()
    pending_migrations = len(migration_manager.get_pending_migrations())

    health.update({
        'migration_version': current_version,
        'pending_migrations': pending_migrations,
        'migration_status': 'up_to_date' if pending_migrations == 0 else 'needs_migration'
    })

    return health