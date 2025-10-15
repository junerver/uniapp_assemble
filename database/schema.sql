-- Android项目构建工具 - SQLite数据库Schema
-- 优化版本：支持高性能查询和大数据量存储

-- ================================
-- 数据库性能优化配置
-- ================================
PRAGMA journal_mode = WAL;                    -- 写前日志模式，提高并发性能
PRAGMA synchronous = NORMAL;                  -- 平衡性能和安全性
PRAGMA cache_size = -64000;                   -- 64MB缓存
PRAGMA temp_store = MEMORY;                   -- 临时表存储在内存中
PRAGMA mmap_size = 268435456;                 -- 256MB内存映射
PRAGMA locking_mode = NORMAL;                 -- 正常锁定模式
PRAGMA foreign_keys = ON;                     -- 启用外键约束
PRAGMA query_only = OFF;                      -- 允许写操作
PRAGMA wal_autocheckpoint = 1000;             -- WAL自动检查点设置

-- ================================
-- 项目配置表
-- ================================
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    project_type VARCHAR(50) NOT NULL,
    repository_url VARCHAR(500) NOT NULL,
    local_path VARCHAR(500) NOT NULL,
    branch VARCHAR(100) DEFAULT 'main',
    build_command VARCHAR(1000),
    environment_vars JSON,
    build_timeout INTEGER DEFAULT 1800,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    tags JSON
);

-- 项目表索引
CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name);
CREATE INDEX IF NOT EXISTS idx_projects_type ON projects(project_type);
CREATE INDEX IF NOT EXISTS idx_projects_active ON projects(is_active);
CREATE INDEX IF NOT EXISTS idx_projects_created ON projects(created_at);
CREATE INDEX IF NOT EXISTS idx_projects_repo_url ON projects(repository_url);

-- 项目表触发器：自动更新updated_at字段
CREATE TRIGGER IF NOT EXISTS update_projects_timestamp
    AFTER UPDATE ON projects
    FOR EACH ROW
BEGIN
    UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- ================================
-- 构建记录表
-- ================================
CREATE TABLE IF NOT EXISTS builds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    build_number INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    started_at DATETIME,
    completed_at DATETIME,
    duration_seconds INTEGER,
    commit_hash VARCHAR(40),
    branch VARCHAR(100),
    build_type VARCHAR(50),
    triggered_by VARCHAR(100),
    exit_code INTEGER,
    artifact_path VARCHAR(500),
    artifact_size INTEGER,
    memory_usage_mb INTEGER,
    cpu_usage_percent INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    build_metadata JSON,

    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    UNIQUE(project_id, build_number)
);

-- 构建表索引（性能优化重点）
CREATE INDEX IF NOT EXISTS idx_builds_project_status ON builds(project_id, status);
CREATE INDEX IF NOT EXISTS idx_builds_project_number ON builds(project_id, build_number);
CREATE INDEX IF NOT EXISTS idx_builds_started ON builds(started_at);
CREATE INDEX IF NOT EXISTS idx_builds_completed ON builds(completed_at);
CREATE INDEX IF NOT EXISTS idx_builds_status ON builds(status);
CREATE INDEX IF NOT EXISTS idx_builds_commit ON builds(commit_hash);
CREATE INDEX IF NOT EXISTS idx_builds_branch ON builds(branch);
CREATE INDEX IF NOT EXISTS idx_builds_type ON builds(build_type);
CREATE INDEX IF NOT EXISTS idx_builds_triggered ON builds(triggered_by);

-- 构建表复合索引（优化常用查询）
CREATE INDEX IF NOT EXISTS idx_builds_project_status_started ON builds(project_id, status, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_builds_status_started ON builds(status, started_at DESC);

-- ================================
-- 构建日志表（大文本优化存储）
-- ================================
CREATE TABLE IF NOT EXISTS build_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    build_id INTEGER NOT NULL,
    sequence_number INTEGER NOT NULL,
    level VARCHAR(20),
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    message TEXT,
    source VARCHAR(100),

    FOREIGN KEY (build_id) REFERENCES builds(id) ON DELETE CASCADE,
    UNIQUE(build_id, sequence_number)
);

-- 构建日志表索引
CREATE INDEX IF NOT EXISTS idx_build_logs_build_sequence ON build_logs(build_id, sequence_number);
CREATE INDEX IF NOT EXISTS idx_build_logs_timestamp ON build_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_build_logs_level ON build_logs(level);
CREATE INDEX IF NOT EXISTS idx_build_logs_source ON build_logs(source);

-- 构建日志表复合索引
CREATE INDEX IF NOT EXISTS idx_build_logs_build_level ON build_logs(build_id, level);
CREATE INDEX IF NOT EXISTS idx_build_logs_build_timestamp ON build_logs(build_id, timestamp DESC);

-- ================================
-- 构建产物表
-- ================================
CREATE TABLE IF NOT EXISTS build_artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    build_id INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_size INTEGER,
    file_type VARCHAR(50),
    checksum VARCHAR(64),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    metadata JSON,

    FOREIGN KEY (build_id) REFERENCES builds(id) ON DELETE CASCADE
);

-- 构建产物表索引
CREATE INDEX IF NOT EXISTS idx_build_artifacts_build ON build_artifacts(build_id);
CREATE INDEX IF NOT EXISTS idx_build_artifacts_type ON build_artifacts(file_type);
CREATE INDEX IF NOT EXISTS idx_build_artifacts_checksum ON build_artifacts(checksum);
CREATE INDEX IF NOT EXISTS idx_build_artifacts_size ON build_artifacts(file_size);

-- ================================
-- Git操作记录表
-- ================================
CREATE TABLE IF NOT EXISTS git_operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    operation_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    from_branch VARCHAR(100),
    to_branch VARCHAR(100),
    commit_hash VARCHAR(40),
    commit_message TEXT,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    duration_seconds INTEGER,
    success BOOLEAN,
    error_message TEXT,
    files_changed INTEGER,
    insertions INTEGER,
    deletions INTEGER,
    operation_metadata JSON,

    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- Git操作表索引
CREATE INDEX IF NOT EXISTS idx_git_operations_project_type ON git_operations(project_id, operation_type);
CREATE INDEX IF NOT EXISTS idx_git_operations_status ON git_operations(status);
CREATE INDEX IF NOT EXISTS idx_git_operations_started ON git_operations(started_at);
CREATE INDEX IF NOT EXISTS idx_git_operations_commit ON git_operations(commit_hash);
CREATE INDEX IF NOT EXISTS idx_git_operations_success ON git_operations(success);

-- Git操作表复合索引
CREATE INDEX IF NOT EXISTS idx_git_operations_project_started ON git_operations(project_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_git_operations_type_status ON git_operations(operation_type, status);

-- ================================
-- 项目配置表
-- ================================
CREATE TABLE IF NOT EXISTS project_configurations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    config_key VARCHAR(255) NOT NULL,
    config_value TEXT,
    config_type VARCHAR(50),
    is_encrypted BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),

    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    UNIQUE(project_id, config_key)
);

-- 项目配置表索引
CREATE INDEX IF NOT EXISTS idx_project_configs_project_key ON project_configurations(project_id, config_key);
CREATE INDEX IF NOT EXISTS idx_project_configs_type ON project_configurations(config_type);
CREATE INDEX IF NOT EXISTS idx_project_configs_encrypted ON project_configurations(is_encrypted);

-- 项目配置表触发器：自动更新updated_at字段
CREATE TRIGGER IF NOT EXISTS update_project_configs_timestamp
    AFTER UPDATE ON project_configurations
    FOR EACH ROW
BEGIN
    UPDATE project_configurations SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- ================================
-- 系统性能指标表
-- ================================
CREATE TABLE IF NOT EXISTS system_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name VARCHAR(100) NOT NULL,
    metric_value INTEGER NOT NULL,
    metric_unit VARCHAR(20),
    build_id INTEGER,
    project_id INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    metadata JSON,

    FOREIGN KEY (build_id) REFERENCES builds(id) ON DELETE SET NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
);

-- 系统性能指标表索引
CREATE INDEX IF NOT EXISTS idx_system_metrics_name_timestamp ON system_metrics(metric_name, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_system_metrics_build ON system_metrics(build_id);
CREATE INDEX IF NOT EXISTS idx_system_metrics_project ON system_metrics(project_id);

-- 系统性能指标表复合索引
CREATE INDEX IF NOT EXISTS idx_system_metrics_name_value ON system_metrics(metric_name, metric_value);

-- ================================
-- 数据库版本管理表
-- ================================
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

-- 插入初始版本
INSERT OR IGNORE INTO schema_version (version, description) VALUES (1, '初始数据库schema');

-- ================================
-- 构建统计视图（优化查询性能）
-- ================================
CREATE VIEW IF NOT EXISTS build_statistics AS
SELECT
    p.id as project_id,
    p.name as project_name,
    COUNT(b.id) as total_builds,
    COUNT(CASE WHEN b.status = 'success' THEN 1 END) as successful_builds,
    COUNT(CASE WHEN b.status = 'failed' THEN 1 END) as failed_builds,
    COUNT(CASE WHEN b.status = 'running' THEN 1 END) as running_builds,
    MAX(b.started_at) as last_build_time,
    AVG(b.duration_seconds) as avg_duration_seconds,
    MAX(b.duration_seconds) as max_duration_seconds,
    MIN(b.duration_seconds) as min_duration_seconds
FROM projects p
LEFT JOIN builds b ON p.id = b.project_id
GROUP BY p.id, p.name;

-- ================================
-- Git操作统计视图
-- ================================
CREATE VIEW IF NOT EXISTS git_statistics AS
SELECT
    p.id as project_id,
    p.name as project_name,
    COUNT(go.id) as total_operations,
    COUNT(CASE WHEN go.success = TRUE THEN 1 END) as successful_operations,
    COUNT(CASE WHEN go.success = FALSE THEN 1 END) as failed_operations,
    go.operation_type,
    MAX(go.started_at) as last_operation_time,
    AVG(go.duration_seconds) as avg_duration_seconds
FROM projects p
LEFT JOIN git_operations go ON p.id = go.project_id
GROUP BY p.id, p.name, go.operation_type;

-- ================================
-- 性能优化：预编译语句模板
-- ================================

-- 插入项目记录的优化语句
-- INSERT INTO projects (name, project_type, repository_url, local_path, branch, build_command, environment_vars, build_timeout, created_at, updated_at, is_active, tags)
-- VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, TRUE, ?);

-- 插入构建记录的优化语句
-- INSERT INTO builds (project_id, build_number, status, build_type, triggered_by, commit_hash, branch, created_at)
-- VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);

-- 批量插入构建日志的优化语句
-- INSERT INTO build_logs (build_id, sequence_number, level, message, source, timestamp)
-- VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP);

-- 查询项目构建历史的优化语句
-- SELECT b.id, b.build_number, b.status, b.started_at, b.completed_at, b.duration_seconds, b.exit_code
-- FROM builds b
-- WHERE b.project_id = ?
-- ORDER BY b.build_number DESC
-- LIMIT ? OFFSET ?;

-- 查询构建日志的优化语句（分页）
-- SELECT id, sequence_number, level, timestamp, message, source
-- FROM build_logs
-- WHERE build_id = ?
-- ORDER BY sequence_number
-- LIMIT ? OFFSET ?;

-- 统计项目构建成功率的优化语句
-- SELECT
--     COUNT(*) as total_builds,
--     COUNT(CASE WHEN status = 'success' THEN 1 END) as successful_builds,
--     ROUND(COUNT(CASE WHEN status = 'success' THEN 1 END) * 100.0 / COUNT(*), 2) as success_rate
-- FROM builds
-- WHERE project_id = ?;

-- ================================
-- 数据清理规则（维护性能）
-- ================================

-- 清理旧的构建日志（保留最近3个月）
-- DELETE FROM build_logs
-- WHERE timestamp < datetime('now', '-3 months');

-- 清理旧的系统指标（保留最近1个月）
-- DELETE FROM system_metrics
-- WHERE timestamp < datetime('now', '-1 month');

-- 清理失败的构建记录（保留最近1个月）
-- DELETE FROM builds
-- WHERE status = 'failed' AND completed_at < datetime('now', '-1 month');

-- ================================
-- 数据完整性约束
-- ================================

-- 确保构建编号连续性
CREATE TRIGGER IF NOT EXISTS maintain_build_number_sequence
    BEFORE INSERT ON builds
    FOR EACH ROW
BEGIN
    UPDATE builds
    SET build_number = build_number + 1
    WHERE project_id = NEW.project_id AND build_number >= (
        SELECT COALESCE(MAX(build_number), 0) + 1
        FROM builds
        WHERE project_id = NEW.project_id
    );
END;

-- 确保日志序号连续性
CREATE TRIGGER IF NOT EXISTS maintain_log_sequence
    BEFORE INSERT ON build_logs
    FOR EACH ROW
BEGIN
    UPDATE build_logs
    SET sequence_number = sequence_number + 1
    WHERE build_id = NEW.build_id AND sequence_number >= (
        SELECT COALESCE(MAX(sequence_number), 0) + 1
        FROM build_logs
        WHERE build_id = NEW.build_id
    );
END;

-- ================================
-- 性能监控视图
-- ================================
CREATE VIEW IF NOT EXISTS database_health AS
SELECT
    'projects' as table_name,
    COUNT(*) as total_records,
    MIN(created_at) as oldest_record,
    MAX(created_at) as newest_record
FROM projects
UNION ALL
SELECT
    'builds' as table_name,
    COUNT(*) as total_records,
    MIN(created_at) as oldest_record,
    MAX(created_at) as newest_record
FROM builds
UNION ALL
SELECT
    'build_logs' as table_name,
    COUNT(*) as total_records,
    MIN(timestamp) as oldest_record,
    MAX(timestamp) as newest_record
FROM build_logs
UNION ALL
SELECT
    'git_operations' as table_name,
    COUNT(*) as total_records,
    MIN(started_at) as oldest_record,
    MAX(started_at) as newest_record
FROM git_operations;