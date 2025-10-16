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
        from ..config.database import get_async_session

        last_log_time = datetime.utcnow() - timedelta(seconds=1)

        while True:
            # 为SSE创建独立的数据库会话
            async with get_async_session() as session:
                try:
                    result = await session.execute(
                        select(BuildLog)
                        .where(BuildLog.build_task_id == task_id)
                        .where(BuildLog.timestamp > last_log_time)
                        .order_by(BuildLog.timestamp.asc())
                        .limit(10)
                    )
                    logs = result.scalars().all()

                    for log in logs:
                        yield log.to_dict()
                        last_log_time = log.timestamp

                    # 检查任务是否完成
                    task = await session.get(BuildTask, task_id)
                    if task and task.is_completed:
                        break

                except Exception as e:
                    logger.error(f"SSE数据库查询失败: {e}")
                    yield {"error": f"SSE数据库查询失败: {str(e)}"}
                    break

            await asyncio.sleep(0.5)  # 等待500ms

    async def _execute_resource_replace(self, task_id: str) -> None:
        """执行资源替换任务。"""
        try:
            # 导入资源服务（避免循环导入）
            from .resource_service import ResourceService
            from .git_service import GitService

            task = await self.session.get(BuildTask, task_id)
            if not task:
                return

            project = await self.session.get(AndroidProject, task.project_id)
            if not project:
                raise BuildError("项目不存在")

            # 创建服务实例
            resource_service = ResourceService(self.session)
            git_service = GitService(self.session)

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
            self.session.add(task)
            await self.session.commit()

            await self._create_build_log(
                task.id,
                BuildLog.create_build_complete_log(task.id, "资源替换", True)
            )

            logger.info(f"资源替换任务完成: {task_id}")

        except Exception as e:
            error_msg = f"资源替换失败: {str(e)}"
            logger.error(f"任务 {task_id} 失败: {error_msg}")

            # 更新任务状态
            task = await self.session.get(BuildTask, task_id)
            if task:
                task.fail(error_msg)
                self.session.add(task)
                await self.session.commit()

            await self._create_build_log(
                task.id,
                BuildLog.create_error_log(task.id, error_msg, source="build_service")
            )

        finally:
            # 清理运行中的任务
            if task_id in self._running_tasks:
                del self._running_tasks[task_id]

    async def _execute_build(self, task_id: str) -> None:
        """执行构建任务。"""
        try:
            from ..utils.gradle_utils import GradleUtils

            task = await self.session.get(BuildTask, task_id)
            if not task:
                return

            project = await self.session.get(AndroidProject, task.project_id)
            if not project:
                raise BuildError("项目不存在")

            # 更新进度
            await self._update_task_progress(task_id, 10, "准备构建环境")

            # 执行Gradle构建
            await self._update_task_progress(task_id, 20, "开始Gradle构建")
            gradle_utils = GradleUtils(project.path)

            # 流式执行构建并记录日志
            result = await self._execute_gradle_with_logging(
                task_id,
                gradle_utils,
                task.config_options or {}
            )

            # 更新进度
            await self._update_task_progress(task_id, 90, "验证构建结果")

            # 完成任务
            task.complete(result)
            self.session.add(task)
            await self.session.commit()

            await self._create_build_log(
                task.id,
                BuildLog.create_build_complete_log(task.id, "Gradle构建", True)
            )

            logger.info(f"构建任务完成: {task_id}")

        except Exception as e:
            error_msg = f"构建失败: {str(e)}"
            logger.error(f"任务 {task_id} 失败: {error_msg}")

            # 更新任务状态
            task = await self.session.get(BuildTask, task_id)
            if task:
                task.fail(error_msg)
                self.session.add(task)
                await self.session.commit()

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
        try:
            from .apk_service import APKService

            task = await self.session.get(BuildTask, task_id)
            if not task:
                return

            project = await self.session.get(AndroidProject, task.project_id)
            if not project:
                raise BuildError("项目不存在")

            # 创建APK服务
            apk_service = APKService(self.session)

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
            self.session.add(task)
            await self.session.commit()

            await self._create_build_log(
                task.id,
                BuildLog.create_build_complete_log(task.id, "APK提取", True)
            )

            logger.info(f"APK提取任务完成: {task_id}")

        except Exception as e:
            error_msg = f"APK提取失败: {str(e)}"
            logger.error(f"任务 {task_id} 失败: {error_msg}")

            # 更新任务状态
            task = await self.session.get(BuildTask, task_id)
            if task:
                task.fail(error_msg)
                self.session.add(task)
                await self.session.commit()

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
            # 异步执行Gradle构建并捕获输出
            process = await gradle_utils.execute_build_async("assembleDebug", config_options)

            # 读取构建输出
            while True:
                line = await process.stdout.readline()
                if not line:
                    break

                line = line.decode('utf-8').strip()
                if line:
                    result["output"] += line + "\n"

                    # 解析并记录日志
                    logs = BuildLog.parse_gradle_output(task_id, line)
                    for log in logs:
                        await self._create_build_log(task_id, log)

                    # 更新进度（基于常见Gradle输出模式）
                    progress = self._parse_gradle_progress(line)
                    if progress > 0:
                        await self._update_task_progress(task_id, progress, f"构建中: {line}")

            # 等待进程完成
            await process.wait()

            if process.returncode == 0:
                result["success"] = True
                result["artifacts"] = gradle_utils.get_build_artifacts()
            else:
                result["error"] = f"Gradle构建失败，退出码: {process.returncode}"

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
        try:
            stmt = (
                update(BuildTask)
                .where(BuildTask.id == task_id)
                .values(progress=progress)
            )
            await self.session.execute(stmt)
            await self.session.commit()

            # 创建进度日志
            await self._create_build_log(
                task_id,
                BuildLog.create_progress_log(task_id, progress, message)
            )

            logger.debug(f"任务 {task_id} 进度更新到 {progress}%: {message}")

        except Exception as e:
            logger.error(f"更新任务进度失败: {e}")

    async def _create_build_log(self, task_id: str, log: BuildLog) -> None:
        """创建构建日志。"""
        try:
            self.session.add(log)
            await self.session.commit()
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