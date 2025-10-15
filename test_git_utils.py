"""
GitUtils 单元测试

测试GitPython安全操作的最佳实践实现
"""

import unittest
import tempfile
import shutil
import os
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import git
from git_utils import (
    GitRepositoryManager, GitFileOperationManager,
    GitOperationError, GitSecurityError
)
from git_error_handling import (
    GitErrorHandler, GitErrorType, GitErrorRecoveryStrategy,
    handle_git_errors
)


class TestGitRepositoryManager(unittest.TestCase):
    """GitRepositoryManager测试类"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.repo_path = Path(self.temp_dir) / "test_repo"
        self.repo_path.mkdir()

        # 初始化Git仓库
        self.test_repo = git.Repo.init(self.repo_path)

        # 配置用户信息（避免提交时需要用户信息）
        with self.test_repo.config_writer() as config:
            config.set_value('user', 'name', 'Test User')
            config.set_value('user', 'email', 'test@example.com')

        # 创建一个初始提交
        test_file = self.repo_path / "README.md"
        test_file.write_text("# Test Repository")
        self.test_repo.index.add([str(test_file)])
        self.test_repo.index.commit("Initial commit")

        self.git_manager = GitRepositoryManager(str(self.repo_path))

    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(self.git_manager.repo_path, self.repo_path.absolute())
        self.assertIsNotNone(self.git_manager.repo)
        self.assertTrue(self.git_manager.backup_dir.exists())

    def test_validate_repository_state_clean(self):
        """测试干净仓库状态验证"""
        self.assertTrue(self.git_manager.validate_repository_state())

    def test_validate_repository_state_dirty(self):
        """测试脏仓库状态验证"""
        # 创建未提交的更改
        test_file = self.repo_path / "test.txt"
        test_file.write_text("test content")

        # 验证应该返回False
        self.assertFalse(self.git_manager.validate_repository_state())

    def test_create_backup(self):
        """测试创建备份"""
        # 创建一些文件
        test_file = self.repo_path / "test.txt"
        test_file.write_text("test content")

        backup_path = self.git_manager.create_backup("test_backup")
        self.assertTrue(Path(backup_path).exists())

        # 检查备份文件
        backup_dir = Path(backup_path)
        self.assertTrue((backup_dir / "test.txt").exists())
        self.assertTrue((backup_dir / "git_state.json").exists())

    def test_restore_backup(self):
        """测试恢复备份"""
        # 创建测试文件
        test_file = self.repo_path / "test.txt"
        original_content = "original content"
        test_file.write_text(original_content)

        # 创建备份
        backup_name = "test_backup"
        self.git_manager.create_backup(backup_name)

        # 修改文件
        test_file.write_text("modified content")
        self.assertEqual(test_file.read_text(), "modified content")

        # 恢复备份
        self.assertTrue(self.git_manager.restore_backup(backup_name))
        self.assertEqual(test_file.read_text(), original_content)

    def test_safe_checkout_branch(self):
        """测试安全分支切换"""
        # 创建新分支
        branch_name = "test-branch"
        self.git_manager.safe_checkout_branch(branch_name, create_if_not_exists=True)

        # 验证分支切换
        self.assertEqual(self.git_manager.repo.active_branch.name, branch_name)

        # 切回主分支
        self.git_manager.safe_checkout_branch("master")
        self.assertEqual(self.git_manager.repo.active_branch.name, "master")

    def test_safe_checkout_branch_with_stash(self):
        """测试带暂存的分支切换"""
        # 创建未提交的更改
        test_file = self.repo_path / "test.txt"
        test_file.write_text("modified content")

        # 切换分支（应该自动暂存）
        branch_name = "test-branch"
        self.git_manager.safe_checkout_branch(branch_name, create_if_not_exists=True)

        # 验证分支切换
        self.assertEqual(self.git_manager.repo.active_branch.name, branch_name)

        # 检查暂存
        stash_list = self.git_manager.repo.git.stash('list')
        self.assertIn('Auto-stash before checkout', stash_list)

    def test_atomic_commit(self):
        """测试原子性提交"""
        # 创建并添加文件
        test_file = self.repo_path / "test.txt"
        test_file.write_text("test content")
        self.git_manager.repo.index.add([str(test_file)])

        # 执行提交
        message = "Test commit"
        commit_hash = self.git_manager.atomic_commit(message)

        # 验证提交
        self.assertEqual(commit_hash, self.git_manager.repo.head.commit.hexsha)
        self.assertEqual(self.git_manager.repo.head.commit.message, message)

    def test_atomic_commit_empty(self):
        """测试空提交"""
        with self.assertRaises(GitOperationError):
            self.git_manager.atomic_commit("Empty commit", allow_empty=False)

    def test_atomic_commit_allow_empty(self):
        """测试允许空提交"""
        commit_hash = self.git_manager.atomic_commit("Empty commit", allow_empty=True)
        self.assertEqual(commit_hash, self.git_manager.repo.head.commit.hexsha)

    def test_get_repository_status(self):
        """测试获取仓库状态"""
        status = self.git_manager.get_repository_status()

        self.assertIn("current_branch", status)
        self.assertIn("current_commit", status)
        self.assertIn("is_detached", status)
        self.assertIn("is_dirty", status)
        self.assertEqual(status["current_branch"], "master")
        self.assertFalse(status["is_detached"])
        self.assertFalse(status["is_dirty"])

    def test_cleanup_old_backups(self):
        """测试清理旧备份"""
        # 创建多个备份
        for i in range(5):
            self.git_manager.create_backup(f"backup_{i}")
            time.sleep(0.1)  # 确保时间戳不同

        # 清理备份，保留2个
        deleted_count = self.git_manager.cleanup_old_backups(keep_count=2)
        self.assertEqual(deleted_count, 3)

        # 验证只剩2个备份
        backups = [d for d in self.git_manager.backup_dir.iterdir()
                  if d.is_dir() and d.name.startswith('backup_')]
        self.assertEqual(len(backups), 2)


class TestGitFileOperationManager(unittest.TestCase):
    """GitFileOperationManager测试类"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.repo_path = Path(self.temp_dir) / "test_repo"
        self.repo_path.mkdir()

        # 初始化Git仓库
        self.test_repo = git.Repo.init(self.repo_path)
        with self.test_repo.config_writer() as config:
            config.set_value('user', 'name', 'Test User')
            config.set_value('user', 'email', 'test@example.com')

        # 创建初始提交
        test_file = self.repo_path / "README.md"
        test_file.write_text("# Test Repository")
        self.test_repo.index.add([str(test_file)])
        self.test_repo.index.commit("Initial commit")

        self.git_manager = GitRepositoryManager(str(self.repo_path))
        self.file_manager = GitFileOperationManager(self.git_manager)

    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_safe_replace_file(self):
        """测试安全文件替换"""
        # 创建测试文件
        test_file = self.repo_path / "test.txt"
        original_content = "original content"
        test_file.write_text(original_content)

        # 替换文件内容
        new_content = "new content"
        self.assertTrue(self.file_manager.safe_replace_file(str(test_file), new_content))

        # 验证内容
        self.assertEqual(test_file.read_text(), new_content)

    def test_safe_replace_file_nonexistent(self):
        """测试替换不存在的文件"""
        nonexistent_file = self.repo_path / "nonexistent.txt"

        with self.assertRaises(GitOperationError):
            self.file_manager.safe_replace_file(str(nonexistent_file), "content")

    def test_batch_file_operations(self):
        """测试批量文件操作"""
        # 准备操作
        operations = [
            {
                "type": "create",
                "path": str(self.repo_path / "file1.txt"),
                "content": "content1"
            },
            {
                "type": "create",
                "path": str(self.repo_path / "file2.txt"),
                "content": "content2"
            }
        ]

        # 执行批量操作
        self.assertTrue(self.file_manager.batch_file_operations(operations))

        # 验证文件创建
        self.assertTrue((self.repo_path / "file1.txt").exists())
        self.assertTrue((self.repo_path / "file2.txt").exists())
        self.assertEqual((self.repo_path / "file1.txt").read_text(), "content1")
        self.assertEqual((self.repo_path / "file2.txt").read_text(), "content2")

    def test_batch_file_operations_with_replace(self):
        """测试包含替换的批量操作"""
        # 创建初始文件
        test_file = self.repo_path / "test.txt"
        test_file.write_text("original")

        # 准备操作
        operations = [
            {
                "type": "replace",
                "path": str(test_file),
                "content": "modified"
            }
        ]

        # 执行批量操作
        self.assertTrue(self.file_manager.batch_file_operations(operations))

        # 验证内容修改
        self.assertEqual(test_file.read_text(), "modified")


class TestGitErrorHandler(unittest.TestCase):
    """GitErrorHandler测试类"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.repo_path = Path(self.temp_dir) / "test_repo"
        self.repo_path.mkdir()

        # 初始化Git仓库
        self.test_repo = git.Repo.init(self.repo_path)
        with self.test_repo.config_writer() as config:
            config.set_value('user', 'name', 'Test User')
            config.set_value('user', 'email', 'test@example.com')

        # 创建初始提交
        test_file = self.repo_path / "README.md"
        test_file.write_text("# Test Repository")
        self.test_repo.index.add([str(test_file)])
        self.test_repo.index.commit("Initial commit")

        self.git_manager = GitRepositoryManager(str(self.repo_path))
        self.error_handler = GitErrorHandler(self.git_manager)

    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_classify_network_error(self):
        """测试网络错误分类"""
        error = git.GitCommandError(['git', 'push'], 'network timeout')
        error_type = self.error_handler.classify_error(error)
        self.assertEqual(error_type, GitErrorType.NETWORK_ERROR)

    def test_classify_permission_error(self):
        """测试权限错误分类"""
        error = PermissionError("access denied")
        error_type = self.error_handler.classify_error(error)
        self.assertEqual(error_type, GitErrorType.PERMISSION_ERROR)

    def test_classify_conflict_error(self):
        """测试冲突错误分类"""
        error = git.GitCommandError(['git', 'merge'], 'merge conflict')
        error_type = self.error_handler.classify_error(error)
        self.assertEqual(error_type, GitErrorType.CONFLICT_ERROR)

    def test_get_recovery_strategy(self):
        """测试获取恢复策略"""
        # 网络错误应该重试
        strategy = self.error_handler.get_recovery_strategy(GitErrorType.NETWORK_ERROR)
        self.assertEqual(strategy, GitErrorRecoveryStrategy.RETRY)

        # 权限错误需要手动干预
        strategy = self.error_handler.get_recovery_strategy(GitErrorType.PERMISSION_ERROR)
        self.assertEqual(strategy, GitErrorRecoveryStrategy.MANUAL_INTERVENTION)

    def test_retry_with_backoff_success(self):
        """测试重试成功"""
        call_count = 0

        def operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("network error")
            return "success"

        result = self.error_handler.retry_with_backoff(operation)
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 2)

    def test_retry_with_backoff_failure(self):
        """测试重试失败"""
        def operation():
            raise ConnectionError("persistent network error")

        with self.assertRaises(ConnectionError):
            self.error_handler.retry_with_backoff(operation)

    def test_log_error(self):
        """测试错误记录"""
        error = Exception("test error")
        self.error_handler.log_error(error, "test_operation", {"context": "test"})

        self.assertEqual(len(self.error_handler.error_history), 1)
        recorded_error = self.error_handler.error_history[0]
        self.assertEqual(recorded_error["operation"], "test_operation")
        self.assertEqual(recorded_error["error_message"], "test error")
        self.assertEqual(recorded_error["context"]["context"], "test")

    def test_get_error_statistics(self):
        """测试错误统计"""
        # 记录一些错误
        self.error_handler.log_error(Exception("error1"), "operation1")
        self.error_handler.log_error(Exception("error2"), "operation1")
        self.error_handler.log_error(Exception("error3"), "operation2")

        stats = self.error_handler.get_error_statistics()
        self.assertEqual(stats["total_errors"], 3)
        self.assertEqual(stats["operations"]["operation1"], 2)
        self.assertEqual(stats["operations"]["operation2"], 1)

    def test_generate_error_report(self):
        """测试错误报告生成"""
        # 记录一些错误
        self.error_handler.log_error(Exception("test error"), "test_operation")

        report = self.error_handler.generate_error_report()
        self.assertIn("Git错误报告", report)
        self.assertIn("test_operation", report)
        self.assertIn("test error", report)


class TestDecorators(unittest.TestCase):
    """装饰器测试类"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.repo_path = Path(self.temp_dir) / "test_repo"
        self.repo_path.mkdir()

        # 初始化Git仓库
        self.test_repo = git.Repo.init(self.repo_path)
        with self.test_repo.config_writer() as config:
            config.set_value('user', 'name', 'Test User')
            config.set_value('user', 'email', 'test@example.com')

        # 创建初始提交
        test_file = self.repo_path / "README.md"
        test_file.write_text("# Test Repository")
        self.test_repo.index.add([str(test_file)])
        self.test_repo.index.commit("Initial commit")

        self.git_manager = GitRepositoryManager(str(self.repo_path))

    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_handle_git_errors_decorator_success(self):
        """测试错误处理装饰器成功情况"""
        @handle_git_errors(self.git_manager, "test_operation")
        def successful_operation():
            return "success"

        result = successful_operation()
        self.assertEqual(result, "success")

    def test_handle_git_errors_decorator_failure(self):
        """测试错误处理装饰器失败情况"""
        @handle_git_errors(self.git_manager, "test_operation")
        def failing_operation():
            raise Exception("test error")

        with self.assertRaises(GitOperationError):
            failing_operation()


class TestIntegration(unittest.TestCase):
    """集成测试类"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.repo_path = Path(self.temp_dir) / "test_repo"
        self.repo_path.mkdir()

        # 初始化Git仓库
        self.test_repo = git.Repo.init(self.repo_path)
        with self.test_repo.config_writer() as config:
            config.set_value('user', 'name', 'Test User')
            config.set_value('user', 'email', 'test@example.com')

        # 创建初始提交
        test_file = self.repo_path / "README.md"
        test_file.write_text("# Test Repository")
        self.test_repo.index.add([str(test_file)])
        self.test_repo.index.commit("Initial commit")

        self.git_manager = GitRepositoryManager(str(self.repo_path))
        self.file_manager = GitFileOperationManager(self.git_manager)
        self.error_handler = GitErrorHandler(self.git_manager)

    def tearDown(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_complete_workflow(self):
        """测试完整工作流程"""
        # 1. 创建备份
        backup_path = self.git_manager.create_backup("workflow_test")

        # 2. 创建新分支
        branch_name = "feature/test"
        self.git_manager.safe_checkout_branch(branch_name, create_if_not_exists=True)

        # 3. 批量文件操作
        operations = [
            {
                "type": "create",
                "path": str(self.repo_path / "feature.txt"),
                "content": "feature content"
            }
        ]
        self.file_manager.batch_file_operations(operations)

        # 4. 提交更改
        self.git_manager.repo.index.add([str(self.repo_path / "feature.txt")])
        commit_hash = self.git_manager.atomic_commit("Add feature file")

        # 5. 切回主分支
        self.git_manager.safe_checkout_branch("master")

        # 6. 合并分支
        self.git_manager.safe_merge_branch(branch_name)

        # 验证结果
        self.assertTrue((self.repo_path / "feature.txt").exists())
        self.assertEqual(self.git_manager.repo.active_branch.name, "master")

        # 7. 清理备份
        deleted_count = self.git_manager.cleanup_old_backups(keep_count=1)
        self.assertGreaterEqual(deleted_count, 0)


if __name__ == "__main__":
    # 设置测试环境
    unittest.main(verbosity=2)