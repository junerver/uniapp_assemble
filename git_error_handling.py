"""
GitPython 错误处理和恢复策略模块

提供详细的错误分类、处理策略和恢复机制
"""

import time
import traceback
from enum import Enum
from typing import Optional, Dict, Any, List, Callable
from pathlib import Path
import logging

from git import GitCommandError, InvalidGitRepositoryError, NoSuchPathError
from git_utils import GitOperationError, GitSecurityError, GitRepositoryManager

logger = logging.getLogger(__name__)


class GitErrorType(Enum):
    """Git错误类型枚举"""
    NETWORK_ERROR = "network_error"
    PERMISSION_ERROR = "permission_error"
    LOCK_ERROR = "lock_error"
    CONFLICT_ERROR = "conflict_error"
    STATE_ERROR = "state_error"
    REPOSITORY_ERROR = "repository_error"
    COMMAND_ERROR = "command_error"
    IO_ERROR = "io_error"
    UNKNOWN_ERROR = "unknown_error"


class GitErrorRecoveryStrategy(Enum):
    """Git错误恢复策略枚举"""
    RETRY = "retry"
    BACKUP_AND_RESTORE = "backup_and_restore"
    RESET_TO_SAFE_STATE = "reset_to_safe_state"
    MANUAL_INTERVENTION = "manual_intervention"
    IGNORE = "ignore"


class GitErrorHandler:
    """
    Git错误处理器

    提供错误分类、处理策略和恢复机制
    """

    def __init__(self, git_manager: GitRepositoryManager):
        self.git_manager = git_manager
        self.error_history: List[Dict[str, Any]] = []
        self.retry_config = {
            "max_retries": 3,
            "retry_delay": 1.0,
            "exponential_backoff": True
        }

    def classify_error(self, error: Exception) -> GitErrorType:
        """
        分类Git错误

        Args:
            error: 异常对象

        Returns:
            GitErrorType: 错误类型
        """
        error_str = str(error).lower()

        # 网络相关错误
        if any(keyword in error_str for keyword in [
            "network", "connection", "timeout", "unreachable", "dns"
        ]):
            return GitErrorType.NETWORK_ERROR

        # 权限相关错误
        elif any(keyword in error_str for keyword in [
            "permission", "access denied", "read-only", "locked"
        ]):
            return GitErrorType.PERMISSION_ERROR

        # 锁相关错误
        elif any(keyword in error_str for keyword in [
            "lock", "locked", "unable to lock", "index.lock"
        ]):
            return GitErrorType.LOCK_ERROR

        # 冲突相关错误
        elif any(keyword in error_str for keyword in [
            "conflict", "merge conflict", "unmerged", "needs merge"
        ]):
            return GitErrorType.CONFLICT_ERROR

        # 状态相关错误
        elif any(keyword in error_str for keyword in [
            "detached head", "not a git repository", "invalid state"
        ]):
            return GitErrorType.STATE_ERROR

        # 仓库相关错误
        elif isinstance(error, (InvalidGitRepositoryError, NoSuchPathError)):
            return GitErrorType.REPOSITORY_ERROR

        # Git命令错误
        elif isinstance(error, GitCommandError):
            return GitErrorType.COMMAND_ERROR

        # IO错误
        elif any(keyword in error_str for keyword in [
            "file not found", "no such file", "disk space", "io error"
        ]):
            return GitErrorType.IO_ERROR

        else:
            return GitErrorType.UNKNOWN_ERROR

    def get_recovery_strategy(self, error_type: GitErrorType) -> GitErrorRecoveryStrategy:
        """
        根据错误类型获取恢复策略

        Args:
            error_type: 错误类型

        Returns:
            GitErrorRecoveryStrategy: 恢复策略
        """
        strategy_map = {
            GitErrorType.NETWORK_ERROR: GitErrorRecoveryStrategy.RETRY,
            GitErrorType.PERMISSION_ERROR: GitErrorRecoveryStrategy.MANUAL_INTERVENTION,
            GitErrorType.LOCK_ERROR: GitErrorRecoveryStrategy.RETRY,
            GitErrorType.CONFLICT_ERROR: GitErrorRecoveryStrategy.MANUAL_INTERVENTION,
            GitErrorType.STATE_ERROR: GitErrorRecoveryStrategy.RESET_TO_SAFE_STATE,
            GitErrorType.REPOSITORY_ERROR: GitErrorRecoveryStrategy.MANUAL_INTERVENTION,
            GitErrorType.COMMAND_ERROR: GitErrorRecoveryStrategy.BACKUP_AND_RESTORE,
            GitErrorType.IO_ERROR: GitErrorRecoveryStrategy.MANUAL_INTERVENTION,
            GitErrorType.UNKNOWN_ERROR: GitErrorRecoveryStrategy.BACKUP_AND_RESTORE,
        }

        return strategy_map.get(error_type, GitErrorRecoveryStrategy.BACKUP_AND_RESTORE)

    def log_error(self, error: Exception, operation: str, context: Dict[str, Any] = None):
        """记录错误信息"""
        error_info = {
            "timestamp": time.time(),
            "operation": operation,
            "error_type": self.classify_error(error).value,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "context": context or {}
        }

        self.error_history.append(error_info)
        logger.error(f"Git错误记录: {operation} - {error_info['error_type']} - {error}")

    def retry_with_backoff(self, operation: Callable, *args, **kwargs) -> Any:
        """
        带退避的重试机制

        Args:
            operation: 要重试的操作函数
            *args: 操作函数的参数
            **kwargs: 操作函数的关键字参数

        Returns:
            Any: 操作结果

        Raises:
            Exception: 重试失败后抛出原始异常
        """
        max_retries = self.retry_config["max_retries"]
        delay = self.retry_config["retry_delay"]
        exponential = self.retry_config["exponential_backoff"]

        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    logger.info(f"重试操作 (第 {attempt} 次): {operation.__name__}")
                    time.sleep(delay)
                    if exponential:
                        delay *= 2

                result = operation(*args, **kwargs)
                if attempt > 0:
                    logger.info(f"重试成功: {operation.__name__}")
                return result

            except Exception as e:
                last_exception = e
                error_type = self.classify_error(e)
                strategy = self.get_recovery_strategy(error_type)

                if attempt == max_retries:
                    logger.error(f"重试失败，已达到最大重试次数: {max_retries}")
                    break

                # 某些错误类型不适合重试
                if strategy != GitErrorRecoveryStrategy.RETRY:
                    logger.error(f"错误类型 {error_type.value} 不适合重试")
                    break

                logger.warning(f"操作失败，准备重试: {e}")

        raise last_exception

    def handle_lock_error(self) -> bool:
        """
        处理Git锁错误

        Returns:
            bool: 处理是否成功
        """
        try:
            # 查找并删除锁文件
            lock_files = [
                self.git_manager.repo_path / ".git" / "index.lock",
                self.git_manager.repo_path / ".git" / "HEAD.lock"
            ]

            removed_locks = 0
            for lock_file in lock_files:
                if lock_file.exists():
                    lock_file.unlink()
                    removed_locks += 1
                    logger.info(f"删除锁文件: {lock_file}")

            if removed_locks > 0:
                logger.info(f"成功删除 {removed_locks} 个锁文件")
                return True
            else:
                logger.info("未发现锁文件")
                return False

        except Exception as e:
            logger.error(f"处理锁错误失败: {e}")
            return False

    def reset_to_safe_state(self, backup_name: Optional[str] = None) -> bool:
        """
        重置到安全状态

        Args:
            backup_name: 指定备份名称，如果为None则使用最新备份

        Returns:
            bool: 重置是否成功
        """
        try:
            if backup_name:
                return self.git_manager.restore_backup(backup_name, force=True)
            else:
                # 使用最新备份
                backups = [d for d in self.git_manager.backup_dir.iterdir()
                          if d.is_dir() and d.name.startswith('backup_')]
                if backups:
                    latest_backup = max(backups, key=lambda x: x.stat().st_mtime)
                    return self.git_manager.restore_backup(latest_backup.name, force=True)
                else:
                    logger.warning("没有可用的备份")
                    return False

        except Exception as e:
            logger.error(f"重置到安全状态失败: {e}")
            return False

    def handle_conflict_resolution(self, strategy: str = "abort") -> bool:
        """
        处理合并冲突

        Args:
            strategy: 处理策略 ("abort", "ours", "theirs")

        Returns:
            bool: 处理是否成功
        """
        try:
            if strategy == "abort":
                self.git_manager.repo.git.merge('--abort')
                self.git_manager.repo.git.rebase('--abort')
                logger.info("中止合并/变基操作")
            elif strategy == "ours":
                self.git_manager.repo.git.merge('--strategy-option', 'ours')
                logger.info("使用我们的版本解决冲突")
            elif strategy == "theirs":
                self.git_manager.repo.git.merge('--strategy-option', 'theirs')
                logger.info("使用他们的版本解决冲突")
            else:
                raise ValueError(f"不支持的冲突解决策略: {strategy}")

            return True

        except Exception as e:
            logger.error(f"冲突解决失败: {e}")
            return False

    def safe_operation_with_recovery(self, operation: Callable, operation_name: str,
                                    *args, **kwargs) -> Any:
        """
        带恢复机制的安全操作

        Args:
            operation: 要执行的操作函数
            operation_name: 操作名称
            *args: 操作函数的参数
            **kwargs: 操作函数的关键字参数

        Returns:
            Any: 操作结果

        Raises:
            Exception: 操作失败且无法恢复时抛出异常
        """
        backup_name = None

        try:
            # 执行操作
            result = operation(*args, **kwargs)
            logger.info(f"操作 {operation_name} 执行成功")
            return result

        except Exception as e:
            error_type = self.classify_error(e)
            strategy = self.get_recovery_strategy(error_type)

            self.log_error(e, operation_name, {
                "error_type": error_type.value,
                "recovery_strategy": strategy.value
            })

            logger.warning(f"操作 {operation_name} 失败，错误类型: {error_type.value}")

            # 根据策略进行恢复
            if strategy == GitErrorRecoveryStrategy.RETRY:
                try:
                    result = self.retry_with_backoff(operation, *args, **kwargs)
                    logger.info(f"重试成功: {operation_name}")
                    return result
                except Exception as retry_error:
                    logger.error(f"重试失败: {operation_name}")
                    raise retry_error

            elif strategy == GitErrorRecoveryStrategy.BACKUP_AND_RESTORE:
                # 创建当前状态备份
                backup_name = f"error_recovery_{operation_name}_{int(time.time())}"
                self.git_manager.create_backup(backup_name)

                # 尝试恢复到上一个安全状态
                if self.reset_to_safe_state():
                    logger.info(f"已恢复到安全状态: {operation_name}")
                else:
                    logger.error(f"无法恢复到安全状态: {operation_name}")

                raise e

            elif strategy == GitErrorRecoveryStrategy.RESET_TO_SAFE_STATE:
                if self.reset_to_safe_state():
                    logger.info(f"已重置到安全状态: {operation_name}")
                else:
                    logger.error(f"无法重置到安全状态: {operation_name}")

                raise e

            elif strategy == GitErrorRecoveryStrategy.MANUAL_INTERVENTION:
                logger.error(f"需要手动干预: {operation_name} - {e}")
                raise GitOperationError(f"操作 {operation_name} 需要手动干预: {e}")

            else:
                raise e

    def get_error_statistics(self) -> Dict[str, Any]:
        """
        获取错误统计信息

        Returns:
            Dict[str, Any]: 错误统计信息
        """
        if not self.error_history:
            return {"total_errors": 0}

        total_errors = len(self.error_history)
        error_types = {}
        operations = {}

        for error in self.error_history:
            # 统计错误类型
            error_type = error["error_type"]
            error_types[error_type] = error_types.get(error_type, 0) + 1

            # 统计操作
            operation = error["operation"]
            operations[operation] = operations.get(operation, 0) + 1

        return {
            "total_errors": total_errors,
            "error_types": error_types,
            "operations": operations,
            "most_common_error": max(error_types.items(), key=lambda x: x[1]) if error_types else None,
            "most_problematic_operation": max(operations.items(), key=lambda x: x[1]) if operations else None
        }

    def generate_error_report(self) -> str:
        """
        生成错误报告

        Returns:
            str: 错误报告文本
        """
        stats = self.get_error_statistics()

        report = []
        report.append("=== Git错误报告 ===")
        report.append(f"总错误数: {stats['total_errors']}")

        if stats['total_errors'] > 0:
            report.append("\n错误类型统计:")
            for error_type, count in stats['error_types'].items():
                report.append(f"  {error_type}: {count}")

            report.append("\n操作错误统计:")
            for operation, count in stats['operations'].items():
                report.append(f"  {operation}: {count}")

            if stats['most_common_error']:
                error_type, count = stats['most_common_error']
                report.append(f"\n最常见错误: {error_type} ({count} 次)")

            if stats['most_problematic_operation']:
                operation, count = stats['most_problematic_operation']
                report.append(f"问题最多的操作: {operation} ({count} 次)")

        report.append("\n最近错误详情:")
        for error in self.error_history[-5:]:  # 显示最近5个错误
            report.append(f"  时间: {time.ctime(error['timestamp'])}")
            report.append(f"  操作: {error['operation']}")
            report.append(f"  类型: {error['error_type']}")
            report.append(f"  消息: {error['error_message']}")
            report.append("")

        return "\n".join(report)


# 全局错误处理装饰器
def handle_git_errors(git_manager: GitRepositoryManager, operation_name: Optional[str] = None):
    """
    Git错误处理装饰器

    Args:
        git_manager: Git仓库管理器实例
        operation_name: 操作名称，如果为None则使用函数名
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            error_handler = GitErrorHandler(git_manager)
            op_name = operation_name or func.__name__

            return error_handler.safe_operation_with_recovery(
                func, op_name, *args, **kwargs
            )

        return wrapper
    return decorator


# 使用示例
def demo_error_handling():
    """演示错误处理的使用"""
    try:
        # 初始化Git仓库管理器
        git_manager = GitRepositoryManager(".", backup_dir="./git_backups")
        error_handler = GitErrorHandler(git_manager)

        print("=== 错误处理演示 ===")

        # 模拟一个可能失败的操作
        @handle_git_errors(git_manager, "demo_operation")
        def risky_operation():
            # 这里故意制造一个错误来演示错误处理
            raise GitCommandError(["git", "invalid-command"], "模拟错误")

        try:
            risky_operation()
        except GitOperationError as e:
            print(f"捕获到处理后的错误: {e}")

        # 显示错误统计
        print("\n=== 错误统计 ===")
        stats = error_handler.get_error_statistics()
        print(f"总错误数: {stats['total_errors']}")

        # 生成错误报告
        print("\n=== 错误报告 ===")
        report = error_handler.generate_error_report()
        print(report)

    except Exception as e:
        print(f"演示失败: {e}")


if __name__ == "__main__":
    demo_error_handling()