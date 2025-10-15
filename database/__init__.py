"""
Android项目构建工具 - 数据库模块

本模块提供完整的数据库解决方案，包括：
- 核心数据模型
- 数据库连接和会话管理
- 迁移和版本控制
- 存储优化
- 备份和恢复
"""

from .models import (
    # 基础模型
    Base,

    # SQLAlchemy模型
    Project, Build, BuildLog, BuildArtifact, GitOperation,
    ProjectConfiguration, SystemMetrics,

    # Pydantic模型
    ProjectBase, ProjectCreate, ProjectUpdate, ProjectInDB,
    BuildBase, BuildCreate, BuildUpdate, BuildInDB,
    BuildLogBase, BuildLogCreate, BuildLogInDB,
    GitOperationBase, GitOperationCreate, GitOperationInDB,

    # 枚举类型
    BuildStatus, GitOperationType, ProjectType,

    # 配置和验证
    DatabaseConfig, ValidationRules
)

from .database import (
    # 核心类
    DatabaseManager, DatabaseService, BaseRepository,

    # 专用仓储
    ProjectRepository, BuildRepository, BuildLogRepository, GitOperationRepository,

    # 全局实例
    db_manager, database_service,

    # 便捷函数
    get_db_session, init_database, close_database,

    # 性能监控
    monitor_query_performance
)

from .migrations import (
    # 迁移管理
    Migration, MigrationManager,

    # 备份管理
    BackupManager,

    # 全局实例
    migration_manager, backup_manager,

    # 便捷函数
    migrate_to_latest, check_database_health
)

from .storage_optimization import (
    # 存储优化
    CompressionStrategy, GzipCompression, LZMACompression, NoCompression,
    BuildLogStorage, CacheManager, StorageOptimizer,

    # 数据类
    StorageStats,

    # 全局实例
    storage_optimizer, log_storage,

    # 便捷函数
    store_build_log, get_build_logs, optimize_storage, get_storage_info
)

__version__ = "1.0.0"
__author__ = "Android Build Tool Team"

# 导出的公共接口
__all__ = [
    # 核心模型
    'Base', 'Project', 'Build', 'BuildLog', 'BuildArtifact', 'GitOperation',
    'ProjectConfiguration', 'SystemMetrics',

    # Pydantic模型
    'ProjectBase', 'ProjectCreate', 'ProjectUpdate', 'ProjectInDB',
    'BuildBase', 'BuildCreate', 'BuildUpdate', 'BuildInDB',
    'BuildLogBase', 'BuildLogCreate', 'BuildLogInDB',
    'GitOperationBase', 'GitOperationCreate', 'GitOperationInDB',

    # 枚举
    'BuildStatus', 'GitOperationType', 'ProjectType',

    # 配置
    'DatabaseConfig', 'ValidationRules',

    # 数据库服务
    'DatabaseManager', 'DatabaseService', 'BaseRepository',
    'ProjectRepository', 'BuildRepository', 'BuildLogRepository', 'GitOperationRepository',
    'db_manager', 'database_service',

    # 便捷函数
    'get_db_session', 'init_database', 'close_database',

    # 迁移和备份
    'Migration', 'MigrationManager', 'BackupManager',
    'migration_manager', 'backup_manager',
    'migrate_to_latest', 'check_database_health',

    # 存储优化
    'CompressionStrategy', 'GzipCompression', 'LZMACompression', 'NoCompression',
    'BuildLogStorage', 'CacheManager', 'StorageOptimizer', 'StorageStats',
    'storage_optimizer', 'log_storage',
    'store_build_log', 'get_build_logs', 'optimize_storage', 'get_storage_info',

    # 性能监控
    'monitor_query_performance'
]