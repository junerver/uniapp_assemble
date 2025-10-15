"""
Android项目构建工具 - 数据库配置模块

提供：
1. 数据库连接配置
2. 性能优化配置
3. 存储优化配置
4. 迁移配置
5. 备份配置
"""

import os
from dataclasses import dataclass
from typing import Dict, Any, Optional
from pathlib import Path


@dataclass
class DatabaseConnectionConfig:
    """数据库连接配置"""
    driver: str = "sqlite"
    database: str = "android_build_tool.db"
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 3600

    def get_connection_url(self) -> str:
        """获取数据库连接URL"""
        if self.driver == "sqlite":
            return f"sqlite:///{self.database}"
        elif self.driver == "mysql":
            return f"mysql+pymysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        elif self.driver == "postgresql":
            return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        else:
            raise ValueError(f"不支持的数据库驱动: {self.driver}")


@dataclass
class SQLiteConfig:
    """SQLite特定配置"""
    journal_mode: str = "WAL"                    # 写前日志模式
    synchronous: str = "NORMAL"                  # 同步模式
    cache_size: int = -64000                     # 缓存大小 (64MB)
    temp_store: str = "MEMORY"                   # 临时表存储
    mmap_size: int = 268435456                   # 内存映射大小 (256MB)
    locking_mode: str = "NORMAL"                 # 锁定模式
    foreign_keys: bool = True                    # 外键约束
    query_only: bool = False                     # 只读模式
    wal_autocheckpoint: int = 1000               # WAL自动检查点

    def get_pragmas(self) -> Dict[str, Any]:
        """获取SQLite PRAGMA设置"""
        return {
            'journal_mode': self.journal_mode,
            'synchronous': self.synchronous,
            'cache_size': self.cache_size,
            'temp_store': self.temp_store,
            'mmap_size': self.mmap_size,
            'locking_mode': self.locking_mode,
            'foreign_keys': 'ON' if self.foreign_keys else 'OFF',
            'query_only': 'ON' if self.query_only else 'OFF',
            'wal_autocheckpoint': self.wal_autocheckpoint
        }


@dataclass
class PerformanceConfig:
    """性能优化配置"""
    query_timeout: int = 300                     # 查询超时时间（秒）
    batch_size: int = 1000                       # 批量操作大小
    slow_query_threshold: float = 1.0            # 慢查询阈值（秒）
    connection_pool_size: int = 5                # 连接池大小
    max_connections: int = 20                    # 最大连接数
    connection_timeout: int = 30                 # 连接超时时间
    session_timeout: int = 3600                  # 会话超时时间

    # 索引优化配置
    auto_create_indexes: bool = True             # 自动创建索引
    index_threshold: int = 1000                  # 索引阈值
    analyze_after_import: bool = True            # 导入后分析

    # 查询优化配置
    enable_query_cache: bool = True              # 启用查询缓存
    cache_size: int = 100                        # 缓存大小
    cache_ttl: int = 300                         # 缓存TTL（秒）


@dataclass
class StorageConfig:
    """存储优化配置"""
    compression_enabled: bool = True             # 启用压缩
    compression_strategy: str = "gzip"           # 压缩策略 (none/gzip/lzma)
    compression_level: int = 6                   # 压缩级别
    compression_threshold: int = 1024            # 压缩阈值（字节）

    # 归档配置
    archive_enabled: bool = True                 # 启用归档
    archive_threshold_days: int = 30             # 归档阈值（天）
    archive_table_suffix: str = "_archive"       # 归档表后缀

    # 清理配置
    cleanup_enabled: bool = True                 # 启用清理
    cleanup_retention_days: int = 90             # 清理保留天数
    cleanup_schedule_hours: int = 24             # 清理计划（小时）

    # 监控配置
    monitor_storage: bool = True                 # 监控存储
    storage_alert_threshold_mb: float = 1000.0   # 存储告警阈值（MB）


@dataclass
class MigrationConfig:
    """迁移配置"""
    auto_migrate: bool = True                    # 自动迁移
    migration_timeout: int = 300                 # 迁移超时时间（秒）
    backup_before_migrate: bool = True           # 迁移前备份
    validate_migrations: bool = True             # 验证迁移
    migration_table: str = "migration_history"   # 迁移历史表

    # 迁移目录配置
    migrations_dir: str = "migrations"           # 迁移文件目录
    builtin_migrations: bool = True              # 启用内置迁移

    # 回滚配置
    enable_rollback: bool = True                 # 启用回滚
    backup_rollback_data: bool = True            # 回滚前备份数据


@dataclass
class BackupConfig:
    """备份配置"""
    auto_backup: bool = True                     # 自动备份
    backup_schedule_hours: int = 24              # 备份计划（小时）
    backup_retention_days: int = 30              # 备份保留天数
    backup_dir: str = "backups"                  # 备份目录
    backup_compression: bool = True              # 备份压缩

    # 备份类型配置
    full_backup_interval: int = 7                # 完整备份间隔（天）
    incremental_backup: bool = True              # 增量备份
    differential_backup: bool = False            # 差异备份

    # 备份验证配置
    verify_backups: bool = True                  # 验证备份
    test_restore: bool = False                   # 测试恢复

    # 备份通知配置
    notify_on_success: bool = False              # 成功通知
    notify_on_failure: bool = True               # 失败通知


@dataclass
class LoggingConfig:
    """日志配置"""
    level: str = "INFO"                          # 日志级别
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_handler: bool = True                    # 文件处理器
    file_path: str = "logs/database.log"         # 日志文件路径
    max_file_size_mb: int = 10                   # 最大文件大小（MB）
    backup_count: int = 5                        # 备份文件数量
    console_handler: bool = True                 # 控制台处理器

    # SQL日志配置
    log_sql: bool = False                        # 记录SQL
    log_slow_queries: bool = True                # 记录慢查询
    slow_query_threshold: float = 1.0            # 慢查询阈值（秒）

    # 审计日志配置
    audit_enabled: bool = True                   # 启用审计
    audit_file: str = "logs/audit.log"           # 审计日志文件
    audit_operations: list = None                # 审计操作列表

    def __post_init__(self):
        if self.audit_operations is None:
            self.audit_operations = ["INSERT", "UPDATE", "DELETE"]


@dataclass
class SecurityConfig:
    """安全配置"""
    encrypt_sensitive_data: bool = True          # 加密敏感数据
    encryption_key: Optional[str] = None         # 加密密钥
    hash_passwords: bool = True                  # 哈希密码

    # 访问控制配置
    enable_access_control: bool = False          # 启用访问控制
    session_timeout: int = 3600                  # 会话超时（秒）
    max_login_attempts: int = 5                  # 最大登录尝试次数
    lockout_duration: int = 900                  # 锁定时长（秒）

    # 数据保护配置
    anonymize_logs: bool = False                 # 匿名化日志
    mask_sensitive_fields: bool = True           # 屏蔽敏感字段
    data_retention_policy: int = 2555            # 数据保留策略（天）


class DatabaseConfig:
    """总数据库配置类"""

    def __init__(self, config_file: Optional[str] = None):
        """
        初始化数据库配置

        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file

        # 加载默认配置
        self.connection = DatabaseConnectionConfig()
        self.sqlite = SQLiteConfig()
        self.performance = PerformanceConfig()
        self.storage = StorageConfig()
        self.migration = MigrationConfig()
        self.backup = BackupConfig()
        self.logging = LoggingConfig()
        self.security = SecurityConfig()

        # 从环境变量加载配置
        self._load_from_env()

        # 从配置文件加载配置
        if config_file and os.path.exists(config_file):
            self._load_from_file(config_file)

    def _load_from_env(self) -> None:
        """从环境变量加载配置"""
        # 数据库连接配置
        if os.getenv("DB_DRIVER"):
            self.connection.driver = os.getenv("DB_DRIVER")
        if os.getenv("DB_DATABASE"):
            self.connection.database = os.getenv("DB_DATABASE")
        if os.getenv("DB_HOST"):
            self.connection.host = os.getenv("DB_HOST")
        if os.getenv("DB_PORT"):
            self.connection.port = int(os.getenv("DB_PORT"))
        if os.getenv("DB_USERNAME"):
            self.connection.username = os.getenv("DB_USERNAME")
        if os.getenv("DB_PASSWORD"):
            self.connection.password = os.getenv("DB_PASSWORD")

        # 性能配置
        if os.getenv("DB_POOL_SIZE"):
            self.performance.connection_pool_size = int(os.getenv("DB_POOL_SIZE"))
        if os.getenv("DB_QUERY_TIMEOUT"):
            self.performance.query_timeout = int(os.getenv("DB_QUERY_TIMEOUT"))

        # 存储配置
        if os.getenv("DB_COMPRESSION_STRATEGY"):
            self.storage.compression_strategy = os.getenv("DB_COMPRESSION_STRATEGY")
        if os.getenv("DB_ARCHIVE_THRESHOLD"):
            self.storage.archive_threshold_days = int(os.getenv("DB_ARCHIVE_THRESHOLD"))

        # 备份配置
        if os.getenv("DB_BACKUP_DIR"):
            self.backup.backup_dir = os.getenv("DB_BACKUP_DIR")
        if os.getenv("DB_BACKUP_RETENTION"):
            self.backup.backup_retention_days = int(os.getenv("DB_BACKUP_RETENTION"))

        # 日志配置
        if os.getenv("DB_LOG_LEVEL"):
            self.logging.level = os.getenv("DB_LOG_LEVEL")
        if os.getenv("DB_LOG_FILE"):
            self.logging.file_path = os.getenv("DB_LOG_FILE")

    def _load_from_file(self, config_file: str) -> None:
        """从配置文件加载配置"""
        try:
            import json
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            # 更新各个配置对象
            if 'connection' in config_data:
                self._update_dataclass(self.connection, config_data['connection'])
            if 'sqlite' in config_data:
                self._update_dataclass(self.sqlite, config_data['sqlite'])
            if 'performance' in config_data:
                self._update_dataclass(self.performance, config_data['performance'])
            if 'storage' in config_data:
                self._update_dataclass(self.storage, config_data['storage'])
            if 'migration' in config_data:
                self._update_dataclass(self.migration, config_data['migration'])
            if 'backup' in config_data:
                self._update_dataclass(self.backup, config_data['backup'])
            if 'logging' in config_data:
                self._update_dataclass(self.logging, config_data['logging'])
            if 'security' in config_data:
                self._update_dataclass(self.security, config_data['security'])

        except Exception as e:
            print(f"加载配置文件失败: {e}")

    def _update_dataclass(self, obj, data: Dict[str, Any]) -> None:
        """更新数据类对象"""
        for key, value in data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)

    def save_to_file(self, config_file: str) -> bool:
        """保存配置到文件"""
        try:
            import json

            config_data = {
                'connection': self.connection.__dict__,
                'sqlite': self.sqlite.__dict__,
                'performance': self.performance.__dict__,
                'storage': self.storage.__dict__,
                'migration': self.migration.__dict__,
                'backup': self.backup.__dict__,
                'logging': self.logging.__dict__,
                'security': self.security.__dict__
            }

            # 确保目录存在
            Path(config_file).parent.mkdir(parents=True, exist_ok=True)

            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)

            return True

        except Exception as e:
            print(f"保存配置文件失败: {e}")
            return False

    def validate(self) -> list:
        """验证配置"""
        errors = []

        # 验证数据库连接配置
        if self.connection.driver not in ["sqlite", "mysql", "postgresql"]:
            errors.append(f"不支持的数据库驱动: {self.connection.driver}")

        if self.connection.driver != "sqlite" and not all([
            self.connection.host, self.connection.username, self.connection.password
        ]):
            errors.append("非SQLite数据库需要提供host、username和password")

        # 验证性能配置
        if self.performance.query_timeout <= 0:
            errors.append("查询超时时间必须大于0")

        if self.performance.batch_size <= 0:
            errors.append("批量操作大小必须大于0")

        # 验证存储配置
        if self.storage.compression_strategy not in ["none", "gzip", "lzma"]:
            errors.append(f"不支持的压缩策略: {self.storage.compression_strategy}")

        if self.storage.compression_level < 1 or self.storage.compression_level > 9:
            errors.append("压缩级别必须在1-9之间")

        # 验证备份配置
        if self.backup.backup_retention_days <= 0:
            errors.append("备份保留天数必须大于0")

        # 验证日志配置
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.logging.level not in valid_log_levels:
            errors.append(f"无效的日志级别: {self.logging.level}")

        return errors

    def get_summary(self) -> Dict[str, Any]:
        """获取配置摘要"""
        return {
            'database_driver': self.connection.driver,
            'database_name': self.connection.database,
            'pool_size': self.performance.connection_pool_size,
            'compression_enabled': self.storage.compression_enabled,
            'auto_backup': self.backup.auto_backup,
            'auto_migrate': self.migration.auto_migrate,
            'log_level': self.logging.level,
            'validation_errors': len(self.validate())
        }


# 默认配置实例
default_config = DatabaseConfig()


def load_config(config_file: Optional[str] = None) -> DatabaseConfig:
    """
    加载数据库配置

    Args:
        config_file: 配置文件路径

    Returns:
        数据库配置实例
    """
    return DatabaseConfig(config_file)


def create_default_config_file(config_file: str = "database_config.json") -> bool:
    """
    创建默认配置文件

    Args:
        config_file: 配置文件路径

    Returns:
        是否成功创建
    """
    config = DatabaseConfig()
    return config.save_to_file(config_file)