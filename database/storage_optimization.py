"""
Android项目构建工具 - 存储优化模块

提供：
1. 大文本字段（构建日志）存储优化
2. 数据压缩和归档
3. 分区存储策略
4. 缓存优化
5. 存储空间管理
6. 性能监控
"""

import gzip
import json
import logging
import lzma
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
from pathlib import Path
import hashlib
import threading
from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy import text, func
from sqlalchemy.orm import Session

from .database import DatabaseService, db_manager

logger = logging.getLogger(__name__)


@dataclass
class StorageStats:
    """存储统计信息"""
    table_name: str
    total_records: int
    total_size_mb: float
    avg_record_size: float
    oldest_record: Optional[datetime]
    newest_record: Optional[datetime]


class CompressionStrategy:
    """压缩策略基类"""

    def compress(self, data: str) -> bytes:
        """压缩数据"""
        raise NotImplementedError

    def decompress(self, compressed_data: bytes) -> str:
        """解压数据"""
        raise NotImplementedError


class GzipCompression(CompressionStrategy):
    """Gzip压缩策略"""

    def __init__(self, compression_level: int = 6):
        self.compression_level = compression_level

    def compress(self, data: str) -> bytes:
        """使用Gzip压缩数据"""
        return gzip.compress(data.encode('utf-8'), compresslevel=self.compression_level)

    def decompress(self, compressed_data: bytes) -> str:
        """解压Gzip数据"""
        return gzip.decompress(compressed_data).decode('utf-8')


class LZMACompression(CompressionStrategy):
    """LZMA压缩策略（高压缩率）"""

    def __init__(self, preset: int = 6):
        self.preset = preset

    def compress(self, data: str) -> bytes:
        """使用LZMA压缩数据"""
        return lzma.compress(data.encode('utf-8'), preset=self.preset)

    def decompress(self, compressed_data: bytes) -> str:
        """解压LZMA数据"""
        return lzma.decompress(compressed_data).decode('utf-8')


class NoCompression(CompressionStrategy):
    """无压缩策略"""

    def compress(self, data: str) -> bytes:
        """不压缩，直接返回字节数据"""
        return data.encode('utf-8')

    def decompress(self, compressed_data: bytes) -> str:
        """直接返回字符串"""
        return compressed_data.decode('utf-8')


class BuildLogStorage:
    """构建日志存储优化器"""

    def __init__(self, db_service: DatabaseService):
        """
        初始化构建日志存储器

        Args:
            db_service: 数据库服务
        """
        self.db_service = db_service
        self.compression_strategies = {
            'none': NoCompression(),
            'gzip': GzipCompression(),
            'lzma': LZMACompression()
        }
        self.current_strategy = 'gzip'
        self.archive_threshold_days = 30
        self.compression_threshold_size = 1024  # 1KB以上的日志才压缩

    def _get_compression_strategy(self) -> CompressionStrategy:
        """获取当前压缩策略"""
        return self.compression_strategies[self.current_strategy]

    def store_log_entry(
        self,
        build_id: int,
        sequence_number: int,
        level: str,
        message: str,
        source: Optional[str] = None,
        compress: Optional[bool] = None
    ) -> bool:
        """
        存储单条日志条目

        Args:
            build_id: 构建ID
            sequence_number: 序列号
            level: 日志级别
            message: 日志消息
            source: 日志来源
            compress: 是否压缩，None表示自动判断

        Returns:
            是否成功
        """
        try:
            # 自动判断是否需要压缩
            if compress is None:
                compress = len(message.encode('utf-8')) > self.compression_threshold_size

            # 准备数据
            log_data = {
                'build_id': build_id,
                'sequence_number': sequence_number,
                'level': level,
                'message': message,
                'source': source,
                'timestamp': datetime.utcnow(),
                'compressed': compress
            }

            if compress:
                strategy = self._get_compression_strategy()
                compressed_message = strategy.compress(message)
                log_data['message_compressed'] = compressed_message
                log_data['message'] = None
                log_data['compression_type'] = self.current_strategy
            else:
                log_data['message_compressed'] = None
                log_data['compression_type'] = None

            # 插入数据库
            with self.db_service.transaction() as session:
                if compress:
                    session.execute(text("""
                        INSERT INTO build_logs
                        (build_id, sequence_number, level, message, source, timestamp, compressed, compression_type)
                        VALUES (:build_id, :sequence_number, :level, NULL, :source, :timestamp, TRUE, :compression_type)
                    """), log_data)

                    # 获取插入的ID
                    result = session.execute(text("SELECT last_insert_rowid()"))
                    log_id = result.scalar()

                    # 存储压缩数据到单独的表
                    session.execute(text("""
                        INSERT INTO build_logs_compressed (log_id, compressed_data)
                        VALUES (:log_id, :compressed_data)
                    """), {'log_id': log_id, 'compressed_data': log_data['message_compressed']})
                else:
                    session.execute(text("""
                        INSERT INTO build_logs
                        (build_id, sequence_number, level, message, source, timestamp, compressed)
                        VALUES (:build_id, :sequence_number, :level, :message, :source, :timestamp, FALSE)
                    """), log_data)

            return True

        except Exception as e:
            logger.error(f"存储日志条目失败: {e}")
            return False

    def get_log_entry(self, log_id: int) -> Optional[Dict[str, Any]]:
        """
        获取单条日志条目

        Args:
            log_id: 日志ID

        Returns:
            日志条目数据或None
        """
        try:
            with self.db_service.transaction() as session:
                # 查询日志基本信息
                result = session.execute(text("""
                    SELECT id, build_id, sequence_number, level, message, source, timestamp,
                           compressed, compression_type
                    FROM build_logs
                    WHERE id = :log_id
                """), {'log_id': log_id})

                row = result.fetchone()
                if not row:
                    return None

                log_data = dict(row)

                # 如果是压缩数据，解压
                if log_data['compressed']:
                    compressed_result = session.execute(text("""
                        SELECT compressed_data FROM build_logs_compressed WHERE log_id = :log_id
                    """), {'log_id': log_id})

                    compressed_row = compressed_result.fetchone()
                    if compressed_row:
                        strategy = self.compression_strategies[log_data['compression_type']]
                        log_data['message'] = strategy.decompress(compressed_row[0])

                return log_data

        except Exception as e:
            logger.error(f"获取日志条目失败: {e}")
            return None

    def get_build_logs(
        self,
        build_id: int,
        skip: int = 0,
        limit: int = 1000,
        level: Optional[str] = None,
        include_compressed: bool = True
    ) -> List[Dict[str, Any]]:
        """
        获取构建日志列表

        Args:
            build_id: 构建ID
            skip: 跳过记录数
            limit: 限制记录数
            level: 日志级别过滤
            include_compressed: 是否包含压缩数据

        Returns:
            日志列表
        """
        try:
            with self.db_service.transaction() as session:
                # 构建查询
                query_params = {'build_id': build_id, 'skip': skip, 'limit': limit}
                where_clause = "WHERE bl.build_id = :build_id"

                if level:
                    where_clause += " AND bl.level = :level"
                    query_params['level'] = level

                # 查询日志列表
                query = f"""
                    SELECT bl.id, bl.sequence_number, bl.level, bl.message, bl.source,
                           bl.timestamp, bl.compressed, bl.compression_type
                    FROM build_logs bl
                    {where_clause}
                    ORDER BY bl.sequence_number
                    LIMIT :limit OFFSET :skip
                """

                result = session.execute(text(query), query_params)
                logs = [dict(row) for row in result]

                # 如果需要解压数据
                if include_compressed:
                    for log in logs:
                        if log['compressed'] and log['compression_type']:
                            compressed_result = session.execute(text("""
                                SELECT compressed_data FROM build_logs_compressed WHERE log_id = :log_id
                            """), {'log_id': log['id']})

                            compressed_row = compressed_result.fetchone()
                            if compressed_row:
                                strategy = self.compression_strategies[log['compression_type']]
                                log['message'] = strategy.decompress(compressed_row[0])

                return logs

        except Exception as e:
            logger.error(f"获取构建日志失败: {e}")
            return []

    def batch_store_logs(self, logs: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        批量存储日志条目

        Args:
            logs: 日志条目列表

        Returns:
            (成功数量, 失败数量)
        """
        success_count = 0
        failure_count = 0

        try:
            with self.db_service.transaction() as session:
                for log in logs:
                    try:
                        # 自动判断是否需要压缩
                        message = log.get('message', '')
                        compress = len(message.encode('utf-8')) > self.compression_threshold_size

                        if compress:
                            strategy = self._get_compression_strategy()
                            compressed_message = strategy.compress(message)

                            # 插入日志记录
                            session.execute(text("""
                                INSERT INTO build_logs
                                (build_id, sequence_number, level, source, timestamp, compressed, compression_type)
                                VALUES (:build_id, :sequence_number, :level, :source, :timestamp, TRUE, :compression_type)
                            """), {
                                'build_id': log['build_id'],
                                'sequence_number': log['sequence_number'],
                                'level': log.get('level', 'INFO'),
                                'source': log.get('source'),
                                'timestamp': log.get('timestamp', datetime.utcnow()),
                                'compression_type': self.current_strategy
                            })

                            # 获取插入的ID并存储压缩数据
                            result = session.execute(text("SELECT last_insert_rowid()"))
                            log_id = result.scalar()

                            session.execute(text("""
                                INSERT INTO build_logs_compressed (log_id, compressed_data)
                                VALUES (:log_id, :compressed_data)
                            """), {'log_id': log_id, 'compressed_data': compressed_message})
                        else:
                            # 直接存储未压缩数据
                            session.execute(text("""
                                INSERT INTO build_logs
                                (build_id, sequence_number, level, message, source, timestamp, compressed)
                                VALUES (:build_id, :sequence_number, :level, :message, :source, :timestamp, FALSE)
                            """), {
                                'build_id': log['build_id'],
                                'sequence_number': log['sequence_number'],
                                'level': log.get('level', 'INFO'),
                                'message': message,
                                'source': log.get('source'),
                                'timestamp': log.get('timestamp', datetime.utcnow())
                            })

                        success_count += 1

                    except Exception as e:
                        logger.error(f"批量存储日志失败: {e}")
                        failure_count += 1
                        continue

            logger.info(f"批量存储日志完成: 成功 {success_count}, 失败 {failure_count}")
            return success_count, failure_count

        except Exception as e:
            logger.error(f"批量存储日志失败: {e}")
            return 0, len(logs)

    def archive_old_logs(self, days: int = None) -> int:
        """
        归档旧日志

        Args:
            days: 归档多少天前的日志，None使用默认值

        Returns:
            归档的记录数量
        """
        if days is None:
            days = self.archive_threshold_days

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        try:
            with self.db_service.transaction() as session:
                # 移动旧日志到归档表
                result = session.execute(text("""
                    INSERT INTO build_logs_archive
                    SELECT * FROM build_logs
                    WHERE timestamp < :cutoff_date
                """), {'cutoff_date': cutoff_date})

                archived_count = result.rowcount

                # 删除原表中的旧记录
                session.execute(text("""
                    DELETE FROM build_logs
                    WHERE timestamp < :cutoff_date
                """), {'cutoff_date': cutoff_date})

                logger.info(f"归档旧日志完成: {archived_count} 条记录")
                return archived_count

        except Exception as e:
            logger.error(f"归档旧日志失败: {e}")
            return 0

    def get_storage_stats(self) -> Dict[str, Any]:
        """获取存储统计信息"""
        try:
            with self.db_service.transaction() as session:
                # 获取主表统计
                main_stats = session.execute(text("""
                    SELECT
                        COUNT(*) as total_records,
                        SUM(LENGTH(message)) as total_size,
                        AVG(LENGTH(message)) as avg_size,
                        MIN(timestamp) as oldest_record,
                        MAX(timestamp) as newest_record
                    FROM build_logs
                    WHERE compressed = FALSE
                """)).fetchone()

                # 获取压缩统计
                compressed_stats = session.execute(text("""
                    SELECT
                        COUNT(*) as compressed_records,
                        SUM(LENGTH(blc.compressed_data)) as compressed_size
                    FROM build_logs bl
                    JOIN build_logs_compressed blc ON bl.id = blc.log_id
                    WHERE bl.compressed = TRUE
                """)).fetchone()

                # 获取归档统计
                archive_stats = session.execute(text("""
                    SELECT
                        COUNT(*) as archive_records,
                        SUM(LENGTH(message)) as archive_size
                    FROM build_logs_archive
                """)).fetchone()

                total_size = (main_stats['total_size'] or 0) + \
                           (compressed_stats['compressed_size'] or 0) + \
                           (archive_stats['archive_size'] or 0)

                compression_ratio = 0
                if main_stats['total_size'] and compressed_stats['compressed_size']:
                    original_size = main_stats['total_size']
                    compressed_size = compressed_stats['compressed_size']
                    compression_ratio = (1 - compressed_size / original_size) * 100

                return {
                    'main_table': {
                        'total_records': main_stats['total_records'] or 0,
                        'total_size_mb': (main_stats['total_size'] or 0) / (1024 * 1024),
                        'avg_size': main_stats['avg_size'] or 0,
                        'oldest_record': main_stats['oldest_record'],
                        'newest_record': main_stats['newest_record']
                    },
                    'compressed': {
                        'total_records': compressed_stats['compressed_records'] or 0,
                        'compressed_size_mb': (compressed_stats['compressed_size'] or 0) / (1024 * 1024)
                    },
                    'archive': {
                        'total_records': archive_stats['archive_records'] or 0,
                        'archive_size_mb': (archive_stats['archive_size'] or 0) / (1024 * 1024)
                    },
                    'overall': {
                        'total_size_mb': total_size / (1024 * 1024),
                        'compression_ratio_percent': compression_ratio,
                        'total_records': (main_stats['total_records'] or 0) + \
                                        (compressed_stats['compressed_records'] or 0) + \
                                        (archive_stats['archive_records'] or 0)
                    }
                }

        except Exception as e:
            logger.error(f"获取存储统计失败: {e}")
            return {}


class CacheManager:
    """缓存管理器"""

    def __init__(self, max_size: int = 100, ttl_seconds: int = 300):
        """
        初始化缓存管理器

        Args:
            max_size: 最大缓存条目数
            ttl_seconds: 缓存过期时间（秒）
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[Any, datetime]] = {}
        self._access_times: Dict[str, datetime] = {}
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self._lock:
            if key not in self._cache:
                return None

            value, created_at = self._cache[key]

            # 检查是否过期
            if datetime.utcnow() - created_at > timedelta(seconds=self.ttl_seconds):
                del self._cache[key]
                self._access_times.pop(key, None)
                return None

            # 更新访问时间
            self._access_times[key] = datetime.utcnow()
            return value

    def set(self, key: str, value: Any) -> None:
        """设置缓存值"""
        with self._lock:
            # 如果缓存已满，删除最久未访问的条目
            if len(self._cache) >= self.max_size and key not in self._cache:
                oldest_key = min(self._access_times.keys(), key=lambda k: self._access_times[k])
                del self._cache[oldest_key]
                self._access_times.pop(oldest_key, None)

            self._cache[key] = (value, datetime.utcnow())
            self._access_times[key] = datetime.utcnow()

    def delete(self, key: str) -> bool:
        """删除缓存条目"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._access_times.pop(key, None)
                return True
            return False

    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._access_times.clear()

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self._lock:
            now = datetime.utcnow()
            expired_count = sum(
                1 for _, created_at in self._cache.values()
                if now - created_at > timedelta(seconds=self.ttl_seconds)
            )

            return {
                'total_entries': len(self._cache),
                'max_size': self.max_size,
                'expired_entries': expired_count,
                'ttl_seconds': self.ttl_seconds,
                'utilization_percent': len(self._cache) / self.max_size * 100
            }


class StorageOptimizer:
    """存储优化器 - 综合存储优化管理"""

    def __init__(self, db_service: DatabaseService):
        """
        初始化存储优化器

        Args:
            db_service: 数据库服务
        """
        self.db_service = db_service
        self.log_storage = BuildLogStorage(db_service)
        self.cache = CacheManager()
        self._setup_compression_tables()

    def _setup_compression_tables(self) -> None:
        """设置压缩存储表"""
        setup_sql = """
        -- 构建日志压缩数据表
        CREATE TABLE IF NOT EXISTS build_logs_compressed (
            log_id INTEGER PRIMARY KEY,
            compressed_data BLOB NOT NULL,
            FOREIGN KEY (log_id) REFERENCES build_logs(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_build_logs_compressed_log_id ON build_logs_compressed(log_id);

        -- 构建日志归档表
        CREATE TABLE IF NOT EXISTS build_logs_archive (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            build_id INTEGER NOT NULL,
            sequence_number INTEGER NOT NULL,
            level VARCHAR(20),
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            message TEXT,
            source VARCHAR(100),
            compressed BOOLEAN DEFAULT FALSE,
            compression_type VARCHAR(20)
        );

        CREATE INDEX IF NOT EXISTS idx_build_logs_archive_build ON build_logs_archive(build_id);
        CREATE INDEX IF NOT EXISTS idx_build_logs_archive_timestamp ON build_logs_archive(timestamp);
        """

        try:
            with self.db_service.transaction() as session:
                session.execute(text(setup_sql))
            logger.info("压缩存储表设置完成")
        except Exception as e:
            logger.error(f"设置压缩存储表失败: {e}")

    def optimize_database(self) -> Dict[str, Any]:
        """
        执行数据库优化

        Returns:
            优化结果统计
        """
        optimization_results = {
            'vacuum': False,
            'analyze': False,
            'reindex': False,
            'clean_old_logs': 0,
            'compress_large_logs': 0,
            'errors': []
        }

        try:
            with self.db_service.transaction() as session:
                # 1. 清理旧日志
                old_logs_count = self.log_storage.archive_old_logs()
                optimization_results['clean_old_logs'] = old_logs_count

                # 2. 压缩大日志
                large_logs_count = self._compress_large_logs()
                optimization_results['compress_large_logs'] = large_logs_count

                # 3. 执行VACUUM（重建数据库文件，回收空间）
                try:
                    session.execute(text("VACUUM"))
                    optimization_results['vacuum'] = True
                    logger.info("数据库VACUUM完成")
                except Exception as e:
                    optimization_results['errors'].append(f"VACUUM失败: {e}")

                # 4. 更新统计信息
                try:
                    session.execute(text("ANALYZE"))
                    optimization_results['analyze'] = True
                    logger.info("数据库ANALYZE完成")
                except Exception as e:
                    optimization_results['errors'].append(f"ANALYZE失败: {e}")

                # 5. 重建索引
                try:
                    session.execute(text("REINDEX"))
                    optimization_results['reindex'] = True
                    logger.info("数据库REINDEX完成")
                except Exception as e:
                    optimization_results['errors'].append(f"REINDEX失败: {e}")

            logger.info(f"数据库优化完成: {optimization_results}")
            return optimization_results

        except Exception as e:
            error_msg = f"数据库优化失败: {e}"
            logger.error(error_msg)
            optimization_results['errors'].append(error_msg)
            return optimization_results

    def _compress_large_logs(self) -> int:
        """压缩大型日志条目"""
        compressed_count = 0

        try:
            with self.db_service.transaction() as session:
                # 查找未压缩的大日志
                result = session.execute(text("""
                    SELECT id, message
                    FROM build_logs
                    WHERE compressed = FALSE
                    AND LENGTH(message) > :threshold_size
                    ORDER BY timestamp DESC
                    LIMIT 1000
                """), {'threshold_size': self.log_storage.compression_threshold_size})

                large_logs = result.fetchall()

                for log_id, message in large_logs:
                    try:
                        # 压缩消息
                        strategy = self.log_storage._get_compression_strategy()
                        compressed_message = strategy.compress(message)

                        # 更新记录为压缩状态
                        session.execute(text("""
                            UPDATE build_logs
                            SET compressed = TRUE,
                                message = NULL,
                                compression_type = :compression_type
                            WHERE id = :log_id
                        """), {
                            'log_id': log_id,
                            'compression_type': self.log_storage.current_strategy
                        })

                        # 存储压缩数据
                        session.execute(text("""
                            INSERT INTO build_logs_compressed (log_id, compressed_data)
                            VALUES (:log_id, :compressed_data)
                        """), {'log_id': log_id, 'compressed_data': compressed_message})

                        compressed_count += 1

                    except Exception as e:
                        logger.error(f"压缩日志失败 ID={log_id}: {e}")
                        continue

            logger.info(f"压缩大型日志完成: {compressed_count} 条记录")
            return compressed_count

        except Exception as e:
            logger.error(f"压缩大型日志失败: {e}")
            return 0

    def get_storage_statistics(self) -> Dict[str, Any]:
        """获取详细存储统计"""
        try:
            with self.db_service.transaction() as session:
                # 获取各表的存储统计
                tables = ['projects', 'builds', 'build_logs', 'build_logs_compressed',
                         'build_logs_archive', 'git_operations', 'project_configurations',
                         'system_metrics']

                table_stats = []
                total_size = 0

                for table in tables:
                    try:
                        # 检查表是否存在
                        result = session.execute(text("""
                            SELECT COUNT(*) as count
                            FROM sqlite_master
                            WHERE type='table' AND name=:table_name
                        """), {'table_name': table})

                        if result.scalar() == 0:
                            continue

                        # 获取记录数
                        count_result = session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                        record_count = count_result.scalar()

                        # 估算表大小（SQLite没有直接的表大小查询）
                        size_result = session.execute(text(f"""
                            SELECT SUM(LENGTH(CAST(* AS TEXT))) as total_size
                            FROM {table}
                            LIMIT 1000
                        """))
                        avg_size = size_result.scalar() or 0
                        estimated_size = avg_size * record_count

                        table_stats.append({
                            'table_name': table,
                            'record_count': record_count,
                            'estimated_size_mb': estimated_size / (1024 * 1024),
                            'avg_record_size': avg_size
                        })

                        total_size += estimated_size

                    except Exception as e:
                        logger.warning(f"获取表 {table} 统计失败: {e}")

                # 获取日志存储详细统计
                log_stats = self.log_storage.get_storage_stats()

                # 获取缓存统计
                cache_stats = self.cache.get_stats()

                return {
                    'database_file_size_mb': self._get_database_file_size(),
                    'total_estimated_size_mb': total_size / (1024 * 1024),
                    'table_statistics': table_stats,
                    'log_storage_stats': log_stats,
                    'cache_stats': cache_stats,
                    'optimization_recommendations': self._get_optimization_recommendations(table_stats, log_stats)
                }

        except Exception as e:
            logger.error(f"获取存储统计失败: {e}")
            return {}

    def _get_database_file_size(self) -> float:
        """获取数据库文件大小（MB）"""
        try:
            if hasattr(db_manager.engine, 'url') and db_manager.engine.url.drivername == 'sqlite':
                db_path = db_manager.engine.url.database
                if db_path and os.path.exists(db_path):
                    size_bytes = os.path.getsize(db_path)
                    return size_bytes / (1024 * 1024)
        except Exception as e:
            logger.error(f"获取数据库文件大小失败: {e}")
        return 0

    def _get_optimization_recommendations(
        self,
        table_stats: List[Dict[str, Any]],
        log_stats: Dict[str, Any]
    ) -> List[str]:
        """获取优化建议"""
        recommendations = []

        # 检查日志存储优化
        if log_stats.get('overall', {}).get('compression_ratio_percent', 0) < 30:
            recommendations.append("建议启用日志压缩以节省存储空间")

        if log_stats.get('archive', {}).get('total_records', 0) > 100000:
            recommendations.append("建议清理归档日志或迁移到外部存储")

        # 检查表大小
        large_tables = [t for t in table_stats if t['estimated_size_mb'] > 100]
        if large_tables:
            recommendations.append(f"大表检测: {', '.join([t['table_name'] for t in large_tables])}")

        # 检查缓存效率
        cache_stats = self.cache.get_stats()
        if cache_stats['utilization_percent'] > 90:
            recommendations.append("缓存利用率过高，建议增加缓存大小")

        return recommendations

    def schedule_maintenance(self) -> None:
        """计划维护任务"""
        try:
            # 清理过期缓存
            self.cache.clear()

            # 压缩大日志
            self._compress_large_logs()

            # 归档旧日志
            self.log_storage.archive_old_logs()

            logger.info("计划维护任务完成")
        except Exception as e:
            logger.error(f"计划维护任务失败: {e}")


# ================================
# 全局实例
# ================================

# 创建全局存储优化器
storage_optimizer = StorageOptimizer(database_service)

# 创建全局日志存储器
log_storage = storage_optimizer.log_storage

# 导出常用函数
def store_build_log(build_id: int, sequence_number: int, level: str, message: str, **kwargs) -> bool:
    """存储构建日志的便捷函数"""
    return log_storage.store_log_entry(build_id, sequence_number, level, message, **kwargs)

def get_build_logs(build_id: int, **kwargs) -> List[Dict[str, Any]]:
    """获取构建日志的便捷函数"""
    return log_storage.get_build_logs(build_id, **kwargs)

def optimize_storage() -> Dict[str, Any]:
    """执行存储优化的便捷函数"""
    return storage_optimizer.optimize_database()

def get_storage_info() -> Dict[str, Any]:
    """获取存储信息的便捷函数"""
    return storage_optimizer.get_storage_statistics()