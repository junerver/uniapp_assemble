"""
Git服务。

提供Git仓库操作的封装，包括分支管理、安全检查和备份功能。
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from ..utils.git_utils import GitUtils
from ..utils.exceptions import BuildError, ValidationError

logger = logging.getLogger(__name__)


class GitService:
    """Git服务类。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def check_safety(self, project_path: str, branch_name: str) -> Dict[str, Any]:
        """
        执行Git安全检查。

        Args:
            project_path: 项目路径
            branch_name: 分支名称

        Returns:
            安全检查结果

        Raises:
            ValidationError: 安全检查失败
        """
        try:
            safety_result = GitUtils.check_safety(project_path, branch_name)

            if not safety_result["is_safe"]:
                error_msg = "Git安全检查失败:\n" + "\n".join(f"- {issue}" for issue in safety_result["issues"])
                raise ValidationError(error_msg)

            logger.info(f"Git安全检查通过: {project_path}@{branch_name}")
            return safety_result

        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            logger.error(f"Git安全检查异常: {e}")
            raise BuildError(f"Git安全检查异常: {e}")

    async def create_backup(
        self,
        project_path: str,
        backup_name: str,
        include_untracked: bool = True
    ) -> Optional[str]:
        """
        创建Git备份。

        Args:
            project_path: 项目路径
            backup_name: 备份名称
            include_untracked: 是否包含未跟踪的文件

        Returns:
            备份路径，失败时返回None
        """
        try:
            backup_result = GitUtils.create_backup(project_path, backup_name)
            backup_path = backup_result.get("backup_path") if backup_result.get("success") else None

            if backup_path:
                logger.info(f"创建Git备份成功: {backup_path}")
            else:
                logger.warning(f"创建Git备份失败: {backup_name}")

            return backup_path

        except Exception as e:
            logger.error(f"创建Git备份异常: {e}")
            return None

    async def restore_backup(
        self,
        project_path: str,
        backup_path: str
    ) -> bool:
        """
        恢复Git备份。

        Args:
            project_path: 项目路径
            backup_path: 备份路径

        Returns:
            恢复是否成功
        """
        try:
            success = await GitUtils.restore_backup(project_path, backup_path)

            if success:
                logger.info(f"恢复Git备份成功: {backup_path}")
            else:
                logger.error(f"恢复Git备份失败: {backup_path}")

            return success

        except Exception as e:
            logger.error(f"恢复Git备份异常: {e}")
            return False

    async def list_backups(self, project_path: str) -> List[Dict[str, Any]]:
        """
        列出所有备份。

        Args:
            project_path: 项目路径

        Returns:
            备份列表
        """
        try:
            backups = await GitUtils.list_backups(project_path)
            return backups

        except Exception as e:
            logger.error(f"列出备份异常: {e}")
            return []

    async def switch_branch(
        self,
        project_path: str,
        branch_name: str,
        create_if_not_exists: bool = False
    ) -> bool:
        """
        切换Git分支。

        Args:
            project_path: 项目路径
            branch_name: 分支名称
            create_if_not_exists: 如果分支不存在是否创建

        Returns:
            切换是否成功
        """
        try:
            # 检查分支是否存在
            if not GitUtils.branch_exists(project_path, branch_name):
                if create_if_not_exists:
                    # 创建新分支
                    success = await GitUtils.create_branch(project_path, branch_name)
                    if not success:
                        logger.error(f"创建分支失败: {branch_name}")
                        return False
                else:
                    logger.error(f"分支不存在: {branch_name}")
                    return False

            # 切换分支
            success = await GitUtils.switch_branch(project_path, branch_name)

            if success:
                logger.info(f"切换到分支成功: {branch_name}")
            else:
                logger.error(f"切换分支失败: {branch_name}")

            return success

        except Exception as e:
            logger.error(f"切换分支异常: {e}")
            return False

    async def get_current_branch(self, project_path: str) -> Optional[str]:
        """
        获取当前分支名称。

        Args:
            project_path: 项目路径

        Returns:
            当前分支名称，失败时返回None
        """
        try:
            branch = GitUtils.get_current_branch(project_path)
            return branch

        except Exception as e:
            logger.error(f"获取当前分支异常: {e}")
            return None

    async def get_branch_status(self, project_path: str, branch_name: str) -> Dict[str, Any]:
        """
        获取分支状态信息。

        Args:
            project_path: 项目路径
            branch_name: 分支名称

        Returns:
            分支状态信息
        """
        try:
            # 获取分支信息
            branch_info = GitUtils.get_branch_info(project_path, branch_name)

            # 获取工作目录状态
            status = await GitUtils.get_status(project_path)

            # 获取最近提交
            recent_commits = await GitUtils.get_recent_commits(project_path, branch_name, limit=5)

            return {
                "branch_name": branch_name,
                "branch_info": branch_info,
                "status": status,
                "recent_commits": recent_commits,
                "is_current": GitUtils.get_current_branch(project_path) == branch_name
            }

        except Exception as e:
            logger.error(f"获取分支状态异常: {e}")
            return {}

    async def commit_changes(
        self,
        project_path: str,
        message: str,
        add_all: bool = True
    ) -> bool:
        """
        提交更改。

        Args:
            project_path: 项目路径
            message: 提交消息
            add_all: 是否添加所有更改

        Returns:
            提交是否成功
        """
        try:
            # 添加文件到暂存区
            if add_all:
                success = await GitUtils.add_all(project_path)
            else:
                success = await GitUtils.add_modified(project_path)

            if not success:
                logger.error("添加文件到暂存区失败")
                return False

            # 提交更改
            success = await GitUtils.commit(project_path, message)

            if success:
                logger.info(f"提交更改成功: {message}")
            else:
                logger.error(f"提交更改失败: {message}")

            return success

        except Exception as e:
            logger.error(f"提交更改异常: {e}")
            return False

    async def has_uncommitted_changes(self, project_path: str) -> bool:
        """
        检查是否有未提交的更改。

        Args:
            project_path: 项目路径

        Returns:
            是否有未提交的更改
        """
        try:
            status = await GitUtils.get_status(project_path)
            return bool(status.get("has_changes", False))

        except Exception as e:
            logger.error(f"检查未提交更改异常: {e}")
            return False

    async def get_remote_url(self, project_path: str) -> Optional[str]:
        """
        获取远程仓库URL。

        Args:
            project_path: 项目路径

        Returns:
            远程仓库URL，失败时返回None
        """
        try:
            remote_url = await GitUtils.get_remote_url(project_path)
            return remote_url

        except Exception as e:
            logger.error(f"获取远程仓库URL异常: {e}")
            return None

    async def is_clean_working_directory(self, project_path: str) -> bool:
        """
        检查工作目录是否干净。

        Args:
            project_path: 项目路径

        Returns:
            工作目录是否干净
        """
        try:
            return GitUtils.is_clean_working_directory(project_path)

        except Exception as e:
            logger.error(f"检查工作目录状态异常: {e}")
            return False