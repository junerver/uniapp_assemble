"""
Git安全操作核心概念演示

这个文件展示了Git安全操作的核心概念和最佳实践，
不依赖外部库，可以独立运行来理解设计理念。
"""

import os
import shutil
import tempfile
import time
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from contextlib import contextmanager
import threading


class MockGitOperationError(Exception):
    """模拟Git操作异常"""
    pass


class MockGitSecurityError(MockGitOperationError):
    """模拟Git安全异常"""
    pass


class MockGitRepository:
    """模拟Git仓库类"""

    def __init__(self, path: str):
        self.path = Path(path)
        self.head_commit = "initial_commit_hash"
        self.current_branch = "master"
        self.is_detached = False
        self.files = {}
        self.index = MockGitIndex()
        self.remotes = {"origin": "https://github.com/example/repo.git"}
        self.branches = {"master": MockGitBranch("master", self.head_commit)}

    def is_dirty(self, untracked_files: bool = False) -> bool:
        """检查仓库是否有未提交的更改"""
        return bool(self.index.staged_files) or (untracked_files and len(self.files) > 0)

    def add_file(self, file_path: str, content: str):
        """添加文件到仓库"""
        self.files[file_path] = content

    def commit(self, message: str) -> str:
        """模拟提交"""
        commit_hash = hashlib.md5(f"{message}{time.time()}".encode()).hexdigest()
        self.head_commit = commit_hash
        self.index.staged_files.clear()
        return commit_hash


class MockGitIndex:
    """模拟Git索引"""

    def __init__(self):
        self.staged_files = set()

    def add(self, files: List[str]):
        """添加文件到暂存区"""
        self.staged_files.update(files)


class MockGitBranch:
    """模拟Git分支"""

    def __init__(self, name: str, commit_hash: str):
        self.name = name
        self.commit_hash = commit_hash


class MockGitRepositoryManager:
    """
    模拟Git仓库安全管理器

    展示Git安全操作的核心概念，不依赖实际的GitPython库
    """

    def __init__(self, repo_path: str, backup_dir: Optional[str] = None):
        self.repo_path = Path(repo_path).absolute()
        self.backup_dir = Path(backup_dir) if backup_dir else self.repo_path / ".git_backups"
        self.backup_dir.mkdir(exist_ok=True)

        # 模拟Git仓库
        self.repo = MockGitRepository(str(self.repo_path))

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
        print(f"[日志] Git操作记录: {operation} - {details}")

    def validate_repository_state(self) -> bool:
        """验证仓库状态的完整性"""
        try:
            # 检查是否有未解决的合并冲突
            if hasattr(self.repo.index, 'unmerged_blobs') and self.repo.index.unmerged_blobs():
                print("⚠️ 检测到未解决的合并冲突")
                return False

            # 检查是否处于detached HEAD状态
            if self.repo.is_detached:
                print("⚠️ 仓库处于detached HEAD状态")
                return False

            # 检查工作区是否干净
            if self.repo.is_dirty(untracked_files=True):
                print("⚠️ 工作区存在未提交的更改")
                return False

            return True

        except Exception as e:
            print(f"❌ 仓库状态验证失败: {e}")
            return False

    def create_backup(self, backup_name: Optional[str] = None) -> str:
        """创建仓库备份"""
        if not backup_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_{timestamp}"

        backup_path = self.backup_dir / backup_name

        try:
            # 创建备份目录
            backup_path.mkdir(exist_ok=True)

            # 备份工作区文件
            for item in self.repo_path.iterdir():
                if item.name != '.git_backups':
                    dest = backup_path / item.name
                    if item.is_dir():
                        shutil.copytree(item, dest, ignore=shutil.ignore_patterns('.git_backups'))
                    else:
                        shutil.copy2(item, dest)

            # 备份Git状态信息
            state_info = {
                "current_branch": self.repo.current_branch,
                "current_commit": self.repo.head_commit,
                "is_dirty": self.repo.is_dirty(),
                "staged_files": list(self.repo.index.staged_files),
                "files": list(self.repo.files.keys())
            }

            state_file = backup_path / "git_state.json"
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(state_info, f, indent=2, ensure_ascii=False)

            self._log_operation("create_backup", {"backup_name": backup_name, "backup_path": str(backup_path)})
            print(f"✅ 备份创建成功: {backup_path}")

            return str(backup_path)

        except Exception as e:
            # 如果备份失败，清理部分创建的备份
            if backup_path.exists():
                shutil.rmtree(backup_path)
            raise MockGitOperationError(f"创建备份失败: {e}")

    def restore_backup(self, backup_name: str, force: bool = False) -> bool:
        """从备份恢复仓库"""
        backup_path = self.backup_dir / backup_name

        if not backup_path.exists():
            raise MockGitOperationError(f"备份 {backup_name} 不存在")

        # 安全检查
        if not force and self.repo.is_dirty(untracked_files=True):
            raise MockGitSecurityError("工作区存在未提交的更改，使用force=True强制恢复")

        try:
            # 再次创建当前状态的备份
            current_backup = self.create_backup(f"before_restore_{backup_name}_{int(time.time())}")

            # 清理当前工作区（保留备份目录）
            for item in self.repo_path.iterdir():
                if item.name != '.git_backups':
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
                with open(state_file, 'r', encoding='utf-8') as f:
                    state_info = json.load(f)

                # 恢复模拟仓库状态
                self.repo.current_branch = state_info.get('current_branch', 'master')
                self.repo.head_commit = state_info.get('current_commit', 'initial')
                self.repo.index.staged_files = set(state_info.get('staged_files', []))

            self._log_operation("restore_backup", {
                "backup_name": backup_name,
                "current_backup": current_backup
            })

            print(f"✅ 从备份 {backup_name} 恢复成功")
            return True

        except Exception as e:
            print(f"❌ 恢复备份失败: {e}")
            return False

    @contextmanager
    def safe_operation_context(self, operation_name: str, auto_backup: bool = True):
        """安全操作上下文管理器"""
        backup_path = None

        with self._operation_lock:
            try:
                # 操作前状态检查
                if not self.validate_repository_state():
                    raise MockGitSecurityError("仓库状态不安全，无法执行操作")

                # 创建备份
                if auto_backup:
                    backup_path = self.create_backup(f"before_{operation_name}_{int(time.time())}")

                print(f"🚀 开始执行安全操作: {operation_name}")
                yield

                self._log_operation(operation_name, {"status": "success", "backup": backup_path})
                print(f"✅ 操作 {operation_name} 执行成功")

            except Exception as e:
                self._log_operation(operation_name, {"status": "failed", "error": str(e), "backup": backup_path})
                print(f"❌ 操作 {operation_name} 执行失败: {e}")

                # 尝试回滚
                if backup_path:
                    try:
                        self.restore_backup(Path(backup_path).name, force=True)
                        print("🔄 已自动回滚到操作前状态")
                    except Exception as rollback_error:
                        print(f"❌ 自动回滚失败: {rollback_error}")

                raise

    def safe_checkout_branch(self, branch_name: str, create_if_not_exists: bool = False) -> bool:
        """安全切换分支"""
        with self.safe_operation_context(f"checkout_branch_{branch_name}"):
            # 检查分支是否存在
            if branch_name not in self.repo.branches:
                if not create_if_not_exists:
                    raise MockGitOperationError(f"分支 {branch_name} 不存在")
                self.repo.branches[branch_name] = MockGitBranch(branch_name, self.repo.head_commit)

            # 检查当前分支状态
            if self.repo.is_dirty():
                print(f"💾 暂存当前更改（模拟）")

            # 切换分支
            self.repo.current_branch = branch_name

            # 检查切换后的状态
            if self.repo.is_detached:
                raise MockGitSecurityError("切换后处于detached HEAD状态")

            print(f"✅ 成功切换到分支: {branch_name}")
            return True

    def atomic_commit(self, message: str, files: Optional[List[str]] = None,
                     allow_empty: bool = False) -> str:
        """原子性提交操作"""
        with self.safe_operation_context("atomic_commit"):
            # 预提交检查
            if not allow_empty and not self.repo.index.staged_files:
                raise MockGitOperationError("没有要提交的更改")

            # 添加文件到暂存区
            if files:
                for file_path in files:
                    self.repo.index.add([file_path])

            # 执行提交
            try:
                commit_hash = self.repo.commit(message)

                self._log_operation("commit", {
                    "hash": commit_hash,
                    "message": message,
                    "files": files
                })

                print(f"✅ 提交成功: {commit_hash[:8]} - {message}")
                return commit_hash

            except Exception as e:
                raise MockGitOperationError(f"提交失败: {e}")

    def get_repository_status(self) -> Dict[str, Any]:
        """获取仓库状态信息"""
        try:
            status = {
                "current_branch": self.repo.current_branch,
                "current_commit": self.repo.head_commit,
                "is_detached": self.repo.is_detached,
                "is_dirty": self.repo.is_dirty(),
                "staged_files": list(self.repo.index.staged_files),
                "branch_count": len(self.repo.branches),
                "remote_count": len(self.repo.remotes),
                "last_commit_time": datetime.now().isoformat(),
                "operation_count": len(self.operation_history),
                "files": list(self.repo.files.keys())
            }

            return status

        except Exception as e:
            print(f"❌ 获取仓库状态失败: {e}")
            return {"error": str(e)}

    def cleanup_old_backups(self, keep_count: int = 10) -> int:
        """清理旧备份"""
        try:
            backups = [d for d in self.backup_dir.iterdir()
                      if d.is_dir() and d.name.startswith('backup_')]
            backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)

            deleted_count = 0
            for backup in backups[keep_count:]:
                shutil.rmtree(backup)
                deleted_count += 1
                print(f"🗑️ 删除旧备份: {backup.name}")

            self._log_operation("cleanup_backups", {"deleted_count": deleted_count})
            return deleted_count

        except Exception as e:
            print(f"❌ 清理备份失败: {e}")
            return 0


class MockGitFileOperationManager:
    """模拟Git文件操作安全管理器"""

    def __init__(self, git_manager: MockGitRepositoryManager):
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
        """安全替换文件内容"""
        file_path = Path(file_path)

        with self.git_manager.safe_operation_context(f"replace_file_{file_path.name}"):
            # 检查文件是否存在
            if not file_path.exists():
                raise MockGitOperationError(f"文件 {file_path} 不存在")

            # 计算当前文件校验和
            current_checksum = self.calculate_file_checksum(str(file_path))

            # 创建文件备份
            if create_backup:
                backup_path = file_path.with_suffix(f".backup_{int(time.time())}")
                shutil.copy2(file_path, backup_path)
                print(f"💾 创建文件备份: {backup_path}")

            try:
                # 写入新内容
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)

                # 验证文件内容
                with open(file_path, 'r', encoding='utf-8') as f:
                    if f.read() != new_content:
                        raise MockGitOperationError("文件内容验证失败")

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

                print(f"✅ 文件 {file_path} 替换成功")
                return True

            except Exception as e:
                # 恢复文件
                if create_backup and backup_path.exists():
                    shutil.copy2(backup_path, file_path)
                    backup_path.unlink()

                raise MockGitOperationError(f"文件替换失败: {e}")

    def batch_file_operations(self, operations: List[Dict[str, Any]]) -> bool:
        """批量文件操作"""
        operation_id = f"batch_ops_{int(time.time())}"

        with self.git_manager.safe_operation_context(operation_id):
            # 预检查所有文件
            for op in operations:
                file_path = Path(op["path"])
                if not file_path.exists() and op["type"] != "create":
                    raise MockGitOperationError(f"文件 {file_path} 不存在")

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
                        raise MockGitOperationError(f"不支持的操作类型: {op['type']}")

                    results.append({"path": op["path"], "success": success})

                except Exception as e:
                    results.append({"path": op["path"], "success": False, "error": str(e)})

            # 检查是否所有操作都成功
            failed_ops = [r for r in results if not r["success"]]
            if failed_ops:
                raise MockGitOperationError(f"部分操作失败: {failed_ops}")

            self.git_manager._log_operation("batch_operations", {
                "operation_count": len(operations),
                "success_count": len([r for r in results if r["success"]])
            })

            print(f"✅ 批量操作完成: {len(operations)} 个操作")
            return True


def demo_mock_git_operations():
    """演示模拟Git操作"""
    print("🚀 Git安全操作核心概念演示")
    print("="*60)

    # 创建临时目录
    temp_dir = tempfile.mkdtemp(prefix="git_demo_")
    repo_path = Path(temp_dir) / "demo_project"
    repo_path.mkdir()

    print(f"📁 创建演示仓库: {repo_path}")

    try:
        # 初始化Git管理器
        git_manager = MockGitRepositoryManager(str(repo_path))
        file_manager = MockGitFileOperationManager(git_manager)

        print("✅ Git仓库管理器初始化成功")

        # 检查仓库状态
        status = git_manager.get_repository_status()
        print(f"📊 当前分支: {status['current_branch']}")
        print(f"📊 当前提交: {status['current_commit'][:8]}")
        print(f"📊 仓库状态: {'干净' if not status['is_dirty'] else '有未提交更改'}")

        # 演示1: 备份和恢复
        print("\n" + "-"*40)
        print("演示1: 备份和恢复机制")
        print("-"*40)

        # 创建一些文件
        readme_file = repo_path / "README.md"
        readme_file.write_text("# Demo Project\n\n这是一个演示项目。")

        config_file = repo_path / "config.json"
        config_file.write_text('{"name": "demo", "version": "1.0.0"}')

        # 创建备份
        backup_path = git_manager.create_backup("initial_state")
        print(f"💾 创建备份: {Path(backup_path).name}")

        # 修改文件
        readme_file.write_text("# Demo Project\n\n这是一个演示项目。\n\n## 新增功能\n- 功能A\n- 功能B")

        # 恢复备份
        print("🔄 恢复到备份状态...")
        success = git_manager.restore_backup(Path(backup_path).name, force=True)
        print(f"恢复结果: {'成功' if success else '失败'}")

        # 验证恢复结果
        restored_content = readme_file.read_text()
        print(f"恢复后的内容: {restored_content.splitlines()[0]}")

        # 演示2: 分支操作
        print("\n" + "-"*40)
        print("演示2: 安全分支操作")
        print("-"*40)

        # 创建新分支
        branch_name = "feature/demo-feature"
        git_manager.safe_checkout_branch(branch_name, create_if_not_exists=True)
        print(f"🌿 创建并切换到分支: {branch_name}")

        # 在功能分支上创建文件
        feature_file = repo_path / "feature.py"
        feature_file.write_text("""#!/usr/bin/env python3
def demo_function():
    return "Hello from demo feature!"

if __name__ == "__main__":
    print(demo_function())
""")

        # 模拟添加到暂存区
        git_manager.repo.index.add([str(feature_file)])

        # 原子性提交
        commit_hash = git_manager.atomic_commit(
            "feat: add demo feature module\n\n- Add feature.py with demo function"
        )
        print(f"✅ 提交成功: {commit_hash[:8]}")

        # 切回主分支
        git_manager.safe_checkout_branch("master")
        print("🌿 切换回主分支")

        # 演示3: 文件操作
        print("\n" + "-"*40)
        print("演示3: 安全文件操作")
        print("-"*40)

        # 安全替换配置文件
        new_config = '''{
    "name": "demo",
    "version": "2.0.0",
    "debug": true,
    "database": {
        "host": "localhost",
        "port": 5432
    }
}'''

        success = file_manager.safe_replace_file(
            str(config_file),
            new_config,
            create_backup=True
        )
        print(f"配置文件更新: {'成功' if success else '失败'}")

        # 批量文件操作
        operations = [
            {
                "type": "create",
                "path": str(repo_path / "utils.py"),
                "content": """# 工具函数
import datetime

def get_timestamp():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def calculate_checksum(text):
    import hashlib
    return hashlib.md5(text.encode()).hexdigest()
"""
            },
            {
                "type": "create",
                "path": str(repo_path / "requirements.txt"),
                "content": """# 项目依赖
requests>=2.28.0
pyyaml>=6.0
"""
            }
        ]

        success = file_manager.batch_file_operations(operations)
        print(f"批量文件操作: {'成功' if success else '失败'}")

        # 演示4: 错误处理
        print("\n" + "-"*40)
        print("演示4: 错误处理机制")
        print("-"*40)

        try:
            # 模拟一个会失败的操作
            with git_manager.safe_operation_context("failing_operation"):
                raise Exception("模拟操作失败")
        except Exception as e:
            print(f"✅ 错误处理演示: 捕获到异常 '{e}'")
            print("✅ 自动回滚机制已触发")

        # 演示5: 备份管理
        print("\n" + "-"*40)
        print("演示5: 备份管理")
        print("-"*40)

        # 创建多个备份
        for i in range(5):
            git_manager.create_backup(f"test_backup_{i}")
            time.sleep(0.1)  # 确保时间戳不同

        print(f"📁 当前备份数量: {len(list(git_manager.backup_dir.iterdir()))}")

        # 清理备份
        deleted_count = git_manager.cleanup_old_backups(keep_count=3)
        print(f"🗑️ 清理了 {deleted_count} 个旧备份")

        # 显示最终状态
        print("\n" + "-"*40)
        print("最终仓库状态")
        print("-"*40)

        final_status = git_manager.get_repository_status()
        for key, value in final_status.items():
            if key != "error":
                print(f"📊 {key}: {value}")

        print(f"\n📋 操作历史记录数: {len(git_manager.operation_history)}")
        print("📋 最近的操作:")
        for op in git_manager.operation_history[-3:]:
            print(f"  - {op['timestamp']}: {op['operation']}")

        print("\n" + "="*60)
        print("✅ 所有演示完成！")
        print("="*60)

        print("\n🎯 核心概念总结:")
        print("1. 🛡️ 安全操作上下文: 确保操作的原子性和一致性")
        print("2. 💾 自动备份机制: 重要操作前自动创建备份")
        print("3. 🔄 自动回滚功能: 操作失败时自动恢复到安全状态")
        print("4. 🔒 并发安全控制: 使用锁机制防止并发冲突")
        print("5. 📝 完整操作日志: 记录所有操作的历史和状态")
        print("6. ✅ 状态验证机制: 操作前后验证仓库状态完整性")
        print("7. 📊 文件校验和: 确保文件操作的完整性")
        print("8. 🗂️ 批量操作支持: 原子性地执行多个文件操作")

        print("\n📚 这些概念可以直接应用到实际的GitPython项目中！")

    except Exception as e:
        print(f"❌ 演示过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # 清理演示仓库
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"\n🧹 清理演示仓库: {temp_dir}")


if __name__ == "__main__":
    demo_mock_git_operations()