"""
Gradle构建过程监控系统
提供异步执行、实时日志流、生命周期管理等功能
"""

import asyncio
import json
import re
import time
from typing import (
    AsyncGenerator, Optional, Dict, Any, List, Callable,
    Union, Set, Tuple
)
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import logging
import signal
import uuid
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BuildStatus(Enum):
    """构建状态枚举"""
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class BuildProgress:
    """构建进度信息"""
    current_step: str = ""
    total_steps: int = 0
    completed_steps: int = 0
    percentage: float = 0.0
    current_file: str = ""
    estimated_time_remaining: Optional[int] = None


@dataclass
class BuildResult:
    """构建结果"""
    build_id: str
    status: BuildStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    apk_path: Optional[str] = None
    error_message: Optional[str] = None
    logs: List[str] = field(default_factory=list)
    progress: BuildProgress = field(default_factory=BuildProgress)
    metadata: Dict[str, Any] = field(default_factory=dict)


class GradleLogParser:
    """Gradle日志解析器"""

    def __init__(self):
        # 正则表达式模式
        self.patterns = {
            'task_start': re.compile(r'> Task\s:(\w+)'),
            'task_complete': re.compile(r'(\w+)\s+UP-TO-DATE|(\w+)\s+(?:SUCCESS|FAILED)'),
            'progress': re.compile(r'(\d+)%'),
            'error': re.compile(r'FAILURE:\s+(.+)', re.MULTILINE),
            'warning': re.compile(r'WARNING:\s+(.+)', re.MULTILINE),
            'apk_output': re.compile(r'Output:\s*(.*\.apk)'),
            'build_complete': re.compile(r'BUILD\s+(SUCCESSFUL|FAILED)'),
            'execution_time': re.compile(r'Total time:\s+([\d.]+)\s+secs')
        }

    def parse_log_line(self, line: str) -> Dict[str, Any]:
        """解析单行日志"""
        result = {
            'type': 'info',
            'content': line,
            'timestamp': datetime.now(),
            'task': None,
            'progress': None,
            'is_error': False,
            'is_warning': False
        }

        # 检查任务开始
        task_match = self.patterns['task_start'].search(line)
        if task_match:
            result['type'] = 'task_start'
            result['task'] = task_match.group(1)

        # 检查进度
        progress_match = self.patterns['progress'].search(line)
        if progress_match:
            result['progress'] = int(progress_match.group(1))

        # 检查错误
        error_match = self.patterns['error'].search(line)
        if error_match:
            result['type'] = 'error'
            result['is_error'] = True
            result['error_message'] = error_match.group(1)

        # 检查警告
        warning_match = self.patterns['warning'].search(line)
        if warning_match:
            result['type'] = 'warning'
            result['is_warning'] = True
            result['warning_message'] = warning_match.group(1)

        # 检查APK输出
        apk_match = self.patterns['apk_output'].search(line)
        if apk_match:
            result['type'] = 'apk_output'
            result['apk_path'] = apk_match.group(1)

        # 检查构建完成
        build_match = self.patterns['build_complete'].search(line)
        if build_match:
            result['type'] = 'build_complete'
            result['success'] = build_match.group(1) == 'SUCCESSFUL'

        return result


class GradleAsyncExecutor:
    """基于asyncio的Gradle异步执行器"""

    def __init__(self, project_path: str, timeout: int = 600):
        self.project_path = Path(project_path)
        self.timeout = timeout
        self.process: Optional[asyncio.subprocess.Process] = None
        self.log_parser = GradleLogParser()
        self._is_cancelled = False

    async def execute_build(
        self,
        tasks: List[str],
        log_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        progress_callback: Optional[Callable[[BuildProgress], None]] = None
    ) -> BuildResult:
        """执行Gradle构建"""

        build_id = str(uuid.uuid4())
        start_time = datetime.now()

        result = BuildResult(
            build_id=build_id,
            status=BuildStatus.RUNNING,
            start_time=start_time
        )

        logger.info(f"开始Gradle构建: {build_id}, 任务: {tasks}")

        try:
            # 准备命令
            cmd = self._prepare_command(tasks)

            # 创建子进程
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=self.project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE,
                env=self._prepare_environment(),
                preexec_fn=self._setup_signal_handlers
            )

            # 处理输出流
            async for log_entry in self._process_output():
                result.logs.append(log_entry['content'])

                # 解析日志
                parsed = self.log_parser.parse_log_line(log_entry['content'])

                # 更新进度
                if parsed['progress']:
                    result.progress.percentage = parsed['progress']
                    if progress_callback:
                        progress_callback(result.progress)

                # 处理APK输出
                if parsed.get('apk_path'):
                    result.apk_path = parsed['apk_path']

                # 处理错误
                if parsed['is_error']:
                    result.error_message = parsed.get('error_message')

                # 调用回调
                if log_callback:
                    log_callback(parsed)

                # 检查取消
                if self._is_cancelled:
                    raise asyncio.CancelledError("构建被用户取消")

            # 等待进程完成
            return_code = await asyncio.wait_for(
                self.process.wait(),
                timeout=self.timeout
            )

            # 更新结果
            end_time = datetime.now()
            result.end_time = end_time
            result.duration = (end_time - start_time).total_seconds()

            if return_code == 0:
                result.status = BuildStatus.SUCCESS
                logger.info(f"构建成功完成: {build_id}")
            else:
                result.status = BuildStatus.FAILED
                logger.error(f"构建失败: {build_id}, 退出码: {return_code}")

        except asyncio.TimeoutError:
            result.status = BuildStatus.TIMEOUT
            result.error_message = f"构建超时 ({self.timeout}秒)"
            logger.error(f"构建超时: {build_id}")

        except asyncio.CancelledError:
            result.status = BuildStatus.CANCELLED
            result.error_message = "构建被取消"
            logger.info(f"构建被取消: {build_id}")

        except Exception as e:
            result.status = BuildStatus.FAILED
            result.error_message = str(e)
            logger.error(f"构建异常: {build_id}, 错误: {e}")

        finally:
            await self._cleanup()

        return result

    def _prepare_command(self, tasks: List[str]) -> List[str]:
        """准备Gradle命令"""
        if self.project_path.joinpath("gradlew").exists():
            cmd = ["./gradlew"]
        elif self.project_path.joinpath("gradlew.bat").exists():
            cmd = ["gradlew.bat"]
        else:
            cmd = ["gradle"]

        # 添加构建参数
        cmd.extend([
            "--info",  # 详细日志
            "--console=plain",  # 简化控制台输出
            "--no-daemon",  # 禁用守护进程
            "--stacktrace"  # 显示堆栈跟踪
        ])

        cmd.extend(tasks)
        return cmd

    def _prepare_environment(self) -> Dict[str, str]:
        """准备环境变量"""
        env = dict(os.environ)

        # 设置JAVA_HOME
        java_home = os.getenv('JAVA_HOME')
        if not java_home:
            # 尝试自动检测Java
            java_home = self._detect_java_home()
            if java_home:
                env['JAVA_HOME'] = java_home

        # 设置GRADLE_OPTS
        env['GRADLE_OPTS'] = env.get('GRADLE_OPTS', '') + " -Xmx2g -XX:MaxMetaspaceSize=512m"

        return env

    def _detect_java_home(self) -> Optional[str]:
        """自动检测Java安装路径"""
        possible_paths = [
            "/usr/lib/jvm/default-java",
            "/usr/lib/jvm/java-11-openjdk",
            "/usr/lib/jvm/java-17-openjdk",
            "C:\\Program Files\\Java\\jdk-11",
            "C:\\Program Files\\Java\\jdk-17"
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return path

        return None

    def _setup_signal_handlers(self):
        """设置信号处理器"""
        def signal_handler(signum, frame):
            self._is_cancelled = True

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

    async def _process_output(self) -> AsyncGenerator[Dict[str, Any], None]:
        """处理进程输出流"""
        if not self.process:
            return

        # 并发读取stdout和stderr
        stdout_task = asyncio.create_task(
            self._read_stream(self.process.stdout, "stdout")
        )
        stderr_task = asyncio.create_task(
            self._read_stream(self.process.stderr, "stderr")
        )

        pending = {stdout_task, stderr_task}

        while pending:
            done, pending = await asyncio.wait(
                pending,
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in done:
                try:
                    async for item in task.result():
                        yield item
                except Exception as e:
                    logger.error(f"读取输出流错误: {e}")

    async def _read_stream(
        self,
        stream: asyncio.StreamReader,
        stream_name: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """从流中读取数据"""
        while True:
            try:
                line = await stream.readline()
                if not line:
                    break

                yield {
                    'stream': stream_name,
                    'content': line.decode('utf-8', errors='ignore').strip(),
                    'timestamp': datetime.now()
                }

            except Exception as e:
                logger.error(f"读取{stream_name}流错误: {e}")
                break

    async def cancel(self):
        """取消构建"""
        self._is_cancelled = True

        if self.process:
            try:
                # 优雅终止
                self.process.terminate()

                # 等待进程结束
                await asyncio.wait_for(self.process.wait(), timeout=10)

            except asyncio.TimeoutError:
                # 强制终止
                self.process.kill()
                await self.process.wait()

    async def _cleanup(self):
        """清理资源"""
        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except:
                self.process.kill()

        self.process = None


class GradleBuildManager:
    """Gradle构建管理器 - 支持并发构建和任务队列"""

    def __init__(self, max_concurrent_builds: int = 3):
        self.max_concurrent_builds = max_concurrent_builds
        self.active_builds: Dict[str, BuildResult] = {}
        self.build_executors: Dict[str, GradleAsyncExecutor] = {}
        self.build_queue: asyncio.Queue = asyncio.Queue()
        self._is_running = False

    async def start(self):
        """启动构建管理器"""
        self._is_running = True

        # 启动工作协程
        for i in range(self.max_concurrent_builds):
            asyncio.create_task(self._worker(f"worker-{i}"))

        logger.info(f"构建管理器已启动，最大并发数: {self.max_concurrent_builds}")

    async def stop(self):
        """停止构建管理器"""
        self._is_running = False

        # 取消所有活跃构建
        for build_id in list(self.active_builds.keys()):
            await self.cancel_build(build_id)

        logger.info("构建管理器已停止")

    async def submit_build(
        self,
        project_path: str,
        tasks: List[str],
        timeout: int = 600,
        log_callback: Optional[Callable] = None,
        progress_callback: Optional[Callable] = None
    ) -> str:
        """提交构建任务"""

        build_id = str(uuid.uuid4())

        build_request = {
            'build_id': build_id,
            'project_path': project_path,
            'tasks': tasks,
            'timeout': timeout,
            'log_callback': log_callback,
            'progress_callback': progress_callback,
            'submitted_at': datetime.now()
        }

        # 初始化构建结果
        self.active_builds[build_id] = BuildResult(
            build_id=build_id,
            status=BuildStatus.QUEUED,
            start_time=datetime.now()
        )

        # 添加到队列
        await self.build_queue.put(build_request)

        logger.info(f"构建任务已提交: {build_id}")
        return build_id

    async def get_build_status(self, build_id: str) -> Optional[BuildResult]:
        """获取构建状态"""
        return self.active_builds.get(build_id)

    async def cancel_build(self, build_id: str) -> bool:
        """取消构建"""
        executor = self.build_executors.get(build_id)
        if executor:
            await executor.cancel()

            build = self.active_builds.get(build_id)
            if build:
                build.status = BuildStatus.CANCELLED

            logger.info(f"构建已取消: {build_id}")
            return True

        return False

    async def _worker(self, worker_name: str):
        """工作协程"""
        logger.info(f"工作协程启动: {worker_name}")

        while self._is_running:
            try:
                # 获取构建任务
                build_request = await asyncio.wait_for(
                    self.build_queue.get(),
                    timeout=1.0
                )

                # 执行构建
                await self._execute_build(build_request)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"工作协程错误 {worker_name}: {e}")

        logger.info(f"工作协程停止: {worker_name}")

    async def _execute_build(self, build_request: Dict[str, Any]):
        """执行构建任务"""
        build_id = build_request['build_id']

        try:
            # 更新状态
            build = self.active_builds[build_id]
            build.status = BuildStatus.RUNNING

            # 创建执行器
            executor = GradleAsyncExecutor(
                build_request['project_path'],
                build_request['timeout']
            )

            self.build_executors[build_id] = executor

            # 执行构建
            result = await executor.execute_build(
                build_request['tasks'],
                build_request.get('log_callback'),
                build_request.get('progress_callback')
            )

            # 更新结果
            self.active_builds[build_id] = result

        except Exception as e:
            # 更新错误状态
            build = self.active_builds.get(build_id)
            if build:
                build.status = BuildStatus.FAILED
                build.error_message = str(e)

        finally:
            # 清理执行器
            self.build_executors.pop(build_id, None)
            self.build_queue.task_done()


# 使用示例
async def example_usage():
    """使用示例"""

    # 创建构建管理器
    manager = GradleBuildManager(max_concurrent_builds=2)
    await manager.start()

    # 日志回调函数
    def log_callback(log_entry):
        print(f"[{log_entry['type']}] {log_entry['content']}")

    # 进度回调函数
    def progress_callback(progress):
        print(f"进度: {progress.percentage}%")

    try:
        # 提交构建任务
        build_id = await manager.submit_build(
            "/path/to/android/project",
            ["assembleDebug"],
            timeout=300,
            log_callback=log_callback,
            progress_callback=progress_callback
        )

        print(f"构建已提交: {build_id}")

        # 监控构建状态
        while True:
            result = await manager.get_build_status(build_id)
            if not result:
                break

            print(f"构建状态: {result.status.value}")

            if result.status in [BuildStatus.SUCCESS, BuildStatus.FAILED, BuildStatus.CANCELLED]:
                if result.apk_path:
                    print(f"APK路径: {result.apk_path}")
                if result.error_message:
                    print(f"错误信息: {result.error_message}")
                break

            await asyncio.sleep(1)

    finally:
        await manager.stop()


if __name__ == "__main__":
    # 运行示例
    asyncio.run(example_usage())