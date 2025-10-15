"""
长时间运行任务的超时和中断处理模块
提供智能超时管理、资源监控、优雅降级等功能
"""

import asyncio
import signal
import psutil
import os
import time
import threading
from typing import Dict, Any, Optional, Callable, List, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import logging
from contextlib import asynccontextmanager
import weakref
import gc

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """任务优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    RESOURCE_EXHAUSTED = "resource_exhausted"


@dataclass
class ResourceLimits:
    """资源限制配置"""
    max_memory_mb: int = 2048  # 最大内存使用(MB)
    max_cpu_percent: float = 80.0  # 最大CPU使用率
    max_disk_space_mb: int = 10240  # 最大磁盘空间(MB)
    max_open_files: int = 1000  # 最大文件句柄数
    memory_check_interval: float = 5.0  # 内存检查间隔(秒)
    cpu_check_interval: float = 2.0  # CPU检查间隔(秒)


@dataclass
class TimeoutConfig:
    """超时配置"""
    default_timeout: int = 600  # 默认超时(秒)
    max_timeout: int = 3600  # 最大超时(秒)
    warning_threshold: float = 0.8  # 警告阈值(百分比)
    check_interval: float = 10.0  # 检查间隔(秒)
    enable_smart_timeout: bool = True  # 启用智能超时


@dataclass
class TaskMetrics:
    """任务指标"""
    task_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    peak_memory_mb: float = 0.0
    peak_cpu_percent: float = 0.0
    avg_memory_mb: float = 0.0
    avg_cpu_percent: float = 0.0
    timeout_extensions: int = 0
    resource_violations: List[str] = field(default_factory=list)


class ResourceMonitor:
    """资源监控器"""

    def __init__(self, resource_limits: ResourceLimits):
        self.limits = resource_limits
        self.is_monitoring = False
        self.monitor_task: Optional[asyncio.Task] = None
        self.callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self.current_process = psutil.Process()

    async def start_monitoring(self):
        """开始监控"""
        self.is_monitoring = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())

    async def stop_monitoring(self):
        """停止监控"""
        self.is_monitoring = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

    def add_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """添加监控回调"""
        self.callbacks.append(callback)

    async def _monitor_loop(self):
        """监控循环"""
        while self.is_monitoring:
            try:
                metrics = await self._collect_metrics()

                # 检查资源限制
                violations = self._check_violations(metrics)

                # 通知回调
                for callback in self.callbacks:
                    try:
                        await asyncio.get_event_loop().run_in_executor(
                            None, callback, {
                                'metrics': metrics,
                                'violations': violations,
                                'timestamp': datetime.now()
                            }
                        )
                    except Exception as e:
                        logger.error(f"监控回调错误: {e}")

                await asyncio.sleep(min(
                    self.limits.memory_check_interval,
                    self.limits.cpu_check_interval
                ))

            except Exception as e:
                logger.error(f"资源监控错误: {e}")
                await asyncio.sleep(5.0)

    async def _collect_metrics(self) -> Dict[str, Any]:
        """收集资源指标"""
        try:
            # 内存使用
            memory_info = self.current_process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)
            memory_percent = self.current_process.memory_percent()

            # CPU使用
            cpu_percent = self.current_process.cpu_percent()

            # 磁盘使用
            disk_usage = psutil.disk_usage('.')
            disk_free_mb = disk_usage.free / (1024 * 1024)

            # 文件句柄数
            num_files = len(self.current_process.open_files())

            return {
                'memory_mb': memory_mb,
                'memory_percent': memory_percent,
                'cpu_percent': cpu_percent,
                'disk_free_mb': disk_free_mb,
                'open_files': num_files,
                'process_id': os.getpid(),
                'thread_count': self.current_process.num_threads()
            }

        except Exception as e:
            logger.error(f"收集资源指标失败: {e}")
            return {}

    def _check_violations(self, metrics: Dict[str, Any]) -> List[str]:
        """检查资源违规"""
        violations = []

        if metrics.get('memory_mb', 0) > self.limits.max_memory_mb:
            violations.append(f"内存超限: {metrics['memory_mb']:.1f}MB > {self.limits.max_memory_mb}MB")

        if metrics.get('cpu_percent', 0) > self.limits.max_cpu_percent:
            violations.append(f"CPU超限: {metrics['cpu_percent']:.1f}% > {self.limits.max_cpu_percent}%")

        if metrics.get('disk_free_mb', 0) < (self.limits.max_disk_space_mb / 2):
            violations.append(f"磁盘空间不足: {metrics['disk_free_mb']:.1f}MB")

        if metrics.get('open_files', 0) > self.limits.max_open_files:
            violations.append(f"文件句柄超限: {metrics['open_files']} > {self.limits.max_open_files}")

        return violations


class SmartTimeoutManager:
    """智能超时管理器"""

    def __init__(self, config: TimeoutConfig):
        self.config = config
        self.active_tasks: Dict[str, Dict[str, Any]] = {}
        self.timeout_task: Optional[asyncio.Task] = None
        self.is_running = False

    async def start(self):
        """启动超时管理器"""
        self.is_running = True
        self.timeout_task = asyncio.create_task(self._timeout_loop())

    async def stop(self):
        """停止超时管理器"""
        self.is_running = False
        if self.timeout_task:
            self.timeout_task.cancel()
            try:
                await self.timeout_task
            except asyncio.CancelledError:
                pass

    def register_task(
        self,
        task_id: str,
        timeout: Optional[int] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        progress_callback: Optional[Callable[[float], None]] = None
    ):
        """注册任务"""
        task_timeout = timeout or self.config.default_timeout
        task_timeout = min(task_timeout, self.config.max_timeout)

        self.active_tasks[task_id] = {
            'task_id': task_id,
            'start_time': datetime.now(),
            'timeout': task_timeout,
            'deadline': datetime.now() + timedelta(seconds=task_timeout),
            'priority': priority,
            'progress_callback': progress_callback,
            'extended': False,
            'warnings_sent': [],
            'last_activity': datetime.now()
        }

        logger.info(f"任务已注册超时管理: {task_id}, 超时: {task_timeout}秒")

    def unregister_task(self, task_id: str):
        """注销任务"""
        if task_id in self.active_tasks:
            del self.active_tasks[task_id]
            logger.info(f"任务已注销超时管理: {task_id}")

    def update_progress(self, task_id: str, progress: float):
        """更新任务进度"""
        if task_id in self.active_tasks:
            task_info = self.active_tasks[task_id]
            task_info['last_activity'] = datetime.now()

            # 智能超时：根据进度调整超时
            if self.config.enable_smart_timeout and progress > 0:
                elapsed = (datetime.now() - task_info['start_time']).total_seconds()
                estimated_total = elapsed / progress if progress > 0 else task_info['timeout']
                remaining_time = estimated_total - elapsed

                # 如果估计需要更多时间，适当延长超时
                if remaining_time > task_info['timeout'] * 0.3:
                    extension = min(remaining_time * 0.5, self.config.max_timeout - task_info['timeout'])
                    new_deadline = task_info['deadline'] + timedelta(seconds=extension)

                    if new_deadline > task_info['deadline']:
                        task_info['deadline'] = new_deadline
                        task_info['extended'] = True
                        logger.info(f"任务超时已延长: {task_id}, 延长: {extension:.1f}秒")

            # 调用进度回调
            if task_info['progress_callback']:
                try:
                    task_info['progress_callback'](progress)
                except Exception as e:
                    logger.error(f"进度回调错误: {e}")

    async def _timeout_loop(self):
        """超时检查循环"""
        while self.is_running:
            try:
                await self._check_timeouts()
                await asyncio.sleep(self.config.check_interval)
            except Exception as e:
                logger.error(f"超时检查错误: {e}")
                await asyncio.sleep(5.0)

    async def _check_timeouts(self):
        """检查超时任务"""
        now = datetime.now()

        for task_id, task_info in list(self.active_tasks.items()):
            try:
                # 计算剩余时间
                remaining = (task_info['deadline'] - now).total_seconds()
                total_timeout = task_info['timeout']
                elapsed = (now - task_info['start_time']).total_seconds()
                progress_ratio = elapsed / total_timeout

                # 发送警告
                if (progress_ratio >= self.config.warning_threshold and
                    'warning' not in task_info['warnings_sent']):

                    await self._send_timeout_warning(task_id, remaining)
                    task_info['warnings_sent'].append('warning')

                # 检查超时
                if remaining <= 0:
                    await self._handle_timeout(task_id)
                    self.unregister_task(task_id)

            except Exception as e:
                logger.error(f"检查任务超时失败 {task_id}: {e}")

    async def _send_timeout_warning(self, task_id: str, remaining: float):
        """发送超时警告"""
        logger.warning(f"任务即将超时: {task_id}, 剩余时间: {remaining:.1f}秒")

        # 这里可以发送WebSocket通知或其他警告机制
        # 例如：await notification_service.send_warning(task_id, remaining)

    async def _handle_timeout(self, task_id: str):
        """处理超时任务"""
        logger.error(f"任务超时: {task_id}")

        # 这里可以触发任务取消或标记为超时
        # 例如：await task_canceler.cancel_task(task_id)


class LongRunningTaskManager:
    """长时间运行任务管理器"""

    def __init__(
        self,
        resource_limits: ResourceLimits = None,
        timeout_config: TimeoutConfig = None
    ):
        self.resource_limits = resource_limits or ResourceLimits()
        self.timeout_config = timeout_config or TimeoutConfig()

        self.resource_monitor = ResourceMonitor(self.resource_limits)
        self.timeout_manager = SmartTimeoutManager(self.timeout_config)

        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.is_running = False

    async def start(self):
        """启动任务管理器"""
        self.is_running = True

        await self.resource_monitor.start_monitoring()
        await self.timeout_manager.start()

        # 设置资源监控回调
        self.resource_monitor.add_callback(self._resource_violation_handler)

        logger.info("长时间运行任务管理器已启动")

    async def stop(self):
        """停止任务管理器"""
        self.is_running = False

        # 取消所有活跃任务
        for task_id in list(self.tasks.keys()):
            await self.cancel_task(task_id)

        await self.resource_monitor.stop_monitoring()
        await self.timeout_manager.stop()

        logger.info("长时间运行任务管理器已停止")

    @asynccontextmanager
    async def managed_task(
        self,
        task_id: str,
        timeout: Optional[int] = None,
        priority: TaskPriority = TaskPriority.NORMAL
    ):
        """托管任务上下文管理器"""

        # 创建任务指标
        metrics = TaskMetrics(task_id=task_id, start_time=datetime.now())
        self.tasks[task_id] = {
            'metrics': metrics,
            'coroutine': None,
            'task': None,
            'cancelled': False
        }

        # 注册超时管理
        self.timeout_manager.register_task(
            task_id, timeout, priority,
            lambda p: self._update_progress(task_id, p)
        )

        try:
            yield self
        finally:
            # 清理任务
            await self._cleanup_task(task_id)

    async def execute_task(
        self,
        task_id: str,
        coro,
        timeout: Optional[int] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> Any:
        """执行长时间运行任务"""

        metrics = TaskMetrics(task_id=task_id, start_time=datetime.now())

        self.tasks[task_id] = {
            'metrics': metrics,
            'coroutine': coro,
            'task': None,
            'cancelled': False,
            'progress_callback': progress_callback
        }

        # 注册超时管理
        self.timeout_manager.register_task(
            task_id, timeout, priority,
            lambda p: self._update_progress(task_id, p)
        )

        try:
            # 创建任务
            task = asyncio.create_task(
                self._execute_with_monitoring(task_id, coro)
            )
            self.tasks[task_id]['task'] = task

            # 等待任务完成
            result = await task

            # 更新指标
            metrics.end_time = datetime.now()
            metrics.duration = (metrics.end_time - metrics.start_time).total_seconds()

            return result

        except asyncio.CancelledError:
            metrics.end_time = datetime.now()
            metrics.duration = (metrics.end_time - metrics.start_time).total_seconds()
            raise

        except Exception as e:
            metrics.end_time = datetime.now()
            metrics.duration = (metrics.end_time - metrics.start_time).total_seconds()
            raise

        finally:
            await self._cleanup_task(task_id)

    async def _execute_with_monitoring(self, task_id: str, coro):
        """带监控的任务执行"""
        start_time = time.time()
        memory_samples = []
        cpu_samples = []

        try:
            # 开始资源监控
            process = psutil.Process()

            # 执行任务
            async for progress, result in self._execute_with_progress(coro):
                # 收集资源指标
                memory_mb = process.memory_info().rss / (1024 * 1024)
                cpu_percent = process.cpu_percent()

                memory_samples.append(memory_mb)
                cpu_samples.append(cpu_percent)

                # 更新进度
                self.timeout_manager.update_progress(task_id, progress)

                # 调用进度回调
                if task_id in self.tasks:
                    progress_callback = self.tasks[task_id].get('progress_callback')
                    if progress_callback:
                        try:
                            progress_callback(progress)
                        except Exception as e:
                            logger.error(f"进度回调错误: {e}")

            return result

        finally:
            # 计算最终指标
            if memory_samples:
                metrics = self.tasks[task_id]['metrics']
                metrics.peak_memory_mb = max(memory_samples)
                metrics.avg_memory_mb = sum(memory_samples) / len(memory_samples)
                metrics.peak_cpu_percent = max(cpu_samples)
                metrics.avg_cpu_percent = sum(cpu_samples) / len(cpu_samples)

    async def _execute_with_progress(self, coro):
        """执行协程并提取进度信息"""
        # 这是一个简化的实现，实际使用中需要根据具体的协程类型来实现
        # 可以通过YIELD语句或回调来报告进度

        try:
            result = await coro
            yield 100.0, result  # 完成时返回100%进度
        except Exception as e:
            raise

    def _update_progress(self, task_id: str, progress: float):
        """更新任务进度"""
        if task_id in self.tasks:
            metrics = self.tasks[task_id]['metrics']
            # 这里可以更新更多进度相关的指标

    async def _resource_violation_handler(self, data: Dict[str, Any]):
        """资源违规处理器"""
        violations = data.get('violations', [])

        if violations:
            logger.warning(f"检测到资源违规: {violations}")

            # 采取降级措施
            await self._handle_resource_violations(violations)

    async def _handle_resource_violations(self, violations: List[str]):
        """处理资源违规"""
        for violation in violations:
            if "内存超限" in violation:
                # 强制垃圾回收
                gc.collect()

                # 降低低优先级任务的优先级
                await self._throttle_low_priority_tasks()

            elif "CPU超限" in violation:
                # 降低CPU密集型任务的优先级
                await self._throttle_cpu_intensive_tasks()

    async def _throttle_low_priority_tasks(self):
        """限制低优先级任务"""
        # 实现任务限制逻辑
        pass

    async def _throttle_cpu_intensive_tasks(self):
        """限制CPU密集型任务"""
        # 实现CPU限制逻辑
        pass

    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        if task_id not in self.tasks:
            return False

        task_info = self.tasks[task_id]
        task_info['cancelled'] = True

        # 取消异步任务
        task = task_info.get('task')
        if task and not task.done():
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

        # 注销超时管理
        self.timeout_manager.unregister_task(task_id)

        logger.info(f"任务已取消: {task_id}")
        return True

    async def _cleanup_task(self, task_id: str):
        """清理任务资源"""
        # 注销超时管理
        self.timeout_manager.unregister_task(task_id)

        # 移除任务
        self.tasks.pop(task_id, None)

        logger.info(f"任务已清理: {task_id}")

    def get_task_metrics(self, task_id: str) -> Optional[TaskMetrics]:
        """获取任务指标"""
        if task_id in self.tasks:
            return self.tasks[task_id]['metrics']
        return None

    def get_active_tasks(self) -> Dict[str, Dict[str, Any]]:
        """获取活跃任务"""
        return {
            task_id: {
                'status': 'running',
                'start_time': info['metrics'].start_time,
                'duration': (datetime.now() - info['metrics'].start_time).total_seconds(),
                'peak_memory_mb': info['metrics'].peak_memory_mb,
                'peak_cpu_percent': info['metrics'].peak_cpu_percent
            }
            for task_id, info in self.tasks.items()
        }


# 使用示例
async def example_long_running_task():
    """长时间运行任务示例"""

    # 创建任务管理器
    resource_limits = ResourceLimits(
        max_memory_mb=1024,
        max_cpu_percent=75.0,
        memory_check_interval=2.0
    )

    timeout_config = TimeoutConfig(
        default_timeout=300,
        enable_smart_timeout=True
    )

    task_manager = LongRunningTaskManager(resource_limits, timeout_config)
    await task_manager.start()

    try:
        # 执行长时间运行的任务
        async def gradle_build_task():
            """模拟Gradle构建任务"""
            print("开始Gradle构建...")

            for i in range(101):
                # 模拟构建进度
                await asyncio.sleep(0.1)

                # 检查是否被取消
                if asyncio.current_task().cancelled():
                    break

                yield i / 100.0, None

            return {"status": "success", "apk_path": "/path/to/app.apk"}

        # 执行任务
        result = await task_manager.execute_task(
            "build_001",
            gradle_build_task(),
            timeout=600,
            priority=TaskPriority.HIGH,
            progress_callback=lambda p: print(f"构建进度: {p:.1f}%")
        )

        print(f"构建完成: {result}")

        # 获取任务指标
        metrics = task_manager.get_task_metrics("build_001")
        if metrics:
            print(f"峰值内存: {metrics.peak_memory_mb:.1f}MB")
            print(f"峰值CPU: {metrics.peak_cpu_percent:.1f}%")

    finally:
        await task_manager.stop()


if __name__ == "__main__":
    asyncio.run(example_long_running_task())