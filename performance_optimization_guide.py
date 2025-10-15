"""
性能优化指南和配置管理
提供系统调优、资源配置、缓存策略等最佳实践
"""

import asyncio
import json
import os
import psutil
import sys
from typing import Dict, Any, List, Optional, Union, Callable
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import yaml
from enum import Enum

logger = logging.getLogger(__name__)


class PerformanceLevel(Enum):
    """性能级别"""
    MINIMAL = "minimal"
    STANDARD = "standard"
    HIGH_PERFORMANCE = "high_performance"
    MAXIMUM = "maximum"


@dataclass
class SystemConfiguration:
    """系统配置"""
    # 进程配置
    max_concurrent_builds: int = 3
    max_concurrent_tasks: int = 10

    # 资源限制
    max_memory_per_build: int = 2048  # MB
    max_cpu_per_build: int = 100  # 百分比
    max_build_time: int = 1800  # 秒

    # 缓存配置
    enable_build_cache: bool = True
    cache_size_limit: int = 1024  # MB
    cache_ttl: int = 86400  # 秒

    # 监控配置
    enable_monitoring: bool = True
    monitoring_interval: float = 5.0  # 秒
    enable_auto_scaling: bool = False

    # 优化配置
    enable_gradle_daemon: bool = True
    enable_gradle_parallel: bool = True
    gradle_heap_size: str = "2g"
    gradle_opts: str = "-XX:+UseG1GC"

    # 网络配置
    download_timeout: int = 300  # 秒
    upload_timeout: int = 300  # 秒
    max_file_size: int = 100  # MB


@dataclass
class PerformanceMetrics:
    """性能指标"""
    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_io: Dict[str, float]
    active_builds: int
    queued_builds: int
    completed_builds: int
    failed_builds: int
    avg_build_time: float
    cache_hit_rate: float


class PerformanceOptimizer:
    """性能优化器"""

    def __init__(self, config: SystemConfiguration):
        self.config = config
        self.metrics_history: List[PerformanceMetrics] = []
        self.optimization_callbacks: List[Callable[[], None]] = []
        self.is_monitoring = False
        self.monitor_task: Optional[asyncio.Task] = None

    async def start_monitoring(self):
        """开始性能监控"""
        self.is_monitoring = True
        self.monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info("性能监控已启动")

    async def stop_monitoring(self):
        """停止性能监控"""
        self.is_monitoring = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("性能监控已停止")

    async def _monitoring_loop(self):
        """监控循环"""
        while self.is_monitoring:
            try:
                metrics = await self._collect_metrics()
                self.metrics_history.append(metrics)

                # 保持历史记录在合理范围内
                if len(self.metrics_history) > 1000:
                    self.metrics_history = self.metrics_history[-500:]

                # 自动优化
                if self.config.enable_auto_scaling:
                    await self._auto_optimize(metrics)

                await asyncio.sleep(self.config.monitoring_interval)

            except Exception as e:
                logger.error(f"性能监控错误: {e}")
                await asyncio.sleep(10.0)

    async def _collect_metrics(self) -> PerformanceMetrics:
        """收集性能指标"""
        try:
            # 系统资源
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            # 网络IO
            net_io = psutil.net_io_counters()

            # 构建统计（这里需要从实际构建管理器获取）
            active_builds = 0  # 从build_manager获取
            queued_builds = 0
            completed_builds = 0
            failed_builds = 0
            avg_build_time = 0.0
            cache_hit_rate = 0.0

            return PerformanceMetrics(
                timestamp=datetime.now(),
                cpu_usage=cpu_percent,
                memory_usage=memory.percent,
                disk_usage=disk.percent,
                network_io={
                    'bytes_sent': net_io.bytes_sent,
                    'bytes_recv': net_io.bytes_recv
                },
                active_builds=active_builds,
                queued_builds=queued_builds,
                completed_builds=completed_builds,
                failed_builds=failed_builds,
                avg_build_time=avg_build_time,
                cache_hit_rate=cache_hit_rate
            )

        except Exception as e:
            logger.error(f"收集性能指标失败: {e}")
            # 返回默认指标
            return PerformanceMetrics(
                timestamp=datetime.now(),
                cpu_usage=0.0,
                memory_usage=0.0,
                disk_usage=0.0,
                network_io={},
                active_builds=0,
                queued_builds=0,
                completed_builds=0,
                failed_builds=0,
                avg_build_time=0.0,
                cache_hit_rate=0.0
            )

    async def _auto_optimize(self, metrics: PerformanceMetrics):
        """自动优化"""
        optimizations = []

        # CPU使用率优化
        if metrics.cpu_usage > 80:
            if self.config.max_concurrent_builds > 1:
                self.config.max_concurrent_builds = max(1, self.config.max_concurrent_builds - 1)
                optimizations.append("减少并发构建数量")

        # 内存使用优化
        if metrics.memory_usage > 85:
            # 强制垃圾回收
            import gc
            gc.collect()

            # 减少内存限制
            if self.config.max_memory_per_build > 1024:
                self.config.max_memory_per_build = max(512, self.config.max_memory_per_build - 256)
                optimizations.append("降低构建内存限制")

        # 磁盘空间优化
        if metrics.disk_usage > 90:
            await self._cleanup_cache()
            optimizations.append("清理缓存释放磁盘空间")

        # 应用优化
        if optimizations:
            logger.info(f"自动优化执行: {', '.join(optimizations)}")
            for callback in self.optimization_callbacks:
                try:
                    callback()
                except Exception as e:
                    logger.error(f"优化回调错误: {e}")

    async def _cleanup_cache(self):
        """清理缓存"""
        try:
            cache_dir = Path("cache")
            if cache_dir.exists():
                # 删除超过TTL的缓存文件
                now = datetime.now()
                ttl = timedelta(seconds=self.config.cache_ttl)

                for cache_file in cache_dir.rglob("*"):
                    if cache_file.is_file():
                        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
                        if now - mtime > ttl:
                            cache_file.unlink()

        except Exception as e:
            logger.error(f"清理缓存失败: {e}")

    def add_optimization_callback(self, callback: Callable[[], None]):
        """添加优化回调"""
        self.optimization_callbacks.append(callback)

    def get_current_metrics(self) -> Optional[PerformanceMetrics]:
        """获取当前指标"""
        return self.metrics_history[-1] if self.metrics_history else None

    def get_metrics_summary(self, hours: int = 1) -> Dict[str, Any]:
        """获取指标摘要"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_metrics = [
            m for m in self.metrics_history
            if m.timestamp > cutoff_time
        ]

        if not recent_metrics:
            return {}

        return {
            'avg_cpu_usage': sum(m.cpu_usage for m in recent_metrics) / len(recent_metrics),
            'avg_memory_usage': sum(m.memory_usage for m in recent_metrics) / len(recent_metrics),
            'peak_cpu_usage': max(m.cpu_usage for m in recent_metrics),
            'peak_memory_usage': max(m.memory_usage for m in recent_metrics),
            'total_builds': sum(m.completed_builds for m in recent_metrics),
            'failed_build_rate': sum(m.failed_builds for m in recent_metrics) / max(1, sum(m.completed_builds for m in recent_metrics)) * 100,
            'avg_build_time': sum(m.avg_build_time for m in recent_metrics) / len(recent_metrics),
            'sample_count': len(recent_metrics)
        }


class ConfigurationOptimizer:
    """配置优化器"""

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.performance_level = PerformanceLevel.STANDARD

    def _load_config(self) -> SystemConfiguration:
        """加载配置"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    return SystemConfiguration(**data)
            except Exception as e:
                logger.error(f"加载配置失败: {e}")

        return SystemConfiguration()

    def save_config(self):
        """保存配置"""
        try:
            config_dict = {
                'max_concurrent_builds': self.config.max_concurrent_builds,
                'max_concurrent_tasks': self.config.max_concurrent_tasks,
                'max_memory_per_build': self.config.max_memory_per_build,
                'max_cpu_per_build': self.config.max_cpu_per_build,
                'max_build_time': self.config.max_build_time,
                'enable_build_cache': self.config.enable_build_cache,
                'cache_size_limit': self.config.cache_size_limit,
                'cache_ttl': self.config.cache_ttl,
                'enable_monitoring': self.config.enable_monitoring,
                'monitoring_interval': self.config.monitoring_interval,
                'enable_auto_scaling': self.config.enable_auto_scaling,
                'enable_gradle_daemon': self.config.enable_gradle_daemon,
                'enable_gradle_parallel': self.config.enable_gradle_parallel,
                'gradle_heap_size': self.config.gradle_heap_size,
                'gradle_opts': self.config.gradle_opts,
                'download_timeout': self.config.download_timeout,
                'upload_timeout': self.config.upload_timeout,
                'max_file_size': self.config.max_file_size
            }

            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)

            logger.info(f"配置已保存到: {self.config_path}")

        except Exception as e:
            logger.error(f"保存配置失败: {e}")

    def optimize_for_system(self):
        """根据系统资源优化配置"""
        try:
            # 获取系统信息
            cpu_count = psutil.cpu_count()
            memory_gb = psutil.virtual_memory().total / (1024**3)
            disk_gb = psutil.disk_usage('/').total / (1024**3)

            # CPU优化
            if cpu_count >= 8:
                self.config.max_concurrent_builds = min(6, cpu_count // 2)
            elif cpu_count >= 4:
                self.config.max_concurrent_builds = 3
            else:
                self.config.max_concurrent_builds = 1

            # 内存优化
            if memory_gb >= 16:
                self.config.max_memory_per_build = 4096
                self.config.gradle_heap_size = "4g"
            elif memory_gb >= 8:
                self.config.max_memory_per_build = 2048
                self.config.gradle_heap_size = "2g"
            elif memory_gb >= 4:
                self.config.max_memory_per_build = 1024
                self.config.gradle_heap_size = "1g"
            else:
                self.config.max_memory_per_build = 512
                self.config.gradle_heap_size = "512m"

            # 磁盘优化
            if disk_gb >= 100:
                self.config.cache_size_limit = 2048
            elif disk_gb >= 50:
                self.config.cache_size_limit = 1024
            else:
                self.config.cache_size_limit = 512

            logger.info(f"系统优化完成 - CPU: {cpu_count}, 内存: {memory_gb:.1f}GB, 磁盘: {disk_gb:.1f}GB")

        except Exception as e:
            logger.error(f"系统优化失败: {e}")

    def set_performance_level(self, level: PerformanceLevel):
        """设置性能级别"""
        self.performance_level = level

        if level == PerformanceLevel.MINIMAL:
            self.config.max_concurrent_builds = 1
            self.config.max_memory_per_build = 512
            self.config.enable_gradle_parallel = False
            self.config.gradle_heap_size = "512m"

        elif level == PerformanceLevel.STANDARD:
            self.config.max_concurrent_builds = 2
            self.config.max_memory_per_build = 1024
            self.config.enable_gradle_parallel = True
            self.config.gradle_heap_size = "1g"

        elif level == PerformanceLevel.HIGH_PERFORMANCE:
            self.config.max_concurrent_builds = 4
            self.config.max_memory_per_build = 2048
            self.config.enable_gradle_parallel = True
            self.config.gradle_heap_size = "2g"

        elif level == PerformanceLevel.MAXIMUM:
            cpu_count = psutil.cpu_count()
            self.config.max_concurrent_builds = cpu_count
            self.config.max_memory_per_build = 4096
            self.config.enable_gradle_parallel = True
            self.config.gradle_heap_size = "4g"

        logger.info(f"性能级别设置为: {level.value}")

    def get_gradle_properties(self) -> Dict[str, str]:
        """获取Gradle属性配置"""
        properties = {}

        if self.config.enable_gradle_daemon:
            properties['org.gradle.daemon'] = 'true'

        if self.config.enable_gradle_parallel:
            properties['org.gradle.parallel'] = 'true'

        properties['org.gradle.jvmargs'] = f"-Xmx{self.config.gradle_heap_size} {self.config.gradle_opts}"
        properties['org.gradle.caching'] = str(self.config.enable_build_cache).lower()
        properties['org.gradle.configureondemand'] = 'true'

        return properties

    def generate_gradle_properties_file(self, project_path: str):
        """生成gradle.properties文件"""
        project_dir = Path(project_path)
        gradle_props_path = project_dir / "gradle.properties"

        properties = self.get_gradle_properties()

        try:
            with open(gradle_props_path, 'w', encoding='utf-8') as f:
                for key, value in properties.items():
                    f.write(f"{key}={value}\n")

            logger.info(f"gradle.properties已生成: {gradle_props_path}")

        except Exception as e:
            logger.error(f"生成gradle.properties失败: {e}")


class CacheManager:
    """缓存管理器"""

    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_index: Dict[str, Dict[str, Any]] = {}
        self._load_cache_index()

    def _load_cache_index(self):
        """加载缓存索引"""
        index_file = self.cache_dir / "index.json"
        if index_file.exists():
            try:
                with open(index_file, 'r') as f:
                    self.cache_index = json.load(f)
            except Exception as e:
                logger.error(f"加载缓存索引失败: {e}")

    def _save_cache_index(self):
        """保存缓存索引"""
        index_file = self.cache_dir / "index.json"
        try:
            with open(index_file, 'w') as f:
                json.dump(self.cache_index, f, indent=2)
        except Exception as e:
            logger.error(f"保存缓存索引失败: {e}")

    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if key not in self.cache_index:
            return None

        cache_info = self.cache_index[key]
        cache_file = self.cache_dir / cache_info['filename']

        if not cache_file.exists():
            del self.cache_index[key]
            self._save_cache_index()
            return None

        # 检查TTL
        if datetime.now() > datetime.fromisoformat(cache_info['expires_at']):
            cache_file.unlink()
            del self.cache_index[key]
            self._save_cache_index()
            return None

        try:
            with open(cache_file, 'rb') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"读取缓存失败: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int = 3600):
        """设置缓存"""
        cache_info = {
            'filename': f"{key.replace('/', '_')}.json",
            'created_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(seconds=ttl)).isoformat(),
            'size': 0
        }

        cache_file = self.cache_dir / cache_info['filename']

        try:
            with open(cache_file, 'w') as f:
                json.dump(value, f)

            cache_info['size'] = cache_file.stat().st_size
            self.cache_index[key] = cache_info
            self._save_cache_index()

        except Exception as e:
            logger.error(f"写入缓存失败: {e}")

    def delete(self, key: str):
        """删除缓存"""
        if key in self.cache_index:
            cache_info = self.cache_index[key]
            cache_file = self.cache_dir / cache_info['filename']

            if cache_file.exists():
                cache_file.unlink()

            del self.cache_index[key]
            self._save_cache_index()

    def cleanup(self):
        """清理过期缓存"""
        now = datetime.now()
        keys_to_delete = []

        for key, cache_info in self.cache_index.items():
            if now > datetime.fromisoformat(cache_info['expires_at']):
                cache_file = self.cache_dir / cache_info['filename']
                if cache_file.exists():
                    cache_file.unlink()
                keys_to_delete.append(key)

        for key in keys_to_delete:
            del self.cache_index[key]

        if keys_to_delete:
            self._save_cache_index()
            logger.info(f"清理了 {len(keys_to_delete)} 个过期缓存项")

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total_size = sum(info['size'] for info in self.cache_index.values())
        total_count = len(self.cache_index)

        return {
            'total_items': total_count,
            'total_size_mb': total_size / (1024 * 1024),
            'cache_dir': str(self.cache_dir)
        }


# 性能优化建议
class PerformanceAdvisor:
    """性能顾问"""

    @staticmethod
    def analyze_system() -> Dict[str, Any]:
        """分析系统性能"""
        try:
            cpu_count = psutil.cpu_count()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            recommendations = []

            # CPU建议
            if cpu_count < 4:
                recommendations.append("CPU核心数较少，建议升级CPU以提升并发构建能力")

            # 内存建议
            if memory.total < 8 * 1024**3:
                recommendations.append("内存小于8GB，建议增加内存以支持更多并发构建")

            # 磁盘建议
            if disk.free < 50 * 1024**3:
                recommendations.append("可用磁盘空间不足50GB，建议清理磁盘或扩容")

            # 系统负载
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > 80:
                recommendations.append("当前CPU使用率过高，建议减少并发任务")

            return {
                'cpu_count': cpu_count,
                'memory_gb': memory.total / (1024**3),
                'disk_free_gb': disk.free / (1024**3),
                'cpu_usage': cpu_percent,
                'memory_usage': memory.percent,
                'recommendations': recommendations
            }

        except Exception as e:
            logger.error(f"系统分析失败: {e}")
            return {'error': str(e)}

    @staticmethod
    def generate_optimization_plan(analysis: Dict[str, Any]) -> Dict[str, Any]:
        """生成优化计划"""
        plan = {
            'immediate_actions': [],
            'short_term_improvements': [],
            'long_term_investments': []
        }

        if 'error' in analysis:
            return plan

        # 即时行动
        if analysis.get('cpu_usage', 0) > 80:
            plan['immediate_actions'].append("减少并发构建数量到CPU核心数的一半")

        if analysis.get('memory_usage', 0) > 85:
            plan['immediate_actions'].append("增加Java堆大小或减少并发构建")

        # 短期改进
        if analysis.get('memory_gb', 0) < 8:
            plan['short_term_improvements'].append("启用更激进的缓存策略")
            plan['short_term_improvements'].append("优化Gradle配置以减少内存使用")

        # 长期投资
        if analysis.get('cpu_count', 0) < 4:
            plan['long_term_investments'].append("升级到多核CPU (至少4核)")

        if analysis.get('memory_gb', 0) < 16:
            plan['long_term_investments'].append("升级到16GB或更多内存")

        return plan


# 使用示例
async def example_performance_optimization():
    """性能优化示例"""

    # 创建配置优化器
    config_optimizer = ConfigurationOptimizer()

    # 根据系统优化配置
    config_optimizer.optimize_for_system()

    # 设置性能级别
    config_optimizer.set_performance_level(PerformanceLevel.HIGH_PERFORMANCE)

    # 保存配置
    config_optimizer.save_config()

    # 生成Gradle配置
    config_optimizer.generate_gradle_properties_file("/path/to/project")

    # 创建性能优化器
    optimizer = PerformanceOptimizer(config_optimizer.config)
    await optimizer.start_monitoring()

    # 创建缓存管理器
    cache_manager = CacheManager()

    # 使用缓存
    cache_manager.set("test_key", {"data": "test_value"}, ttl=3600)
    cached_data = cache_manager.get("test_key")

    # 获取系统建议
    advisor = PerformanceAdvisor()
    system_analysis = advisor.analyze_system()
    optimization_plan = advisor.generate_optimization_plan(system_analysis)

    print("系统分析结果:")
    print(json.dumps(system_analysis, indent=2))

    print("\n优化计划:")
    print(json.dumps(optimization_plan, indent=2))

    # 获取性能指标摘要
    await asyncio.sleep(10)  # 等待一些指标收集
    metrics_summary = optimizer.get_metrics_summary()
    print(f"\n性能指标摘要: {metrics_summary}")

    # 清理
    await optimizer.stop_monitoring()


if __name__ == "__main__":
    asyncio.run(example_performance_optimization())