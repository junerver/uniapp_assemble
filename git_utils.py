"""
GitPython 安全操作最佳实践模块

本模块提供了一套完整的Git安全操作工具，包括：
1. 分支切换安全性检查
2. 资源备份和回滚机制
3. 原子性提交操作
4. 并发操作处理
5. 状态检测和错误恢复
6. 敏感操作安全验证
"""

import os
import shutil
import time
import hashlib
import tempfile
import threading
from contextlib import contextmanager
from typing import Optional, List, Dict, Any, Callable, Union
from pathlib import Path
from datetime import datetime
import logging

import git
from git import Repo, InvalidGitRepositoryError, NoSuchPathError, GitCommandError

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GitOperationError(Exception):
    """Git操作自定义异常"""
    pass


class GitSecurityError(GitOperationError):
    """Git安全相关异常"""
    pass


class GitRepositoryManager:
    """
    Git仓库安全管理器

    提供安全的Git操作，包括分支切换、提交、备份等功能
    """

    def __init__(self, repo_path: str, backup_dir: Optional[str] = None):
        """
        初始化Git仓库管理器

        Args:
            repo_path: Git仓库路径
            backup_dir: 备份目录路径，如果为None则使用默认备份目录
        """
        self.repo_path = Path(repo_path).absolute()
        self.backup_dir = Path(backup_dir) if backup_dir else self.repo_path / ".git_backups"
        self.backup_dir.mkdir(exist_ok=True)

        # 加载仓库
        try:
            self.repo = Repo(self.repo_path)
        except InvalidGitRepositoryError:
            raise GitOperationError(f"路径 {repo_path} 不是有效的Git仓库")
        except NoSuchPathError:
            raise GitOperationError(f"路径 {repo_path} 不存在")

        # 操作锁，用于并发控制
        self._operation_lock = threading.Lock()

        # 操作历史记录
        self.operation_history: List[Dict[str, Any]] = []

    def _log_operation(self, operation: str, details: Dict[str, Any] = None):
        """记录操作历史"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "details": details or {}
        }
        self.operation_history.append(entry)
        logger.info(f"Git操作记录: {operation} - {details}")

    def validate_repository_state(self) -> bool:
        """
        验证仓库状态的完整性

        Returns:
            bool: 仓库状态是否正常
        """
        try:
            # 检查是否有未解决的合并冲突
            if self.repo.index.unmerged_blobs():
                logger.warning("检测到未解决的合并冲突")
                return False

            # 检查是否处于detached HEAD状态
            if self.repo.head.is_detached:
                logger.warning("仓库处于detached HEAD状态")
                return False

            # 检查工作区是否干净
            if self.repo.is_dirty(untracked_files=True):
                logger.warning("工作区存在未提交的更改")
                return False

            # 验证Git对象数据库完整性
            try:
                self.repo.git.fsck()
            except GitCommandError as e:
                logger.error(f"Git对象数据库检查失败: {e}")
                return False

            return True

        except Exception as e:
            logger.error(f"仓库状态验证失败: {e}")
            return False

    def create_backup(self, backup_name: Optional[str] = None) -> str:
        """
        创建仓库备份

        Args:
            backup_name: 备份名称，如果为None则自动生成

        Returns:
            str: 备份目录路径
        """
        if not backup_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_{timestamp}"

        backup_path = self.backup_dir / backup_name

        try:
            # 创建备份目录
            backup_path.mkdir(exist_ok=True)

            # 备份工作区文件（排除.git目录）
            for item in self.repo_path.iterdir():
                if item.name != '.git':
                    dest = backup_path / item.name
                    if item.is_dir():
                        shutil.copytree(item, dest, ignore=shutil.ignore_patterns('.git'))
                    else:
                        shutil.copy2(item, dest)

            # 备份Git状态信息
            state_info = {
                "current_branch": self.repo.active_branch.name,
                "current_commit": self.repo.head.commit.hexsha,
                "is_dirty": self.repo.is_dirty(),
                "untracked_files": [f for f in self.repo.untracked_files],
                "staged_files": [item.a_path for item in self.repo.index.iter_blobs()],
                "modified_files": [item.a_path for item in self.repo.index.diff(None)]
            }

            state_file = backup_path / "git_state.json"
            import json
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(state_info, f, indent=2, ensure_ascii=False)

            self._log_operation("create_backup", {"backup_name": backup_name, "backup_path": str(backup_path)})
            logger.info(f"备份创建成功: {backup_path}")

            return str(backup_path)

        except Exception as e:
            # 如果备份失败，清理部分创建的备份
            if backup_path.exists():
                shutil.rmtree(backup_path)
            raise GitOperationError(f"创建备份失败: {e}")

    def restore_backup(self, backup_name: str, force: bool = False) -> bool:
        """
        从备份恢复仓库

        Args:
            backup_name: 备份名称
            force: 是否强制恢复（忽略当前更改）

        Returns:
            bool: 恢复是否成功
        """
        backup_path = self.backup_dir / backup_name

        if not backup_path.exists():
            raise GitOperationError(f"备份 {backup_name} 不存在")

        # 安全检查
        if not force and self.repo.is_dirty(untracked_files=True):
            raise GitSecurityError("工作区存在未提交的更改，使用force=True强制恢复")

        try:
            # 再次创建当前状态的备份
            current_backup = self.create_backup(f"before_restore_{backup_name}_{int(time.time())}")

            # 清理当前工作区（保留.git目录）
            for item in self.repo_path.iterdir():
                if item.name != '.git':
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()

            # 恢复备份文件
            for item in backup_path.iterdir():
                if item.name != 'git_state.json':
                    dest = self.repo_path / item.name
                    if item.is_dir():
                        shutil.copytree(item, dest)
                    else:
                        shutil.copy2(item, dest)

            # 读取并恢复Git状态
            state_file = backup_path / "git_state.json"
            if state_file.exists():
                import json
                with open(state_file, 'r', encoding='utf-8') as f:
                    state_info = json.load(f)

                # 切换到原来的分支
                if 'current_branch' in state_info:
                    try:
                        self.repo.git.checkout(state_info['current_branch'])
                    except GitCommandError:
                        logger.warning(f"无法切换到分支 {state_info['current_branch']}")

            self._log_operation("restore_backup", {
                "backup_name": backup_name,
                "current_backup": current_backup
            })

            logger.info(f"从备份 {backup_name} 恢复成功")
            return True

        except Exception as e:
            logger.error(f"恢复备份失败: {e}")
            return False

    @contextmanager
    def safe_operation_context(self, operation_name: str, auto_backup: bool = True):
        """
        安全操作上下文管理器

        Args:
            operation_name: 操作名称
            auto_backup: 是否自动创建备份
        """
        backup_path = None

        with self._operation_lock:
            try:
                # 操作前状态检查
                if not self.validate_repository_state():
                    raise GitSecurityError("仓库状态不安全，无法执行操作")

                # 创建备份
                if auto_backup:
                    backup_path = self.create_backup(f"before_{operation_name}_{int(time.time())}")

                logger.info(f"开始执行安全操作: {operation_name}")
                yield

                self._log_operation(operation_name, {"status": "success", "backup": backup_path})
                logger.info(f"操作 {operation_name} 执行成功")

            except Exception as e:
                self._log_operation(operation_name, {"status": "failed", "error": str(e), "backup": backup_path})
                logger.error(f"操作 {operation_name} 执行失败: {e}")

                # 尝试回滚
                if backup_path:
                    try:
                        self.restore_backup(Path(backup_path).name, force=True)
                        logger.info("已自动回滚到操作前状态")
                    except Exception as rollback_error:
                        logger.error(f"自动回滚失败: {rollback_error}")

                raise

    def safe_checkout_branch(self, branch_name: str, create_if_not_exists: bool = False) -> bool:
        """
        安全切换分支

        Args:
            branch_name: 目标分支名
            create_if_not_exists: 如果分支不存在是否创建

        Returns:
            bool: 切换是否成功
        """
        with self.safe_operation_context(f"checkout_branch_{branch_name}"):
            # 检查分支是否存在
            try:
                target_branch = self.repo.branches[branch_name]
            except IndexError:
                if not create_if_not_exists:
                    raise GitOperationError(f"分支 {branch_name} 不存在")
                target_branch = self.repo.create_head(branch_name)

            # 检查当前分支状态
            if self.repo.is_dirty():
                # 暂存当前更改
                self.repo.git.stash('push', '-m', f'Auto-stash before checkout to {branch_name}')
                self._log_operation("stash_changes", {"branch": branch_name})

            # 切换分支
            target_branch.checkout()

            # 检查切换后的状态
            if self.repo.head.is_detached:
                raise GitSecurityError("切换后处于detached HEAD状态")

            logger.info(f"成功切换到分支: {branch_name}")
            return True

    def atomic_commit(self, message: str, files: Optional[List[str]] = None,
                     allow_empty: bool = False) -> str:
        """
        原子性提交操作

        Args:
            message: 提交信息
            files: 要提交的文件列表，如果为None则提交所有暂存的更改
            allow_empty: 是否允许空提交

        Returns:
            str: 提交哈希值
        """
        with self.safe_operation_context("atomic_commit"):
            # 预提交检查
            if not allow_empty and not self.repo.index.diff("HEAD"):
                raise GitOperationError("没有要提交的更改")

            # 添加文件到暂存区
            if files:
                for file_path in files:
                    try:
                        self.repo.index.add([file_path])
                    except Exception as e:
                        raise GitOperationError(f"添加文件 {file_path} 到暂存区失败: {e}")

            # 执行提交
            try:
                commit = self.repo.index.commit(message)
                commit_hash = commit.hexsha

                # 验证提交是否成功
                if commit_hash != self.repo.head.commit.hexsha:
                    raise GitOperationError("提交验证失败")

                self._log_operation("commit", {
                    "hash": commit_hash,
                    "message": message,
                    "files": files
                })

                logger.info(f"提交成功: {commit_hash[:8]} - {message}")
                return commit_hash

            except Exception as e:
                raise GitOperationError(f"提交失败: {e}")

    def safe_merge_branch(self, source_branch: str, target_branch: Optional[str] = None,
                         strategy: str = "merge", fast_forward: bool = True) -> bool:
        """
        安全合并分支

        Args:
            source_branch: 源分支名
            target_branch: 目标分支名，如果为None则使用当前分支
            strategy: 合并策略 ("merge" 或 "rebase")
            fast_forward: 是否允许快进合并

        Returns:
            bool: 合并是否成功
        """
        operation_name = f"merge_{source_branch}_to_{target_branch or 'current'}"

        with self.safe_operation_context(operation_name):
            # 保存当前分支
            original_branch = self.repo.active_branch.name

            # 切换到目标分支
            if target_branch and target_branch != original_branch:
                self.safe_checkout_branch(target_branch)

            try:
                if strategy == "merge":
                    # 执行合并
                    merge_result = self.repo.merge(source_branch)

                    # 检查合并结果
                    if merge_result.conflicts:
                        # 中止合并
                        self.repo.git.merge('--abort')
                        raise GitOperationError(f"合并 {source_branch} 时产生冲突")

                elif strategy == "rebase":
                    # 执行变基
                    self.repo.git.rebase(source_branch)

                else:
                    raise GitOperationError(f"不支持的合并策略: {strategy}")

                self._log_operation("merge", {
                    "source": source_branch,
                    "target": target_branch or original_branch,
                    "strategy": strategy
                })

                logger.info(f"成功合并 {source_branch} 到 {target_branch or original_branch}")
                return True

            except GitCommandError as e:
                # 尝试中止操作
                try:
                    if strategy == "merge":
                        self.repo.git.merge('--abort')
                    elif strategy == "rebase":
                        self.repo.git.rebase('--abort')
                except:
                    pass

                raise GitOperationError(f"合并失败: {e}")

            finally:
                # 切回原分支
                if target_branch and target_branch != original_branch:
                    self.safe_checkout_branch(original_branch)

    def get_repository_status(self) -> Dict[str, Any]:
        """
        获取仓库状态信息

        Returns:
            Dict[str, Any]: 仓库状态信息
        """
        try:
            status = {
                "current_branch": self.repo.active_branch.name,
                "current_commit": self.repo.head.commit.hexsha,
                "is_detached": self.repo.head.is_detached,
                "is_dirty": self.repo.is_dirty(),
                "untracked_files": list(self.repo.untracked_files),
                "modified_files": [item.a_path for item in self.repo.index.diff(None)],
                "staged_files": [item.a_path for item in self.repo.index.diff("HEAD")],
                "branch_count": len(list(self.repo.branches)),
                "remote_count": len(list(self.repo.remotes)),
                "last_commit_time": self.repo.head.commit.committed_datetime.isoformat(),
                "operation_count": len(self.operation_history)
            }

            # 检查是否有冲突
            try:
                status["has_conflicts"] = bool(self.repo.index.unmerged_blobs())
            except:
                status["has_conflicts"] = False

            return status

        except Exception as e:
            logger.error(f"获取仓库状态失败: {e}")
            return {"error": str(e)}

    def cleanup_old_backups(self, keep_count: int = 10) -> int:
        """
        清理旧备份

        Args:
            keep_count: 保留的备份数量

        Returns:
            int: 删除的备份数量
        """
        try:
            backups = [d for d in self.backup_dir.iterdir() if d.is_dir() and d.name.startswith('backup_')]
            backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)

            deleted_count = 0
            for backup in backups[keep_count:]:
                shutil.rmtree(backup)
                deleted_count += 1
                logger.info(f"删除旧备份: {backup.name}")

            self._log_operation("cleanup_backups", {"deleted_count": deleted_count})
            return deleted_count

        except Exception as e:
            logger.error(f"清理备份失败: {e}")
            return 0


class GitFileOperationManager:
    """
    Git文件操作安全管理器

    专门处理文件级别的安全操作
    """

    def __init__(self, git_manager: GitRepositoryManager):
        self.git_manager = git_manager
        self.file_checksums: Dict[str, str] = {}

    def calculate_file_checksum(self, file_path: str) -> str:
        """计算文件校验和"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ""

    def safe_replace_file(self, file_path: str, new_content: str,
                         create_backup: bool = True) -> bool:
        """
        安全替换文件内容

        Args:
            file_path: 文件路径
            new_content: 新文件内容
            create_backup: 是否创建文件备份

        Returns:
            bool: 操作是否成功
        """
        file_path = Path(file_path)

        with self.git_manager.safe_operation_context(f"replace_file_{file_path.name}"):
            # 检查文件是否存在
            if not file_path.exists():
                raise GitOperationError(f"文件 {file_path} 不存在")

            # 计算当前文件校验和
            current_checksum = self.calculate_file_checksum(str(file_path))

            # 创建文件备份
            if create_backup:
                backup_path = file_path.with_suffix(f".backup_{int(time.time())}")
                shutil.copy2(file_path, backup_path)
                logger.info(f"创建文件备份: {backup_path}")

            try:
                # 写入新内容
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)

                # 验证文件内容
                with open(file_path, 'r', encoding='utf-8') as f:
                    if f.read() != new_content:
                        raise GitOperationError("文件内容验证失败")

                # 记录校验和变化
                new_checksum = self.calculate_file_checksum(str(file_path))
                self.file_checksums[str(file_path)] = {
                    "old": current_checksum,
                    "new": new_checksum
                }

                self.git_manager._log_operation("replace_file", {
                    "file_path": str(file_path),
                    "checksum_old": current_checksum,
                    "checksum_new": new_checksum
                })

                logger.info(f"文件 {file_path} 替换成功")
                return True

            except Exception as e:
                # 恢复文件
                if create_backup and backup_path.exists():
                    shutil.copy2(backup_path, file_path)
                    backup_path.unlink()

                raise GitOperationError(f"文件替换失败: {e}")

    def batch_file_operations(self, operations: List[Dict[str, Any]]) -> bool:
        """
        批量文件操作

        Args:
            operations: 操作列表，每个操作包含类型、路径、内容等信息

        Returns:
            bool: 操作是否成功
        """
        operation_id = f"batch_ops_{int(time.time())}"

        with self.git_manager.safe_operation_context(operation_id):
            # 预检查所有文件
            for op in operations:
                file_path = Path(op["path"])
                if not file_path.exists() and op["type"] != "create":
                    raise GitOperationError(f"文件 {file_path} 不存在")

            # 执行操作
            results = []
            for op in operations:
                try:
                    if op["type"] == "replace":
                        success = self.safe_replace_file(op["path"], op["content"], create_backup=False)
                    elif op["type"] == "create":
                        with open(op["path"], 'w', encoding='utf-8') as f:
                            f.write(op["content"])
                        success = True
                    elif op["type"] == "delete":
                        file_path = Path(op["path"])
                        file_path.unlink()
                        success = True
                    else:
                        raise GitOperationError(f"不支持的操作类型: {op['type']}")

                    results.append({"path": op["path"], "success": success})

                except Exception as e:
                    results.append({"path": op["path"], "success": False, "error": str(e)})

            # 检查是否所有操作都成功
            failed_ops = [r for r in results if not r["success"]]
            if failed_ops:
                raise GitOperationError(f"部分操作失败: {failed_ops}")

            self.git_manager._log_operation("batch_operations", {
                "operation_count": len(operations),
                "success_count": len([r for r in results if r["success"]])
            })

            logger.info(f"批量操作完成: {len(operations)} 个操作")
            return True


# 使用示例和测试函数
def demo_git_operations():
    """演示Git安全操作的使用"""

    # 初始化Git仓库管理器
    try:
        git_manager = GitRepositoryManager(".", backup_dir="./git_backups")
        file_manager = GitFileOperationManager(git_manager)

        print("=== Git仓库状态 ===")
        status = git_manager.get_repository_status()
        for key, value in status.items():
            print(f"{key}: {value}")

        print("\n=== 创建备份 ===")
        backup_path = git_manager.create_backup("demo_backup")
        print(f"备份路径: {backup_path}")

        print("\n=== 安全切换分支示例 ===")
        # 注意：这需要在实际的Git仓库中运行
        # git_manager.safe_checkout_branch("feature-branch", create_if_not_exists=True)

        print("\n=== 文件操作示例 ===")
        # file_manager.safe_replace_file("example.txt", "新的文件内容")

        print("\n=== 清理旧备份 ===")
        deleted_count = git_manager.cleanup_old_backups(keep_count=5)
        print(f"删除了 {deleted_count} 个旧备份")

    except GitOperationError as e:
        print(f"Git操作错误: {e}")
    except Exception as e:
        print(f"未知错误: {e}")


if __name__ == "__main__":
    demo_git_operations()