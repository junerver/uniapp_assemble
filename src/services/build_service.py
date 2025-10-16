"""
构建服务。

负责构建任务的编排、执行和状态管理。
"""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable, AsyncGenerator
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from ..models.build_task import BuildTask, TaskType, TaskStatus
from ..models.build_log import BuildLog, LogLevel
from ..models.android_project import AndroidProject
from ..utils.exceptions import BuildError, ValidationError
from ..utils.git_utils import GitUtils

logger = logging.getLogger(__name__)


class BuildService:
    """构建服务类。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._progress_callbacks: Dict[str, List[Callable]] = {}

    async def create_build_task(
        self,
        project_id: str,
        task_type: TaskType,
        git_branch: str,
        resource_package_path: Optional[str] = None,
        config_options: Optional[Dict[str, Any]] = None
    ) -> BuildTask:
        """创建构建任务。"""
        logger.info(f"[DEBUG] BuildService.create_build_task 接收: task_type={task_type}, type={type(task_type)}, value={task_type.value if isinstance(task_type, TaskType) else 'N/A'}")

        # 验证项目存在
        project = await self.session.get(AndroidProject, project_id)
        if not project:
            raise ValidationError(f"项目不存在: {project_id}")

        # 验证Git仓库
        if not GitUtils.is_git_repository(project.path):
            raise ValidationError(f"项目不是有效的Git仓库: {project.path}")

        # 验证分支存在
        if not GitUtils.branch_exists(project.path, git_branch):
            raise ValidationError(f"分支不存在: {git_branch}")

        # 根据任务类型创建任务
        logger.info(f"[DEBUG] 开始判断任务类型: task_type={task_type}, TaskType.BUILD={TaskType.BUILD}, 相等吗? {task_type == TaskType.BUILD}")
        if task_type == TaskType.RESOURCE_REPLACE:
            if not resource_package_path:
                raise ValidationError("资源替换任务需要提供资源包路径")
            task = BuildTask.create_resource_replace_task(
                project_id=project_id,
                resource_package_path=resource_package_path,
                git_branch=git_branch,
                config_options=config_options
            )
        elif task_type == TaskType.BUILD:
            task = BuildTask.create_build_task(
                project_id=project_id,
                git_branch=git_branch,
                resource_package_path=resource_package_path,
                config_options=config_options
            )
        elif task_type == TaskType.EXTRACT_APK:
            task = BuildTask.create_extract_apk_task(
                project_id=project_id,
                build_task_id="",  # 将在后续设置
                config_options=config_options
            )
        else:
            raise ValidationError(f"不支持的任务类型: {task_type}")

        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)

        # 创建开始日志
        await self._create_build_log(
            task.id,
            BuildLog.create_build_start_log(task.id, task_type.value)
        )

        logger.info(f"创建构建任务: {task.id} ({task_type.value})")
        return task

    async def start_build_task(self, task_id: str) -> bool:
        """开始执行构建任务。"""
        task = await self.session.get(BuildTask, task_id)
        if not task:
            raise ValidationError(f"构建任务不存在: {task_id}")

        logger.info(f"[DEBUG] start_build_task: task.task_type={task.task_type}, TaskType.BUILD.value={TaskType.BUILD.value}, TaskType.RESOURCE_REPLACE.value={TaskType.RESOURCE_REPLACE.value}")

        if task.status != TaskStatus.PENDING.value:
            raise ValidationError(f"任务状态不是pending: {task.status}")

        # 检查是否已有运行中的任务
        if task_id in self._running_tasks:
            raise ValidationError(f"任务已在运行中: {task_id}")

        # 启动任务
        task.start()
        self.session.add(task)
        await self.session.commit()

        # 创建异步任务
        logger.info(f"[DEBUG] 判断执行类型: task.task_type={task.task_type}, 类型={type(task.task_type)}")
        if task.task_type == TaskType.RESOURCE_REPLACE.value:
            asyncio_task = asyncio.create_task(
                self._execute_resource_replace(task_id)
            )
        elif task.task_type == TaskType.BUILD.value:
            asyncio_task = asyncio.create_task(
                self._execute_build(task_id)
            )
        elif task.task_type == TaskType.EXTRACT_APK.value:
            asyncio_task = asyncio.create_task(
                self._execute_apk_extraction(task_id)
            )
        else:
            raise ValidationError(f"不支持的任务类型: {task.task_type}")

        self._running_tasks[task_id] = asyncio_task

        logger.info(f"开始执行构建任务: {task_id}")
        return True

    async def cancel_build_task(self, task_id: str) -> bool:
        """取消构建任务。"""
        task = await self.session.get(BuildTask, task_id)
        if not task:
            raise ValidationError(f"构建任务不存在: {task_id}")

        if task.is_completed:
            raise ValidationError(f"任务已完成，无法取消: {task_id}")

        # 取消异步任务
        if task_id in self._running_tasks:
            self._running_tasks[task_id].cancel()
            del self._running_tasks[task_id]

        # 更新任务状态
        task.cancel()
        self.session.add(task)
        await self.session.commit()

        # 创建取消日志
        await self._create_build_log(
            task.id,
            BuildLog.create_info_log(
                task.id,
                "任务已被用户取消",
                source="build_service"
            )
        )

        logger.info(f"取消构建任务: {task_id}")
        return True

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态。"""
        task = await self.session.get(BuildTask, task_id)
        if not task:
            return None

        return task.to_dict()

    async def get_task_logs(self, task_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取任务日志。"""
        result = await self.session.execute(
            select(BuildLog)
            .where(BuildLog.build_task_id == task_id)
            .order_by(BuildLog.timestamp.desc())
            .limit(limit)
        )
        logs = result.scalars().all()
        return [log.to_dict() for log in logs]

    async def stream_task_logs(self, task_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """实时流式获取任务日志。"""
        from ..config.database import AsyncSessionLocal

        last_log_time = datetime.utcnow() - timedelta(seconds=1)
        no_log_count = 0  # 连续无日志计数
        max_no_log_cycles = 120  # 最大无日志循环次数 (约60秒)

        while True:
            # 为SSE创建独立的数据库会话
            try:
                async with AsyncSessionLocal() as session:
                    result = await session.execute(
                        select(BuildLog)
                        .where(BuildLog.build_task_id == task_id)
                        .where(BuildLog.timestamp > last_log_time)
                        .order_by(BuildLog.timestamp.asc())
                        .limit(10)
                    )
                    logs = result.scalars().all()

                    if logs:
                        # 有新日志，发送并重置计数
                        for log in logs:
                            yield log.to_dict()
                            last_log_time = log.timestamp
                        no_log_count = 0
                    else:
                        # 没有新日志，增加计数
                        no_log_count += 1

                        # 检查任务是否完成
                        task = await session.get(BuildTask, task_id)
                        if task and task.is_completed:
                            # 任务完成，发送完成信号并退出
                            yield {
                                "type": "task_completed",
                                "task_id": task_id,
                                "status": task.status,
                                "final": True
                            }
                            break

                        # 如果长时间无日志且任务未完成，发送心跳
                        if no_log_count % 10 == 0:  # 每5秒发送一次心跳
                            yield {
                                "type": "heartbeat",
                                "task_id": task_id,
                                "message": "任务执行中，等待新日志...",
                                "no_log_cycles": no_log_count
                            }

                        # 如果超时，退出循环
                        if no_log_count >= max_no_log_cycles:
                            yield {
                                "type": "timeout",
                                "task_id": task_id,
                                "message": "日志流超时，任务可能仍在执行中",
                                "no_log_cycles": no_log_count
                            }
                            break

            except Exception as e:
                logger.error(f"SSE数据库查询失败: {e}")
                yield {"error": f"SSE数据库查询失败: {str(e)}"}
                break

            await asyncio.sleep(0.5)  # 等待500ms

    async def _execute_resource_replace(self, task_id: str) -> None:
        """执行资源替换任务。"""
        # 为后台任务创建独立的数据库session
        # 注意：不能使用self.session，因为它属于API请求的session，会在请求结束后关闭
        from ..config.database import AsyncSessionLocal
        from .resource_service import ResourceService
        from .git_service import GitService

        async with AsyncSessionLocal() as session:
            try:
                task = await session.get(BuildTask, task_id)
                if not task:
                    return

                project = await session.get(AndroidProject, task.project_id)
                if not project:
                    raise BuildError("项目不存在")

                # 创建服务实例，使用独立的session
                resource_service = ResourceService(session)
                git_service = GitService(session)

                # 更新进度
                await self._update_task_progress(task_id, 10, "开始资源替换")

                # 执行Git安全检查
                await self._update_task_progress(task_id, 20, "执行Git安全检查")
                await git_service.check_safety(project.path, task.git_branch)

                # 执行资源替换
                await self._update_task_progress(task_id, 40, "执行资源替换")
                result = await resource_service.replace_resources(
                    project.path,
                    task.resource_package_path,
                    task.git_branch,
                    task.config_options or {}
                )

                # 更新进度
                await self._update_task_progress(task_id, 90, "验证替换结果")

                # 完成任务
                task.complete(result)
                session.add(task)
                await session.commit()

                await self._create_build_log(
                    task.id,
                    BuildLog.create_build_complete_log(task.id, "资源替换", True)
                )

                logger.info(f"资源替换任务完成: {task_id}")

            except Exception as e:
                error_msg = f"资源替换失败: {str(e)}"
                logger.error(f"任务 {task_id} 失败: {error_msg}")

                # 更新任务状态
                task = await session.get(BuildTask, task_id)
                if task:
                    task.fail(error_msg)
                    session.add(task)
                    await session.commit()

                await self._create_build_log(
                    task.id,
                    BuildLog.create_error_log(task.id, error_msg, source="build_service")
                )

            finally:
                # 清理运行中的任务
                if task_id in self._running_tasks:
                    del self._running_tasks[task_id]

    async def _execute_build(self, task_id: str) -> None:
        """
        执行完整构建任务。

        包含以下步骤:
        1. Git安全检查
        2. 资源替换 (如果提供了资源包)
        3. Gradle构建
        4. 产物收集
        """
        # 为后台任务创建独立的数据库session
        from ..config.database import AsyncSessionLocal
        from ..utils.gradle_utils import GradleUtils
        from .resource_service import ResourceService
        from .git_service import GitService

        async with AsyncSessionLocal() as session:
            try:
                task = await session.get(BuildTask, task_id)
                if not task:
                    return

                project = await session.get(AndroidProject, task.project_id)
                if not project:
                    raise BuildError("项目不存在")

                # 创建服务实例
                gradle_utils = GradleUtils(project.path)
                git_service = GitService(session)

                # 合并结果
                final_result = {
                    "success": False,
                    "resource_replace_result": None,
                    "build_result": None
                }

                # === 步骤1: Git安全检查 (5%) ===
                await self._update_task_progress(task_id, 5, "执行Git安全检查")
                await git_service.check_safety(project.path, task.git_branch)
                await self._create_build_log(
                    task_id,
                    BuildLog.create_info_log(task_id, "Git安全检查通过", source="build_service")
                )

                # === 步骤2: 资源替换 (10% - 30%) ===
                if task.resource_package_path:
                    await self._update_task_progress(task_id, 10, "开始资源替换")

                    resource_service = ResourceService(session)
                    resource_result = await resource_service.replace_resources(
                        project.path,
                        task.resource_package_path,
                        task.git_branch,
                        task.config_options or {}
                    )

                    final_result["resource_replace_result"] = resource_result

                    await self._update_task_progress(task_id, 30, "资源替换完成")
                    await self._create_build_log(
                        task_id,
                        BuildLog.create_info_log(
                            task_id,
                            f"资源替换完成: {resource_result.get('replacement_result', {}).get('files_replaced', 0)} 个文件已替换",
                            source="build_service"
                        )
                    )
                else:
                    await self._update_task_progress(task_id, 30, "跳过资源替换(未提供资源包)")

                # === 步骤3: Gradle构建 (35% - 85%) ===
                await self._update_task_progress(task_id, 35, "准备Gradle构建环境")

                # 验证构建环境
                validation = gradle_utils.validate_build_environment()
                if not validation["valid"]:
                    raise BuildError(f"构建环境验证失败: {', '.join(validation['issues'])}")

                # 获取构建类型
                build_type = task.config_options.get("build_type", "clean :app:assembleRelease") if task.config_options else "clean :app:assembleRelease"

                await self._update_task_progress(task_id, 40, f"开始Gradle构建 ({build_type})")
                await self._create_build_log(
                    task_id,
                    BuildLog.create_info_log(task_id, f"执行Gradle任务: {build_type}", source="gradle")
                )

                # 流式执行构建并记录日志
                build_result = await self._execute_gradle_with_logging(
                    task_id,
                    gradle_utils,
                    task.config_options or {}
                )

                final_result["build_result"] = build_result

                # === 步骤4: 验证构建结果 (85% - 95%) ===
                await self._update_task_progress(task_id, 85, "验证构建结果")

                if not build_result.get("success"):
                    raise BuildError(f"Gradle构建失败: {build_result.get('error', '未知错误')}")

                # 收集构建产物
                artifacts = build_result.get("artifacts", [])
                await self._create_build_log(
                    task_id,
                    BuildLog.create_info_log(
                        task_id,
                        f"构建成功! 生成 {len(artifacts)} 个产物, 耗时 {build_result.get('build_time', 0)} 秒",
                        source="build_service"
                    )
                )

                # === 完成任务 (100%) ===
                await self._update_task_progress(task_id, 100, "构建任务完成")

                final_result["success"] = True
                task.complete(final_result)
                session.add(task)
                await session.commit()

                await self._create_build_log(
                    task.id,
                    BuildLog.create_build_complete_log(task.id, "完整构建", True)
                )

                logger.info(f"构建任务完成: {task_id}, 产物数量: {len(artifacts)}")

            except Exception as e:
                error_msg = f"构建失败: {str(e)}"
                logger.error(f"任务 {task_id} 失败: {error_msg}", exc_info=True)

                # 更新任务状态
                task = await session.get(BuildTask, task_id)
                if task:
                    task.fail(error_msg)
                    session.add(task)
                    await session.commit()

                await self._create_build_log(
                    task.id,
                    BuildLog.create_error_log(task.id, error_msg, source="build_service")
                )

            finally:
                # 清理运行中的任务
                if task_id in self._running_tasks:
                    del self._running_tasks[task_id]

    async def _execute_apk_extraction(self, task_id: str) -> None:
        """执行APK提取任务。"""
        # 为后台任务创建独立的数据库session
        from ..config.database import AsyncSessionLocal
        from .apk_service import APKService

        async with AsyncSessionLocal() as session:
            try:
                task = await session.get(BuildTask, task_id)
                if not task:
                    return

                project = await session.get(AndroidProject, task.project_id)
                if not project:
                    raise BuildError("项目不存在")

                # 创建APK服务,使用独立session
                apk_service = APKService(session)

                # 更新进度
                await self._update_task_progress(task_id, 10, "开始APK提取")

                # 提取APK文件
                await self._update_task_progress(task_id, 50, "扫描APK文件")
                result = await apk_service.extract_apk_files(
                    project.path,
                    task.config_options or {}
                )

                # 更新进度
                await self._update_task_progress(task_id, 90, "验证提取结果")

                # 完成任务
                task.complete(result)
                session.add(task)
                await session.commit()

                await self._create_build_log(
                    task.id,
                    BuildLog.create_build_complete_log(task.id, "APK提取", True)
                )

                logger.info(f"APK提取任务完成: {task_id}")

            except Exception as e:
                error_msg = f"APK提取失败: {str(e)}"
                logger.error(f"任务 {task_id} 失败: {error_msg}")

                # 更新任务状态
                task = await session.get(BuildTask, task_id)
                if task:
                    task.fail(error_msg)
                    session.add(task)
                    await session.commit()

                await self._create_build_log(
                    task.id,
                    BuildLog.create_error_log(task.id, error_msg, source="build_service")
                )

            finally:
                # 清理运行中的任务
                if task_id in self._running_tasks:
                    del self._running_tasks[task_id]

    async def _execute_gradle_with_logging(
        self,
        task_id: str,
        gradle_utils: "GradleUtils",
        config_options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行Gradle构建并记录日志。"""
        result = {
            "success": False,
            "output": "",
            "error": "",
            "build_time": 0,
            "artifacts": []
        }

        start_time = datetime.utcnow()

        try:
            # 获取构建类型,默认为clean :app:assembleRelease
            build_type = config_options.get("build_type", "clean :app:assembleRelease")

            # 异步执行Gradle构建并捕获输出
            process = await gradle_utils.execute_build_async(build_type, config_options)

            # 读取构建输出 - Windows和Linux兼容
            import sys
            if sys.platform == "win32":
                # Windows: 同步Popen对象,在executor中实时读取
                import asyncio
                import threading
                import queue
                loop = asyncio.get_event_loop()

                output_queue = queue.Queue()

                # 定义读取stdout的线程函数
                def read_stdout():
                    try:
                        for line in iter(process.stdout.readline, b''):
                            try:
                                decoded_line = line.decode('utf-8', errors='replace').strip()
                                if decoded_line:
                                    output_queue.put(('stdout', decoded_line))
                            except Exception as e:
                                logger.error(f"解码stdout失败: {e}")
                    finally:
                        output_queue.put(('stdout', None))  # 结束标记

                # 定义读取stderr的线程函数
                def read_stderr():
                    try:
                        for line in iter(process.stderr.readline, b''):
                            try:
                                decoded_line = line.decode('utf-8', errors='replace').strip()
                                if decoded_line:
                                    output_queue.put(('stderr', decoded_line))
                            except Exception as e:
                                logger.error(f"解码stderr失败: {e}")
                    finally:
                        output_queue.put(('stderr', None))  # 结束标记

                # 启动读取线程
                stdout_thread = threading.Thread(target=read_stdout, daemon=True)
                stderr_thread = threading.Thread(target=read_stderr, daemon=True)
                stdout_thread.start()
                stderr_thread.start()

                # 实时处理输出
                streams_ended = 0
                while streams_ended < 2:
                    try:
                        # 非阻塞读取,每100ms检查一次
                        stream_type, line = await loop.run_in_executor(
                            None,
                            lambda: output_queue.get(timeout=0.1)
                        )

                        if line is None:
                            streams_ended += 1
                            continue

                        # 记录输出
                        if stream_type == 'stdout':
                            result["output"] += line + "\n"
                        else:  # stderr
                            result["error"] += line + "\n"
                            # 避免日志编码错误 - 使用errors='replace'处理无法编码的字符
                            try:
                                logger.info(f"[GRADLE stderr] {line}")
                            except UnicodeEncodeError:
                                # 如果logger仍然失败，跳过控制台输出
                                pass

                        # 解析日志并存入数据库（这个会发送到SSE）
                        logs = BuildLog.parse_gradle_output(task_id, line)
                        for log in logs:
                            await self._create_build_log(task_id, log)

                        # 更新进度
                        progress = self._parse_gradle_progress(line)
                        if progress > 0:
                            await self._update_task_progress(task_id, progress, f"{line[:100]}")

                    except:
                        # 超时,继续循环
                        await asyncio.sleep(0.1)

                # 等待进程完成
                await loop.run_in_executor(None, process.wait)

                # 等待线程结束
                stdout_thread.join(timeout=1)
                stderr_thread.join(timeout=1)
            else:
                # Unix/Linux: 异步subprocess
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break

                    line = line.decode('utf-8').strip()
                    if line:
                        result["output"] += line + "\n"
                        logs = BuildLog.parse_gradle_output(task_id, line)
                        for log in logs:
                            await self._create_build_log(task_id, log)
                        progress = self._parse_gradle_progress(line)
                        if progress > 0:
                            await self._update_task_progress(task_id, progress, f"{line}")

                await process.wait()

            if process.returncode == 0:
                result["success"] = True
                result["artifacts"] = gradle_utils.get_build_artifacts()
            else:
                # 构建失败,组合错误信息
                error_msg = f"Gradle构建失败，退出码: {process.returncode}"
                if result["error"]:
                    error_msg += f"\n错误输出:\n{result['error']}"
                result["error"] = error_msg

        except Exception as e:
            result["error"] = str(e)
            raise

        finally:
            result["build_time"] = int((datetime.utcnow() - start_time).total_seconds())

        return result

    def _parse_gradle_progress(self, line: str) -> int:
        """解析Gradle输出中的进度信息。"""
        line = line.lower().strip()

        # 基于常见Gradle输出模式估算进度
        if "task :" in line and not line.startswith("> task :"):
            return 15  # 开始执行任务
        elif "compiling" in line or "compile" in line:
            return 25  # 编译阶段
        elif "processing" in line or "process" in line:
            return 50  # 处理资源
        elif "packaging" in line or "package" in line:
            return 75  # 打包阶段
        elif "build succeeded" in line or "success" in line:
            return 95  # 构建成功
        elif "build failed" in line or "failed" in line:
            return 95  # 构建失败

        return 0

    async def _update_task_progress(self, task_id: str, progress: int, message: str) -> None:
        """更新任务进度。"""
        # 为后台任务创建独立的session
        from ..config.database import AsyncSessionLocal

        try:
            async with AsyncSessionLocal() as session:
                stmt = (
                    update(BuildTask)
                    .where(BuildTask.id == task_id)
                    .values(progress=progress)
                )
                await session.execute(stmt)
                await session.commit()

                # 创建进度日志
                log = BuildLog.create_progress_log(task_id, progress, message)
                session.add(log)
                await session.commit()

                logger.debug(f"任务 {task_id} 进度更新到 {progress}%: {message}")

        except Exception as e:
            logger.error(f"更新任务进度失败: {e}")

    async def _create_build_log(self, task_id: str, log: BuildLog) -> None:
        """创建构建日志。"""
        # 为后台任务创建独立的session
        from ..config.database import AsyncSessionLocal

        try:
            async with AsyncSessionLocal() as session:
                session.add(log)
                await session.commit()
        except Exception as e:
            logger.error(f"创建构建日志失败: {e}")

    async def get_active_tasks(self) -> List[BuildTask]:
        """获取活跃的任务列表。"""
        result = await self.session.execute(
            select(BuildTask)
            .where(BuildTask.status == TaskStatus.RUNNING.value)
            .order_by(BuildTask.created_at.desc())
        )
        return result.scalars().all()

    async def cleanup_completed_tasks(self, days: int = 7) -> int:
        """清理已完成的任务。"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        stmt = (
            update(BuildTask)
            .where(BuildTask.completed_at < cutoff_date)
            .where(BuildTask.status.in_([
                TaskStatus.COMPLETED.value,
                TaskStatus.FAILED.value,
                TaskStatus.CANCELLED.value
            ]))
            .values(is_active=False)
        )

        result = await self.session.execute(stmt)
        await self.session.commit()

        logger.info(f"清理了 {result.rowcount} 个已完成任务")
        return result.rowcount