"""
Git操作服务。

提供Git提交、回滚、分支管理等功能，支持安全操作和备份恢复。
"""

import asyncio
import logging
import os
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import subprocess

from ..models.android_project import AndroidProject
from ..models.git_operation import GitOperation, OperationType, OperationStatus
from ..models.repository_backup import RepositoryBackup, BackupType, BackupStatus
from ..utils.git_utils import GitUtils, NotAGitRepositoryError, GitUtilsError
from ..utils.exceptions import BuildError, ValidationError

logger = logging.getLogger(__name__)


class GitService:
    """Git操作服务类。"""

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

    # 新增的高级Git操作功能

    async def create_safe_commit(
        self,
        project_id: str,
        commit_message: str,
        files_to_commit: Optional[List[str]] = None,
        create_backup: bool = True,
        backup_expiry_days: int = 30
    ) -> Dict[str, Any]:
        """
        安全提交更改，可选择创建备份。

        Args:
            project_id: 项目ID
            commit_message: 提交消息
            files_to_commit: 要提交的文件列表，None表示提交所有更改
            create_backup: 是否创建备份
            backup_expiry_days: 备份过期天数

        Returns:
            操作结果字典
        """
        try:
            # 获取项目信息
            project = await self._get_project(project_id)
            project_path = Path(project.path)

            # 验证Git仓库
            if not GitUtils.is_git_repository(project_path):
                raise ValidationError(f"项目路径不是有效的Git仓库: {project_path}")

            # 创建Git操作记录
            git_operation = GitOperation.create_commit_operation(
                project_id=project_id,
                commit_message=commit_message,
                files_affected=files_to_commit or [],
                description=f"安全提交: {commit_message}",
                config_options={
                    "create_backup": create_backup,
                    "backup_expiry_days": backup_expiry_days,
                    "files_to_commit": files_to_commit
                }
            )

            self.session.add(git_operation)
            await self.session.flush()  # 获取ID

            # 开始操作
            git_operation.start()
            logger.info(f"开始Git提交操作: {git_operation.id}")

            result = {
                "operation_id": git_operation.id,
                "project_id": project_id,
                "commit_message": commit_message,
                "status": "in_progress",
                "steps": []
            }

            # 步骤1: 安全检查
            safety_result = await self._perform_safety_checks(project_path, "当前分支")
            result["steps"].append({
                "step": "safety_check",
                "status": "completed",
                "data": safety_result
            })

            if not safety_result["is_safe"]:
                # 标记操作失败
                error_msg = f"安全检查失败: {'; '.join(safety_result['issues'])}"
                git_operation.fail(error_msg)
                await self.session.commit()

                result["status"] = "failed"
                result["error"] = error_msg
                return result

            # 获取当前状态
            repo_info_before = GitUtils.get_repository_info(project_path)
            git_operation.commit_hash_before = repo_info_before.get("latest_commit", {}).get("sha")

            # 步骤2: 创建备份（如果需要）
            backup_info = None
            if create_backup:
                backup_info = await self._create_operation_backup(
                    project_id, git_operation.id, project_path,
                    repo_info_before.get("latest_commit", {}).get("sha"),
                    repo_info_before.get("current_branch")
                )
                result["steps"].append({
                    "step": "backup_creation",
                    "status": "completed" if backup_info else "skipped",
                    "data": backup_info
                })

            # 步骤3: 添加文件到暂存区
            if files_to_commit:
                # 添加指定文件
                await self._add_specific_files(project_path, files_to_commit)
                result["steps"].append({
                    "step": "add_files",
                    "status": "completed",
                    "data": {"files_added": files_to_commit}
                })
            else:
                # 添加所有更改
                await GitUtils.add_all(project_path)
                result["steps"].append({
                    "step": "add_all_files",
                    "status": "completed"
                })

            # 步骤4: 执行提交
            commit_success = await GitUtils.commit(project_path, commit_message)
            if not commit_success:
                raise GitUtilsError("Git提交失败")

            result["steps"].append({
                "step": "git_commit",
                "status": "completed"
            })

            # 获取提交后的状态
            repo_info_after = GitUtils.get_repository_info(project_path)
            new_commit_hash = repo_info_after.get("latest_commit", {}).get("sha")
            git_operation.commit_hash_after = new_commit_hash

            # 完成操作
            git_operation.complete(
                result_data={
                    "backup_info": backup_info,
                    "safety_check": safety_result,
                    "commit_hash": new_commit_hash,
                    "files_committed": files_to_commit or "all_changes"
                },
                commit_hash=new_commit_hash
            )

            await self.session.commit()

            result["status"] = "completed"
            result["commit_hash"] = new_commit_hash
            result["backup_info"] = backup_info

            logger.info(f"Git提交操作完成: {git_operation.id}, 提交: {new_commit_hash[:7]}")
            return result

        except Exception as e:
            # 回滚操作状态
            if 'git_operation' in locals():
                git_operation.fail(str(e))
                await self.session.commit()

            logger.error(f"Git提交操作失败: {e}")
            raise BuildError(f"Git提交失败: {str(e)}")

    async def create_safe_rollback(
        self,
        project_id: str,
        target_commit_hash: str,
        create_backup: bool = True,
        backup_expiry_days: int = 30
    ) -> Dict[str, Any]:
        """
        安全回滚到指定提交。

        Args:
            project_id: 项目ID
            target_commit_hash: 目标提交哈希
            create_backup: 是否创建备份
            backup_expiry_days: 备份过期天数

        Returns:
            操作结果字典
        """
        try:
            # 获取项目信息
            project = await self._get_project(project_id)
            project_path = Path(project.path)

            # 验证Git仓库
            if not GitUtils.is_git_repository(project_path):
                raise ValidationError(f"项目路径不是有效的Git仓库: {project_path}")

            # 创建Git操作记录
            git_operation = GitOperation.create_rollback_operation(
                project_id=project_id,
                target_commit_hash=target_commit_hash,
                description=f"回滚到提交: {target_commit_hash[:7]}",
                config_options={
                    "create_backup": create_backup,
                    "backup_expiry_days": backup_expiry_days
                }
            )

            self.session.add(git_operation)
            await self.session.flush()

            # 开始操作
            git_operation.start()
            logger.info(f"开始Git回滚操作: {git_operation.id}")

            result = {
                "operation_id": git_operation.id,
                "project_id": project_id,
                "target_commit": target_commit_hash,
                "status": "in_progress",
                "steps": []
            }

            # 步骤1: 验证目标提交
            commit_validation = await self._validate_target_commit(project_path, target_commit_hash)
            result["steps"].append({
                "step": "commit_validation",
                "status": "completed",
                "data": commit_validation
            })

            if not commit_validation["exists"]:
                error_msg = f"目标提交不存在: {target_commit_hash}"
                git_operation.fail(error_msg)
                await self.session.commit()

                result["status"] = "failed"
                result["error"] = error_msg
                return result

            # 获取当前状态
            repo_info_before = GitUtils.get_repository_info(project_path)
            current_commit_hash = repo_info_before.get("latest_commit", {}).get("sha")
            git_operation.commit_hash_before = current_commit_hash

            # 步骤2: 安全检查
            safety_result = await self._perform_safety_checks(project_path, "当前分支")
            result["steps"].append({
                "step": "safety_check",
                "status": "completed",
                "data": safety_result
            })

            if not safety_result["is_safe"]:
                # 对于回滚操作，警告而不是错误
                result["warnings"] = safety_result["issues"]

            # 步骤3: 创建备份（如果需要）
            backup_info = None
            if create_backup:
                backup_info = await self._create_operation_backup(
                    project_id, git_operation.id, project_path,
                    current_commit_hash,
                    repo_info_before.get("current_branch")
                )
                result["steps"].append({
                    "step": "backup_creation",
                    "status": "completed" if backup_info else "skipped",
                    "data": backup_info
                })

            # 步骤4: 执行回滚
            rollback_success = await self._execute_rollback(project_path, target_commit_hash)
            if not rollback_success:
                raise GitUtilsError("Git回滚失败")

            result["steps"].append({
                "step": "git_rollback",
                "status": "completed"
            })

            # 步骤5: 验证回滚结果
            rollback_validation = await self._validate_rollback_result(project_path, target_commit_hash)
            result["steps"].append({
                "step": "rollback_validation",
                "status": "completed",
                "data": rollback_validation
            })

            # 完成操作
            git_operation.complete(
                result_data={
                    "backup_info": backup_info,
                    "target_commit": target_commit_hash,
                    "previous_commit": current_commit_hash,
                    "rollback_validation": rollback_validation
                }
            )

            await self.session.commit()

            result["status"] = "completed"
            result["backup_info"] = backup_info
            result["previous_commit"] = current_commit_hash

            logger.info(f"Git回滚操作完成: {git_operation.id}, 从 {current_commit_hash[:7]} 回滚到 {target_commit_hash[:7]}")
            return result

        except Exception as e:
            # 回滚操作状态
            if 'git_operation' in locals():
                git_operation.fail(str(e))
                await self.session.commit()

            logger.error(f"Git回滚操作失败: {e}")
            raise BuildError(f"Git回滚失败: {str(e)}")

    async def get_operation_history(
        self,
        project_id: str,
        operation_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        获取Git操作历史。

        Args:
            project_id: 项目ID
            operation_type: 操作类型过滤
            limit: 返回记录数量限制

        Returns:
            操作历史列表
        """
        try:
            query = select(GitOperation).where(GitOperation.project_id == project_id)

            if operation_type:
                query = query.where(GitOperation.operation_type == operation_type)

            query = query.order_by(GitOperation.created_at.desc()).limit(limit)

            result = await self.session.execute(query)
            operations = result.scalars().all()

            return [operation.to_dict() for operation in operations]

        except Exception as e:
            logger.error(f"获取Git操作历史失败: {e}")
            return []

    async def get_operation_details(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """
        获取Git操作详情。

        Args:
            operation_id: 操作ID

        Returns:
            操作详情字典
        """
        try:
            result = await self.session.execute(
                select(GitOperation).where(GitOperation.id == operation_id)
            )
            operation = result.scalars().first()

            if not operation:
                return None

            operation_dict = operation.to_dict()

            # 获取关联的备份信息
            backup_result = await self.session.execute(
                select(RepositoryBackup).where(RepositoryBackup.git_operation_id == operation_id)
            )
            backups = backup_result.scalars().all()
            operation_dict["backups"] = [backup.to_dict() for backup in backups]

            return operation_dict

        except Exception as e:
            logger.error(f"获取Git操作详情失败: {e}")
            return None

    async def get_backup_list(self, project_id: str) -> List[Dict[str, Any]]:
        """
        获取项目的备份列表。

        Args:
            project_id: 项目ID

        Returns:
            备份列表
        """
        try:
            result = await self.session.execute(
                select(RepositoryBackup)
                .join(GitOperation)
                .where(GitOperation.project_id == project_id)
                .where(RepositoryBackup.status == BackupStatus.COMPLETED.value)
                .order_by(RepositoryBackup.created_at.desc())
            )
            backups = result.scalars().all()

            return [backup.to_dict() for backup in backups]

        except Exception as e:
            logger.error(f"获取备份列表失败: {e}")
            return []

    async def restore_from_backup(self, backup_id: str) -> Dict[str, Any]:
        """
        从备份恢复仓库。

        Args:
            backup_id: 备份ID

        Returns:
            恢复结果字典
        """
        try:
            # 获取备份信息
            result = await self.session.execute(
                select(RepositoryBackup).where(RepositoryBackup.id == backup_id)
            )
            backup = result.scalars().first()

            if not backup:
                raise ValidationError(f"备份不存在: {backup_id}")

            if not backup.is_completed:
                raise ValidationError(f"备份未完成: {backup_id}")

            # 获取项目信息
            project = await self._get_project(backup.project_id)
            project_path = Path(project.path)

            # 执行恢复
            restore_success = await self._execute_restore(project_path, backup.backup_path)

            if restore_success:
                # 记录恢复操作
                restore_operation = GitOperation(
                    project_id=backup.project_id,
                    operation_type=OperationType.ROLLBACK.value,
                    status=OperationStatus.COMPLETED.value,
                    description=f"从备份恢复: {backup.id}",
                    config_options={"backup_id": backup_id}
                )

                self.session.add(restore_operation)
                await self.session.commit()

                return {
                    "success": True,
                    "backup_id": backup_id,
                    "restore_operation_id": restore_operation.id,
                    "restored_at": datetime.utcnow().isoformat()
                }
            else:
                raise GitUtilsError("恢复操作失败")

        except Exception as e:
            logger.error(f"从备份恢复失败: {e}")
            raise BuildError(f"恢复失败: {str(e)}")

    async def delete_expired_backups(self, project_id: Optional[str] = None) -> Dict[str, Any]:
        """
        删除过期的备份。

        Args:
            project_id: 项目ID，None表示删除所有项目的过期备份

        Returns:
            删除结果统计
        """
        try:
            query = select(RepositoryBackup).where(
                RepositoryBackup.expires_at < datetime.utcnow()
            )

            if project_id:
                query = query.where(RepositoryBackup.project_id == project_id)

            result = await self.session.execute(query)
            expired_backups = result.scalars().all()

            deleted_count = 0
            total_size_freed = 0

            for backup in expired_backups:
                try:
                    # 删除备份文件
                    backup_file = Path(backup.backup_path)
                    if backup_file.exists():
                        file_size = backup_file.stat().st_size
                        backup_file.unlink()
                        total_size_freed += file_size

                    # 删除数据库记录
                    await self.session.delete(backup)
                    deleted_count += 1

                    logger.info(f"删除过期备份: {backup.id}")

                except Exception as e:
                    logger.error(f"删除备份失败 {backup.id}: {e}")

            await self.session.commit()

            return {
                "deleted_count": deleted_count,
                "total_size_freed": total_size_freed,
                "cleaned_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"删除过期备份失败: {e}")
            raise BuildError(f"清理过期备份失败: {str(e)}")

    # 私有辅助方法

    async def _get_project(self, project_id: str) -> AndroidProject:
        """获取项目信息。"""
        result = await self.session.execute(
            select(AndroidProject).where(AndroidProject.id == project_id)
        )
        project = result.scalars().first()
        if not project:
            raise ValidationError(f"项目不存在: {project_id}")
        return project

    async def _perform_safety_checks(self, project_path: Path, context: str) -> Dict[str, Any]:
        """执行安全检查。"""
        try:
            current_branch = GitUtils.get_current_branch(project_path)
            return GitUtils.check_safety(project_path, current_branch)
        except Exception as e:
            logger.error(f"安全检查失败: {e}")
            return {
                "is_safe": False,
                "issues": [f"安全检查失败: {str(e)}"],
                "warnings": [],
                "recommendations": []
            }

    async def _create_operation_backup(
        self,
        project_id: str,
        git_operation_id: str,
        project_path: Path,
        commit_hash: str,
        branch_name: str
    ) -> Optional[Dict[str, Any]]:
        """创建操作备份。"""
        try:
            # 使用GitUtils创建备份
            backup_name = f"git-op-{git_operation_id[:8]}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
            backup_result = GitUtils.create_backup(project_path, backup_name)

            if backup_result["success"]:
                # 创建备份记录
                backup = RepositoryBackup.create_snapshot_backup(
                    project_id=project_id,
                    git_operation_id=git_operation_id,
                    backup_path=backup_result["backup_path"],
                    commit_hash=commit_hash,
                    branch_name=branch_name,
                    description=f"Git操作前备份: {git_operation_id}"
                )

                backup.backup_size = backup_result["backup_size"]
                backup.complete(metadata=backup_result)

                # 设置过期时间
                backup.set_expiry(days=30)

                self.session.add(backup)
                await self.session.commit()

                return backup.to_dict()
            else:
                logger.warning(f"创建备份失败: {backup_result.get('error', '未知错误')}")
                return None

        except Exception as e:
            logger.error(f"创建操作备份失败: {e}")
            return None

    async def _add_specific_files(self, project_path: Path, files: List[str]) -> bool:
        """添加指定文件到暂存区。"""
        try:
            repo = GitUtils.get_repository(project_path)
            for file_path in files:
                try:
                    repo.git.add(file_path)
                except Exception as e:
                    logger.warning(f"添加文件失败 {file_path}: {e}")
            return True
        except Exception as e:
            logger.error(f"添加指定文件失败: {e}")
            return False

    async def _validate_target_commit(self, project_path: Path, commit_hash: str) -> Dict[str, Any]:
        """验证目标提交。"""
        try:
            repo = GitUtils.get_repository(project_path)

            # 检查提交是否存在
            try:
                commit = repo.commit(commit_hash)
                return {
                    "exists": True,
                    "commit_hash": commit.hexsha,
                    "short_hash": commit.hexsha[:7],
                    "message": commit.message.strip(),
                    "author": str(commit.author),
                    "committed_date": commit.committed_datetime.isoformat()
                }
            except Exception:
                return {
                    "exists": False,
                    "commit_hash": commit_hash,
                    "error": "提交不存在"
                }

        except Exception as e:
            logger.error(f"验证目标提交失败: {e}")
            return {
                "exists": False,
                "commit_hash": commit_hash,
                "error": str(e)
            }

    async def _execute_rollback(self, project_path: Path, target_commit: str) -> bool:
        """执行回滚操作。"""
        try:
            repo = GitUtils.get_repository(project_path)

            # 使用git reset --hard回滚
            repo.git.reset("--hard", target_commit)

            logger.info(f"回滚完成: {project_path} -> {target_commit[:7]}")
            return True

        except Exception as e:
            logger.error(f"执行回滚失败: {e}")
            return False

    async def _validate_rollback_result(self, project_path: Path, target_commit: str) -> Dict[str, Any]:
        """验证回滚结果。"""
        try:
            repo = GitUtils.get_repository(project_path)
            current_commit = repo.head.commit.hexsha

            return {
                "success": current_commit == target_commit,
                "current_commit": current_commit,
                "target_commit": target_commit,
                "matches": current_commit == target_commit
            }

        except Exception as e:
            logger.error(f"验证回滚结果失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _execute_restore(self, project_path: Path, backup_path: str) -> bool:
        """执行恢复操作。"""
        try:
            # 使用GitUtils恢复备份
            backup_name = Path(backup_path).stem
            return GitUtils.restore_backup(project_path, backup_name)

        except Exception as e:
            logger.error(f"执行恢复失败: {e}")
            return False

    async def get_repository_status(self, project_id: str) -> Dict[str, Any]:
        """
        获取Git仓库状态信息。

        Args:
            project_id: 项目ID

        Returns:
            仓库状态信息
        """
        try:
            # 获取项目信息
            project = await self._get_project(project_id)
            project_path = Path(project.path)

            # 验证Git仓库
            if not GitUtils.is_git_repository(project_path):
                raise ValidationError(f"项目路径不是有效的Git仓库: {project_path}")

            # 获取仓库信息
            repo_info = GitUtils.get_repository_info(project_path)

            # 获取当前状态
            status = await GitUtils.get_status(project_path)

            # 获取暂存区文件列表
            staged_files = []
            try:
                repo = GitUtils.get_repository(project_path)
                staged_files = [item.a_path for item in repo.index.diff("HEAD")]
            except Exception as e:
                logger.warning(f"获取暂存区文件列表失败: {e}")

            # 是否为干净工作区（无脏状态且无暂存文件）
            is_clean = (not repo_info.get("is_dirty", False)) and len(staged_files) == 0

            # 获取当前分支
            current_branch = GitUtils.get_current_branch(project_path)

            # 获取远程URL
            try:
                remote_url = await GitUtils.get_remote_url(project_path)
            except:
                remote_url = None

            return {
                "project_id": project_id,
                "is_git_repository": True,
                "current_branch": current_branch,
                "current_commit": repo_info.get("latest_commit", {}),
                "status": status,
                "remote_url": remote_url,
                "repository_info": repo_info,
                "is_clean": is_clean,
                "staged_files": staged_files
            }

        except Exception as e:
            logger.error(f"获取仓库状态失败: {e}")
            raise BuildError(f"获取仓库状态失败: {str(e)}")

    async def get_commit_history(self, project_id: str, limit: int = 50, branch: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取Git提交历史。

        Args:
            project_id: 项目ID
            limit: 返回记录数量限制

        Returns:
            提交历史列表
        """
        try:
            # 获取项目信息
            project = await self._get_project(project_id)
            project_path = Path(project.path)

            # 验证Git仓库
            if not GitUtils.is_git_repository(project_path):
                raise ValidationError(f"项目路径不是有效的Git仓库: {project_path}")

            # 选择目标分支：优先使用传入分支且存在，否则使用当前分支
            try:
                if branch and GitUtils.branch_exists(project_path, branch):
                    target_branch = branch
                else:
                    target_branch = GitUtils.get_current_branch(project_path)
            except Exception:
                target_branch = GitUtils.get_current_branch(project_path)

            # 获取提交历史
            commits = await GitUtils.get_recent_commits(project_path, target_branch, limit)

            return commits

        except Exception as e:
            logger.error(f"获取提交历史失败: {e}")
            raise BuildError(f"获取提交历史失败: {str(e)}")

    async def create_branch(
        self,
        project_id: str,
        branch_name: str,
        source_branch: Optional[str] = None,
        create_backup: bool = True,
        backup_expiry_days: int = 30
    ) -> Dict[str, Any]:
        """
        创建新分支。

        Args:
            project_id: 项目ID
            branch_name: 新分支名称
            source_branch: 源分支名称
            create_backup: 是否创建备份
            backup_expiry_days: 备份过期天数

        Returns:
            操作结果
        """
        try:
            # 获取项目信息
            project = await self._get_project(project_id)
            project_path = Path(project.path)

            # 验证Git仓库
            if not GitUtils.is_git_repository(project_path):
                raise ValidationError(f"项目路径不是有效的Git仓库: {project_path}")

            # 获取当前分支（如果没有指定源分支）
            if not source_branch:
                source_branch = GitUtils.get_current_branch(project_path)

            # 创建Git操作记录
            git_operation = GitOperation(
                project_id=project_id,
                operation_type=OperationType.BRANCH_SWITCH.value,
                status=OperationStatus.PENDING.value,
                description=f"创建分支: {branch_name} 从 {source_branch}",
                config_options={
                    "create_backup": create_backup,
                    "backup_expiry_days": backup_expiry_days,
                    "branch_name": branch_name,
                    "source_branch": source_branch
                }
            )

            self.session.add(git_operation)
            await self.session.flush()

            # 开始操作
            git_operation.start()
            logger.info(f"开始创建分支操作: {git_operation.id}")

            result = {
                "operation_id": git_operation.id,
                "project_id": project_id,
                "branch_name": branch_name,
                "source_branch": source_branch,
                "status": "in_progress",
                "steps": []
            }

            # 步骤1: 获取当前状态
            repo_info_before = GitUtils.get_repository_info(project_path)
            git_operation.commit_hash_before = repo_info_before.get("latest_commit", {}).get("sha")

            # 步骤2: 创建备份（如果需要）
            backup_info = None
            if create_backup:
                backup_info = await self._create_operation_backup(
                    project_id, git_operation.id, project_path,
                    repo_info_before.get("latest_commit", {}).get("sha"),
                    source_branch
                )
                result["steps"].append({
                    "step": "backup_creation",
                    "status": "completed" if backup_info else "skipped",
                    "data": backup_info
                })

            # 步骤3: 切换到源分支
            if source_branch != GitUtils.get_current_branch(project_path):
                switch_success = await GitUtils.switch_branch(project_path, source_branch)
                if not switch_success:
                    raise GitUtilsError(f"切换到源分支失败: {source_branch}")

                result["steps"].append({
                    "step": "switch_to_source_branch",
                    "status": "completed",
                    "data": {"branch": source_branch}
                })

            # 步骤4: 创建新分支
            create_success = await GitUtils.create_branch(project_path, branch_name)
            if not create_success:
                raise GitUtilsError(f"创建分支失败: {branch_name}")

            result["steps"].append({
                "step": "create_branch",
                "status": "completed",
                "data": {"branch": branch_name}
            })

            # 完成操作
            git_operation.complete(
                result_data={
                    "backup_info": backup_info,
                    "branch_name": branch_name,
                    "source_branch": source_branch
                }
            )

            await self.session.commit()

            result["status"] = "completed"
            result["backup_info"] = backup_info

            logger.info(f"创建分支操作完成: {git_operation.id}, 分支: {branch_name}")
            return result

        except Exception as e:
            # 回滚操作状态
            if 'git_operation' in locals():
                git_operation.fail(str(e))
                await self.session.commit()

            logger.error(f"创建分支操作失败: {e}")
            raise BuildError(f"创建分支失败: {str(e)}")

    async def switch_branch(
        self,
        project_id: str,
        branch_name: str,
        create_backup: bool = True,
        backup_expiry_days: int = 30
    ) -> Dict[str, Any]:
        """
        切换到指定分支。

        Args:
            project_id: 项目ID
            branch_name: 目标分支名称
            create_backup: 是否创建备份
            backup_expiry_days: 备份过期天数

        Returns:
            操作结果
        """
        try:
            # 获取项目信息
            project = await self._get_project(project_id)
            project_path = Path(project.path)

            # 验证Git仓库
            if not GitUtils.is_git_repository(project_path):
                raise ValidationError(f"项目路径不是有效的Git仓库: {project_path}")

            # 检查分支是否存在
            if not GitUtils.branch_exists(project_path, branch_name):
                raise ValidationError(f"分支不存在: {branch_name}")

            # 获取当前分支
            current_branch = GitUtils.get_current_branch(project_path)

            # 如果已经在目标分支，直接返回
            if current_branch == branch_name:
                return {
                    "project_id": project_id,
                    "branch_name": branch_name,
                    "status": "already_on_branch",
                    "message": f"已经在分支 {branch_name} 上"
                }

            # 创建Git操作记录
            git_operation = GitOperation(
                project_id=project_id,
                operation_type=OperationType.BRANCH_SWITCH.value,
                status=OperationStatus.PENDING.value,
                description=f"切换分支: {current_branch} -> {branch_name}",
                config_options={
                    "create_backup": create_backup,
                    "backup_expiry_days": backup_expiry_days,
                    "from_branch": current_branch,
                    "to_branch": branch_name
                }
            )

            self.session.add(git_operation)
            await self.session.flush()

            # 开始操作
            git_operation.start()
            logger.info(f"开始切换分支操作: {git_operation.id}")

            result = {
                "operation_id": git_operation.id,
                "project_id": project_id,
                "from_branch": current_branch,
                "to_branch": branch_name,
                "status": "in_progress",
                "steps": []
            }

            # 步骤1: 获取当前状态
            repo_info_before = GitUtils.get_repository_info(project_path)
            git_operation.commit_hash_before = repo_info_before.get("latest_commit", {}).get("sha")

            # 步骤2: 创建备份（如果需要）
            backup_info = None
            if create_backup:
                backup_info = await self._create_operation_backup(
                    project_id, git_operation.id, project_path,
                    repo_info_before.get("latest_commit", {}).get("sha"),
                    current_branch
                )
                result["steps"].append({
                    "step": "backup_creation",
                    "status": "completed" if backup_info else "skipped",
                    "data": backup_info
                })

            # 步骤3: 执行分支切换
            switch_success = await GitUtils.switch_branch(project_path, branch_name)
            if not switch_success:
                raise GitUtilsError(f"切换分支失败: {branch_name}")

            result["steps"].append({
                "step": "switch_branch",
                "status": "completed",
                "data": {"branch": branch_name}
            })

            # 完成操作
            git_operation.complete(
                result_data={
                    "backup_info": backup_info,
                    "from_branch": current_branch,
                    "to_branch": branch_name
                }
            )

            await self.session.commit()

            result["status"] = "completed"
            result["backup_info"] = backup_info

            logger.info(f"切换分支操作完成: {git_operation.id}, {current_branch} -> {branch_name}")
            return result

        except Exception as e:
            # 回滚操作状态
            if 'git_operation' in locals():
                git_operation.fail(str(e))
                await self.session.commit()

            logger.error(f"切换分支操作失败: {e}")
            raise BuildError(f"切换分支失败: {str(e)}")

    async def get_branch_list(self, project_id: str) -> List[str]:
        """
        获取Git分支列表。

        Args:
            project_id: 项目ID

        Returns:
            分支名称列表

        Raises:
            ValidationError: 项目不存在或不是有效的Git仓库
            BuildError: 获取分支列表失败
        """
        try:
            # 获取项目信息
            project = await self._get_project(project_id)
            project_path = Path(project.path)

            # 验证Git仓库
            if not GitUtils.is_git_repository(project_path):
                raise ValidationError(f"项目路径不是有效的Git仓库: {project_path}")

            # 获取所有本地分支
            branches = GitUtils.get_all_branches(project_path, include_remote=False)

            logger.info(f"获取分支列表成功: {project_id}, 分支数: {len(branches)}")
            return branches

        except ValueError as e:
            # 重新抛出ValidationError
            raise
        except Exception as e:
            logger.error(f"获取分支列表失败: {e}")
            raise BuildError(f"获取分支列表失败: {str(e)}")

    async def delete_backup(self, backup_id: str) -> bool:
        """
        删除指定的备份。

        Args:
            backup_id: 备份ID

        Returns:
            删除是否成功
        """
        try:
            # 获取备份信息
            result = await self.session.execute(
                select(RepositoryBackup).where(RepositoryBackup.id == backup_id)
            )
            backup = result.scalars().first()

            if not backup:
                return False

            # 删除备份文件
            backup_file = Path(backup.backup_path)
            if backup_file.exists():
                backup_file.unlink()

            # 删除数据库记录
            await self.session.delete(backup)
            await self.session.commit()

            logger.info(f"删除备份成功: {backup_id}")
            return True

        except Exception as e:
            logger.error(f"删除备份失败: {e}")
            return False