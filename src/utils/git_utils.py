"""
Git操作工具模块。

提供Git分支检测、仓库状态检查和安全性验证功能。
"""

import asyncio
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from git import Repo, GitCommandError, InvalidGitRepositoryError
from git.exc import NoSuchPathError

logger = logging.getLogger(__name__)


class GitUtilsError(Exception):
    """Git工具错误基类。"""
    pass


class NotAGitRepositoryError(GitUtilsError):
    """不是有效的Git仓库。"""
    pass


class BranchNotFoundError(GitUtilsError):
    """分支不存在。"""
    pass


class GitUtils:
    """Git操作工具类。"""

    @staticmethod
    def is_git_repository(path: str | Path) -> bool:
        """
        检查路径是否为有效的Git仓库。

        Args:
            path: 要检查的路径

        Returns:
            如果是有效的Git仓库返回True，否则返回False
        """
        try:
            repo_path = Path(path)
            if not repo_path.exists():
                return False

            Repo(repo_path)
            return True
        except (InvalidGitRepositoryError, NoSuchPathError):
            return False
        except Exception as e:
            logger.warning(f"检查Git仓库时出错: {e}")
            return False

    @staticmethod
    def get_repository(path: str | Path) -> Repo:
        """
        获取Git仓库对象。

        Args:
            path: Git仓库路径

        Returns:
            Git仓库对象

        Raises:
            NotAGitRepositoryError: 如果路径不是有效的Git仓库
        """
        try:
            repo_path = Path(path)
            if not repo_path.exists():
                raise NotAGitRepositoryError(f"路径不存在: {path}")

            repo = Repo(repo_path)
            return repo
        except InvalidGitRepositoryError:
            raise NotAGitRepositoryError(f"不是有效的Git仓库: {path}")
        except NoSuchPathError:
            raise NotAGitRepositoryError(f"路径不存在: {path}")

    @staticmethod
    def get_current_branch(path: str | Path) -> str:
        """
        获取当前分支名称。

        Args:
            path: Git仓库路径

        Returns:
            当前分支名称

        Raises:
            NotAGitRepositoryError: 如果路径不是有效的Git仓库
        """
        try:
            repo = GitUtils.get_repository(path)

            # 检查是否处于分离HEAD状态
            if repo.head.is_detached:
                return f"HEAD (detached at {repo.head.commit.hexsha[:7]})"

            return repo.active_branch.name
        except Exception as e:
            logger.error(f"获取当前分支失败: {e}")
            raise

    @staticmethod
    def get_all_branches(path: str | Path, include_remote: bool = False) -> List[str]:
        """
        获取所有分支列表。

        Args:
            path: Git仓库路径
            include_remote: 是否包含远程分支

        Returns:
            分支名称列表

        Raises:
            NotAGitRepositoryError: 如果路径不是有效的Git仓库
        """
        try:
            repo = GitUtils.get_repository(path)
            branches = []

            # 本地分支
            for branch in repo.heads:
                branches.append(branch.name)

            # 远程分支
            if include_remote:
                for remote in repo.remotes:
                    for ref in remote.refs:
                        # 过滤掉HEAD引用
                        if not ref.name.endswith('/HEAD'):
                            branches.append(ref.name)

            return sorted(branches)
        except Exception as e:
            logger.error(f"获取分支列表失败: {e}")
            raise

    @staticmethod
    def branch_exists(path: str | Path, branch_name: str) -> bool:
        """
        检查分支是否存在。

        Args:
            path: Git仓库路径
            branch_name: 分支名称

        Returns:
            如果分支存在返回True，否则返回False

        Raises:
            NotAGitRepositoryError: 如果路径不是有效的Git仓库
        """
        try:
            branches = GitUtils.get_all_branches(path, include_remote=True)
            # 检查本地分支和远程分支
            return branch_name in branches or f"origin/{branch_name}" in branches
        except Exception as e:
            logger.error(f"检查分支是否存在失败: {e}")
            raise

    @staticmethod
    def get_repository_info(path: str | Path) -> Dict[str, Any]:
        """
        获取Git仓库信息。

        Args:
            path: Git仓库路径

        Returns:
            仓库信息字典，包含：
            - current_branch: 当前分支
            - is_dirty: 是否有未提交的更改
            - untracked_files: 未跟踪文件数量
            - modified_files: 已修改文件数量
            - remote_url: 远程仓库URL（如果有）
            - latest_commit: 最新提交信息

        Raises:
            NotAGitRepositoryError: 如果路径不是有效的Git仓库
        """
        try:
            repo = GitUtils.get_repository(path)

            # 获取远程URL
            remote_url = None
            if repo.remotes:
                try:
                    remote_url = repo.remotes.origin.url
                except AttributeError:
                    # 没有origin远程
                    remote_url = repo.remotes[0].url if repo.remotes else None

            # 获取最新提交信息
            latest_commit = None
            try:
                commit = repo.head.commit
                latest_commit = {
                    "sha": commit.hexsha,
                    "short_sha": commit.hexsha[:7],
                    "message": commit.message.strip(),
                    "author": str(commit.author),
                    "committed_date": commit.committed_datetime.isoformat()
                }
            except Exception as e:
                logger.warning(f"获取最新提交信息失败: {e}")

            # 统计文件变更
            untracked_files = len(repo.untracked_files)
            modified_files = len([item.a_path for item in repo.index.diff(None)])

            return {
                "current_branch": GitUtils.get_current_branch(path),
                "is_dirty": repo.is_dirty(untracked_files=True),
                "untracked_files": untracked_files,
                "modified_files": modified_files,
                "remote_url": remote_url,
                "latest_commit": latest_commit,
                "repository_path": str(Path(path).resolve())
            }
        except Exception as e:
            logger.error(f"获取仓库信息失败: {e}")
            raise

    @staticmethod
    def has_uncommitted_changes(path: str | Path) -> bool:
        """
        检查是否有未提交的更改。

        Args:
            path: Git仓库路径

        Returns:
            如果有未提交的更改返回True，否则返回False

        Raises:
            NotAGitRepositoryError: 如果路径不是有效的Git仓库
        """
        try:
            repo = GitUtils.get_repository(path)
            return repo.is_dirty(untracked_files=True)
        except Exception as e:
            logger.error(f"检查未提交更改失败: {e}")
            raise

    @staticmethod
    def get_branch_info(path: str | Path, branch_name: str) -> Dict[str, Any]:
        """
        获取特定分支的详细信息。

        Args:
            path: Git仓库路径
            branch_name: 分支名称

        Returns:
            分支信息字典

        Raises:
            NotAGitRepositoryError: 如果路径不是有效的Git仓库
            BranchNotFoundError: 如果分支不存在
        """
        try:
            repo = GitUtils.get_repository(path)

            # 查找分支
            branch = None
            for head in repo.heads:
                if head.name == branch_name:
                    branch = head
                    break

            if not branch:
                raise BranchNotFoundError(f"分支不存在: {branch_name}")

            # 获取分支最新提交
            commit = branch.commit

            return {
                "name": branch.name,
                "commit_sha": commit.hexsha,
                "short_sha": commit.hexsha[:7],
                "commit_message": commit.message.strip(),
                "author": str(commit.author),
                "committed_date": commit.committed_datetime.isoformat(),
                "is_current": repo.active_branch.name == branch_name if not repo.head.is_detached else False
            }
        except BranchNotFoundError:
            raise
        except Exception as e:
            logger.error(f"获取分支信息失败: {e}")
            raise

    @staticmethod
    def is_clean_working_tree(path: str | Path) -> bool:
        """
        检查工作目录是否干净（没有未提交的更改和未跟踪的文件）。

        Args:
            path: Git仓库路径

        Returns:
            如果工作目录干净返回True，否则返回False

        Raises:
            NotAGitRepositoryError: 如果路径不是有效的Git仓库
        """
        try:
            repo = GitUtils.get_repository(path)
            return not repo.is_dirty(untracked_files=True) and len(repo.untracked_files) == 0
        except Exception as e:
            logger.error(f"检查工作目录状态失败: {e}")
            raise

    @staticmethod
    def list_directories_in_branch(
        path: str | Path,
        branch_name: str,
        directory_path: str = "app/src/main/assets/apps"
    ) -> List[str]:
        """
        列出指定分支的特定路径下的文件夹列表(不切换分支)。

        Args:
            path: Git仓库路径
            branch_name: 分支名称
            directory_path: 要列出的目录路径(相对于仓库根目录)

        Returns:
            文件夹名称列表

        Raises:
            NotAGitRepositoryError: 如果路径不是有效的Git仓库
            BranchNotFoundError: 如果分支不存在
        """
        try:
            repo = GitUtils.get_repository(path)

            # 处理远程分支名称
            ref_name = branch_name
            if branch_name.startswith("origin/"):
                # 远程分支:使用refs/remotes/格式
                ref_name = f"refs/remotes/{branch_name}"
            else:
                # 本地分支:先检查是否存在
                found = False
                for head in repo.heads:
                    if head.name == branch_name:
                        found = True
                        ref_name = f"refs/heads/{branch_name}"
                        break

                if not found:
                    # 尝试作为远程分支
                    ref_name = f"refs/remotes/origin/{branch_name}"

            # 获取分支的commit
            try:
                commit = repo.commit(ref_name)
            except Exception:
                raise BranchNotFoundError(f"分支不存在: {branch_name}")

            # 获取指定路径的tree对象
            try:
                tree = commit.tree
                # 导航到指定目录
                for part in directory_path.split('/'):
                    if part:
                        tree = tree / part
            except KeyError:
                # 路径不存在,返回空列表
                logger.warning(f"路径在分支 {branch_name} 中不存在: {directory_path}")
                return []

            # 列出所有文件夹
            directories = []
            for item in tree:
                if item.type == 'tree':  # tree类型表示文件夹
                    directories.append(item.name)

            return sorted(directories)

        except BranchNotFoundError:
            raise
        except Exception as e:
            logger.error(f"列出分支目录失败: {e}")
            raise

    @staticmethod
    def check_safety(path: str | Path, branch_name: str) -> Dict[str, Any]:
        """
        执行Git安全检查。

        Args:
            path: Git仓库路径
            branch_name: 要操作的分支名称

        Returns:
            安全检查结果字典，包含：
            - is_safe: 是否安全
            - issues: 发现的问题列表
            - warnings: 警告列表
            - recommendations: 建议操作列表

        Raises:
            NotAGitRepositoryError: 如果路径不是有效的Git仓库
            BranchNotFoundError: 如果分支不存在
        """
        try:
            repo = GitUtils.get_repository(path)
            current_branch = GitUtils.get_current_branch(path)

            safety_result = {
                "is_safe": True,
                "issues": [],
                "warnings": [],
                "recommendations": [],
                "current_branch": current_branch,
                "target_branch": branch_name,
                "checks": {}
            }

            # 检查1: 分支是否存在
            safety_result["checks"]["branch_exists"] = GitUtils.branch_exists(path, branch_name)
            if not safety_result["checks"]["branch_exists"]:
                safety_result["is_safe"] = False
                safety_result["issues"].append(f"目标分支 '{branch_name}' 不存在")
                return safety_result

            # 检查2: 工作区状态
            is_dirty = GitUtils.has_uncommitted_changes(path)
            safety_result["checks"]["working_tree_clean"] = not is_dirty

            if is_dirty:
                safety_result["is_safe"] = False
                repo_info = GitUtils.get_repository_info(path)

                if repo_info["untracked_files"] > 0:
                    safety_result["issues"].append(f"有 {repo_info['untracked_files']} 个未跟踪文件")

                if repo_info["modified_files"] > 0:
                    safety_result["issues"].append(f"有 {repo_info['modified_files']} 个修改文件")

                safety_result["recommendations"].append("建议先提交或暂存所有更改")
                safety_result["recommendations"].append("或者使用 '--force' 选项强制执行")

            # 检查3: 是否在目标分支上
            is_on_target_branch = current_branch == branch_name
            safety_result["checks"]["on_target_branch"] = is_on_target_branch

            if not is_on_target_branch:
                safety_result["warnings"].append(f"当前分支 '{current_branch}' 与目标分支 '{branch_name}' 不同")
                safety_result["recommendations"].append(f"切换到分支 '{branch_name}' 后再执行操作")

            # 检查4: 是否有未推送的提交
            try:
                # 获取本地和远程的提交差异
                if repo.remotes:
                    remote = repo.remotes.origin
                    try:
                        # 检查是否有未推送的提交
                        ahead_count = len(list(repo.iter_commits(f'{branch_name}..origin/{branch_name}')))
                        safety_result["checks"]["up_to_date_with_remote"] = ahead_count == 0

                        if ahead_count > 0:
                            safety_result["warnings"].append(f"有 {ahead_count} 个提交未推送到远程仓库")
                            safety_result["recommendations"].append("建议先推送提交到远程仓库")
                    except Exception:
                        # 远程仓库可能不存在或无法访问
                        safety_result["warnings"].append("无法检查远程仓库状态")
                        safety_result["checks"]["up_to_date_with_remote"] = None
                else:
                    safety_result["warnings"].append("没有配置远程仓库")
                    safety_result["checks"]["up_to_date_with_remote"] = None
            except Exception as e:
                logger.warning(f"检查远程仓库状态失败: {e}")
                safety_result["warnings"].append("检查远程仓库状态时出错")
                safety_result["checks"]["up_to_date_with_remote"] = None

            # 检查5: 检查是否有冲突标记文件
            conflict_files = []
            ignored_patterns = [
                '.git', 'build', '.idea', 'gradle', 'target', 'out', 'intermediates',
                'cache', 'tmp', 'temp', 'bak', 'backup', 'node_modules', '.gradle',
                'local.properties', 'proguard-rules.pro'
            ]

            try:
                for root, dirs, files in os.walk(path):
                    # 跳过忽略的目录
                    if any(ignored in root for ignored in ignored_patterns):
                        continue

                    for file in files:
                        file_path = os.path.join(root, file)

                        # 跳过忽略的文件扩展名
                        if file.endswith(('.jar', '.dex', '.class', '.so', '.aar')):
                            continue

                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                lines = content.split('\n')

                                # 检测真正的Git冲突标记
                                for i, line in enumerate(lines):
                                    stripped_line = line.strip()
                                    # Git冲突标记通常在行首
                                    if (stripped_line.startswith('<<<<<<<') or
                                        stripped_line.startswith('=======') or
                                        stripped_line.startswith('>>>>>>>')):
                                        # 进一步验证是否为Git冲突标记
                                        # Git冲突标记格式：<<<<<<< HEAD, =======, >>>>>>> branch_name
                                        if (re.match(r'^<<<<<<<\s*(\w+)?', stripped_line) or
                                            stripped_line == '======' or
                                            re.match(r'^>>>>>>>\s*\w+', stripped_line)):
                                            relative_path = os.path.relpath(file_path, path)
                                            conflict_files.append(relative_path)
                                            logger.warning(f"发现Git冲突标记: {relative_path}:{i+1}")
                                            break
                        except Exception:
                            continue
            except Exception as e:
                logger.warning(f"检查冲突文件失败: {e}")

            safety_result["checks"]["no_conflicts"] = len(conflict_files) == 0
            if conflict_files:
                safety_result["is_safe"] = False
                safety_result["issues"].append(f"发现 {len(conflict_files)} 个冲突文件: {', '.join(conflict_files)}")
                safety_result["recommendations"].append("先解决所有合并冲突")

            # 检查6: 检查重要的项目文件
            important_files = [
                "app/build.gradle",
                "build.gradle",
                "gradle.properties",
                "settings.gradle",
                "app/src/main/AndroidManifest.xml"
            ]

            missing_files = []
            for file_path in important_files:
                full_path = Path(path) / file_path
                if not full_path.exists():
                    missing_files.append(file_path)

            safety_result["checks"]["important_files_exist"] = len(missing_files) == 0
            if missing_files:
                safety_result["warnings"].append(f"缺少重要文件: {', '.join(missing_files)}")

            # 检查7: 检查Git hooks
            git_dir = Path(path) / ".git"
            hooks_dir = git_dir / "hooks"
            safety_result["checks"]["git_hooks_exist"] = hooks_dir.exists()

            if not hooks_dir.exists():
                safety_result["warnings"].append("没有配置Git hooks")
                safety_result["recommendations"].append("考虑配置pre-commit hooks来提高代码质量")

            # 检查8: 检查.gitignore文件
            gitignore_path = Path(path) / ".gitignore"
            safety_result["checks"]["gitignore_exists"] = gitignore_path.exists()

            if not gitignore_path.exists():
                safety_result["warnings"].append("没有配置.gitignore文件")
                safety_result["recommendations"].append("创建.gitignore文件以排除不需要版本控制的文件")

            # 检查9: 仓库大小检查
            try:
                total_size = 0
                file_count = 0
                for root, dirs, files in os.walk(path):
                    # 跳过.git目录
                    if '.git' in root:
                        continue

                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            file_size = os.path.getsize(file_path)
                            total_size += file_size
                            file_count += 1
                        except OSError:
                            continue

                safety_result["checks"]["repository_size"] = {
                    "total_size_mb": round(total_size / (1024 * 1024), 2),
                    "file_count": file_count
                }

                # 检查仓库是否过大
                if total_size > 1024 * 1024 * 1024:  # 1GB
                    safety_result["warnings"].append(f"仓库大小较大: {round(total_size / (1024 * 1024 * 1024), 2)} GB")
                    safety_result["recommendations"].append("考虑使用Git LFS来管理大文件")

            except Exception as e:
                logger.warning(f"检查仓库大小失败: {e}")

            logger.info(f"Git安全检查完成: {path}, 分支: {branch_name}, 安全: {safety_result['is_safe']}")
            return safety_result

        except BranchNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Git安全检查失败: {e}")
            raise

    @staticmethod
    def create_backup(path: str | Path, backup_name: str) -> Dict[str, Any]:
        """
        创建仓库备份。

        Args:
            path: Git仓库路径
            backup_name: 备份名称

        Returns:
            备份结果字典

        Raises:
            NotAGitRepositoryError: 如果路径不是有效的Git仓库
        """
        try:
            repo = GitUtils.get_repository(path)

            # 创建备份目录
            backup_dir = Path(path) / ".git-backups" / backup_name
            backup_dir.mkdir(parents=True, exist_ok=True)

            # 使用git archive创建备份
            backup_file = backup_dir / f"{backup_name}.tar.gz"

            result = subprocess.run(
                ["git", "archive", "--format=tar.gz",
                 "--output=" + str(backup_file), "HEAD"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                # 获取备份文件信息
                stat = backup_file.stat()

                backup_result = {
                    "success": True,
                    "backup_name": backup_name,
                    "backup_path": str(backup_file),
                    "backup_size": stat.st_size,
                    "created_at": datetime.utcnow().isoformat()
                }

                logger.info(f"创建Git备份成功: {backup_file}")
                return backup_result
            else:
                raise GitUtilsError(f"创建备份失败: {result.stderr}")

        except Exception as e:
            logger.error(f"创建Git备份失败: {e}")
            raise GitUtilsError(f"创建Git备份失败: {str(e)}")

    @staticmethod
    def restore_backup(path: str | Path, backup_name: str) -> bool:
        """
        恢复仓库备份。

        Args:
            path: Git仓库路径
            backup_name: 备份名称

        Returns:
            恢复是否成功

        Raises:
            NotAGitRepositoryError: 如果路径不是有效的Git仓库
        """
        try:
            repo = GitUtils.get_repository(path)

            backup_file = Path(path) / ".git-backups" / backup_name / f"{backup_name}.tar.gz"

            if not backup_file.exists():
                raise GitUtilsError(f"备份文件不存在: {backup_file}")

            # 恢复备份
            result = subprocess.run(
                ["tar", "xzf", str(backup_file), "-C", path],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                logger.info(f"恢复Git备份成功: {backup_file}")
                return True
            else:
                raise GitUtilsError(f"恢复备份失败: {result.stderr}")

        except Exception as e:
            logger.error(f"恢复Git备份失败: {e}")
            raise GitUtilsError(f"恢复Git备份失败: {str(e)}")

    @staticmethod
    def list_backups(path: str | Path) -> List[Dict[str, Any]]:
        """
        列出所有可用的备份。

        Args:
            path: Git仓库路径

        Returns:
            备份列表

        Raises:
            NotAGitRepositoryError: 如果路径不是有效的Git仓库
        """
        try:
            backup_dir = Path(path) / ".git-backups"
            if not backup_dir.exists():
                return []

            backups = []
            for backup_item in backup_dir.iterdir():
                if backup_item.is_dir():
                    backup_file = backup_item / f"{backup_item.name}.tar.gz"
                    if backup_file.exists():
                        stat = backup_file.stat()
                        backups.append({
                            "name": backup_item.name,
                            "path": str(backup_file),
                            "size": stat.st_size,
                            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                        })

            return sorted(backups, key=lambda x: x["created_at"], reverse=True)

        except Exception as e:
            logger.error(f"列出备份失败: {e}")
            raise GitUtilsError(f"列出备份失败: {str(e)}")

    @staticmethod
    def delete_backup(path: str | Path, backup_name: str) -> bool:
        """
        删除备份。

        Args:
            path: Git仓库路径
            backup_name: 备份名称

        Returns:
            删除是否成功

        Raises:
            NotAGitRepositoryError: 如果路径不是有效的Git仓库
        """
        try:
            backup_dir = Path(path) / ".git-backups" / backup_name

            if backup_dir.exists():
                import shutil
                shutil.rmtree(backup_dir)
                logger.info(f"删除备份成功: {backup_name}")
                return True
            else:
                raise GitUtilsError(f"备份不存在: {backup_name}")

        except Exception as e:
            logger.error(f"删除备份失败: {e}")
            raise GitUtilsError(f"删除备份失败: {str(e)}")

    @staticmethod
    async def create_backup(path: str | Path, backup_name: str, include_untracked: bool = True) -> Optional[str]:
        """
        异步创建仓库备份。

        Args:
            path: Git仓库路径
            backup_name: 备份名称
            include_untracked: 是否包含未跟踪的文件

        Returns:
            备份文件路径，失败时返回None
        """
        try:
            result = GitUtils.create_backup(path, backup_name)
            return result.get("backup_path") if result.get("success") else None
        except Exception as e:
            logger.error(f"异步创建备份失败: {e}")
            return None

    @staticmethod
    async def restore_backup(path: str | Path, backup_path: str) -> bool:
        """
        异步恢复仓库备份。

        Args:
            path: Git仓库路径
            backup_path: 备份文件路径

        Returns:
            恢复是否成功
        """
        try:
            # 提取备份名称
            backup_name = Path(backup_path).stem
            return GitUtils.restore_backup(path, backup_name)
        except Exception as e:
            logger.error(f"异步恢复备份失败: {e}")
            return False

    @staticmethod
    async def list_backups(path: str | Path) -> List[Dict[str, Any]]:
        """
        异步列出所有可用的备份。

        Args:
            path: Git仓库路径

        Returns:
            备份列表
        """
        try:
            return GitUtils.list_backups(path)
        except Exception as e:
            logger.error(f"异步列出备份失败: {e}")
            return []

    @staticmethod
    async def create_branch(path: str | Path, branch_name: str) -> bool:
        """
        异步创建新分支。

        Args:
            path: Git仓库路径
            branch_name: 分支名称

        Returns:
            创建是否成功
        """
        try:
            repo = GitUtils.get_repository(path)

            # 检查分支是否已存在
            if branch_name in [head.name for head in repo.heads]:
                logger.warning(f"分支已存在: {branch_name}")
                return True

            # 创建新分支
            new_branch = repo.create_head(branch_name)
            logger.info(f"创建分支成功: {branch_name}")
            return True

        except Exception as e:
            logger.error(f"创建分支失败: {e}")
            return False

    @staticmethod
    async def switch_branch(path: str | Path, branch_name: str) -> bool:
        """
        异步切换分支。

        Args:
            path: Git仓库路径
            branch_name: 分支名称

        Returns:
            切换是否成功
        """
        try:
            repo = GitUtils.get_repository(path)

            # 查找分支
            target_branch = None
            for head in repo.heads:
                if head.name == branch_name:
                    target_branch = head
                    break

            if not target_branch:
                logger.error(f"分支不存在: {branch_name}")
                return False

            # 切换分支
            target_branch.checkout()
            logger.info(f"切换到分支成功: {branch_name}")
            return True

        except Exception as e:
            logger.error(f"切换分支失败: {e}")
            return False

    @staticmethod
    async def add_all(path: str | Path) -> bool:
        """
        异步添加所有更改到暂存区。

        Args:
            path: Git仓库路径

        Returns:
            添加是否成功
        """
        try:
            repo = GitUtils.get_repository(path)
            repo.git.add("-A")
            return True
        except Exception as e:
            logger.error(f"添加文件到暂存区失败: {e}")
            return False

    @staticmethod
    async def add_modified(path: str | Path) -> bool:
        """
        异步添加已修改的文件到暂存区。

        Args:
            path: Git仓库路径

        Returns:
            添加是否成功
        """
        try:
            repo = GitUtils.get_repository(path)
            repo.git.add("-u")
            return True
        except Exception as e:
            logger.error(f"添加修改文件到暂存区失败: {e}")
            return False

    @staticmethod
    async def commit(path: str | Path, message: str) -> bool:
        """
        异步提交更改。

        Args:
            path: Git仓库路径
            message: 提交消息

        Returns:
            提交是否成功
        """
        try:
            repo = GitUtils.get_repository(path)
            repo.git.commit("-m", message)
            return True
        except Exception as e:
            logger.error(f"提交更改失败: {e}")
            return False

    @staticmethod
    async def get_status(path: str | Path) -> Dict[str, Any]:
        """
        异步获取仓库状态。

        Args:
            path: Git仓库路径

        Returns:
            仓库状态信息
        """
        try:
            repo = GitUtils.get_repository(path)

            # 获取状态信息
            status_output = repo.git.status("--porcelain")

            modified_files = []
            untracked_files = []

            for line in status_output.split('\n'):
                if line.strip():
                    status_code = line[:2]
                    file_path = line[3:]

                    if status_code == "??":
                        untracked_files.append(file_path)
                    else:
                        modified_files.append(file_path)

            return {
                "has_changes": len(modified_files) > 0 or len(untracked_files) > 0,
                "modified_files": modified_files,
                "untracked_files": untracked_files,
                "is_dirty": repo.is_dirty(untracked_files=True)
            }

        except Exception as e:
            logger.error(f"获取仓库状态失败: {e}")
            return {}

    @staticmethod
    async def get_recent_commits(path: str | Path, branch_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        异步获取最近的提交记录。

        Args:
            path: Git仓库路径
            branch_name: 分支名称
            limit: 提交数量限制

        Returns:
            提交记录列表
        """
        try:
            repo = GitUtils.get_repository(path)

            # 查找分支
            target_branch = None
            for head in repo.heads:
                if head.name == branch_name:
                    target_branch = head
                    break

            if not target_branch:
                return []

            commits = []
            for commit in target_branch.commit.iter_items(max_count=limit):
                commits.append({
                    "sha": commit.hexsha,
                    "short_sha": commit.hexsha[:7],
                    "message": commit.message.strip(),
                    "author": str(commit.author),
                    "committed_date": commit.committed_datetime.isoformat()
                })

            return commits

        except Exception as e:
            logger.error(f"获取提交记录失败: {e}")
            return []

    @staticmethod
    async def get_remote_url(path: str | Path) -> Optional[str]:
        """
        异步获取远程仓库URL。

        Args:
            path: Git仓库路径

        Returns:
            远程仓库URL，失败时返回None
        """
        try:
            repo = GitUtils.get_repository(path)
            repo_info = GitUtils.get_repository_info(path)
            return repo_info.get("remote_url")
        except Exception as e:
            logger.error(f"获取远程仓库URL失败: {e}")
            return None

    @staticmethod
    def is_clean_working_directory(path: str | Path) -> bool:
        """
        检查工作目录是否干净（包含未跟踪文件）。

        Args:
            path: Git仓库路径

        Returns:
            工作目录是否干净
        """
        try:
            repo = GitUtils.get_repository(path)
            return not repo.is_dirty(untracked_files=True)
        except Exception as e:
            logger.error(f"检查工作目录状态失败: {e}")
            return False
