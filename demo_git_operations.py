#!/usr/bin/env python3
"""
GitPython 安全操作演示脚本

此脚本演示了如何使用本项目中的Git安全操作工具
包含实际的使用示例和最佳实践展示
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from git_utils import GitRepositoryManager, GitFileOperationManager, GitOperationError
from git_error_handling import GitErrorHandler, handle_git_errors


def create_demo_repository():
    """创建演示用的Git仓库"""
    # 创建临时目录
    temp_dir = tempfile.mkdtemp(prefix="git_demo_")
    repo_path = Path(temp_dir) / "demo_project"
    repo_path.mkdir()

    print(f"创建演示仓库: {repo_path}")

    # 初始化Git仓库
    import git
    repo = git.Repo.init(repo_path)

    # 配置用户信息
    with repo.config_writer() as config:
        config.set_value('user', 'name', 'Demo User')
        config.set_value('user', 'email', 'demo@example.com')

    # 创建初始文件
    readme_content = """# Demo Project

这是一个演示项目，用于展示GitPython安全操作的最佳实践。

## 功能特性

- 安全的分支操作
- 自动备份和恢复
- 智能错误处理
- 原子性提交
"""

    readme_file = repo_path / "README.md"
    readme_file.write_text(readme_content)

    # 初始提交
    repo.index.add([str(readme_file)])
    repo.index.commit("Initial commit: Add README")

    return str(repo_path)


def demo_basic_operations():
    """演示基本Git操作"""
    print("\n" + "="*60)
    print("演示1: 基本Git安全操作")
    print("="*60)

    # 创建演示仓库
    repo_path = create_demo_repository()
    backup_dir = Path(repo_path) / ".git_backups"

    try:
        # 初始化Git管理器
        git_manager = GitRepositoryManager(repo_path, backup_dir=str(backup_dir))

        print("✓ Git仓库管理器初始化成功")

        # 检查仓库状态
        status = git_manager.get_repository_status()
        print(f"✓ 当前分支: {status['current_branch']}")
        print(f"✓ 当前提交: {status['current_commit'][:8]}")
        print(f"✓ 仓库状态: {'干净' if not status['is_dirty'] else '有未提交更改'}")

        # 创建备份
        backup_path = git_manager.create_backup("initial_state")
        print(f"✓ 创建备份: {backup_path}")

        # 安全创建并切换分支
        branch_name = "feature/demo-feature"
        git_manager.safe_checkout_branch(branch_name, create_if_not_exists=True)
        print(f"✓ 创建并切换到分支: {branch_name}")

        # 创建新文件
        feature_file = Path(repo_path) / "feature.py"
        feature_content = '''#!/usr/bin/env python3
"""
演示功能模块
"""

def demo_function():
    """演示函数"""
    return "Hello from demo feature!"

if __name__ == "__main__":
    print(demo_function())
'''
        feature_file.write_text(feature_content)
        print(f"✓ 创建功能文件: {feature_file}")

        # 原子性提交
        git_manager.repo.index.add([str(feature_file)])
        commit_hash = git_manager.atomic_commit(
            "feat: add demo feature module\n\n- Add feature.py with demo function",
            allow_empty=False
        )
        print(f"✓ 提交成功: {commit_hash[:8]}")

        # 切回主分支
        git_manager.safe_checkout_branch("master")
        print("✓ 切换回主分支")

        # 安全合并分支
        git_manager.safe_merge_branch(branch_name, strategy="merge")
        print(f"✓ 合并分支 {branch_name} 到主分支")

    except Exception as e:
        print(f"✗ 操作失败: {e}")
    finally:
        # 清理演示仓库
        shutil.rmtree(Path(repo_path).parent, ignore_errors=True)
        print(f"✓ 清理演示仓库: {repo_path}")


def demo_file_operations():
    """演示文件操作"""
    print("\n" + "="*60)
    print("演示2: 安全文件操作")
    print("="*60)

    # 创建演示仓库
    repo_path = create_demo_repository()

    try:
        git_manager = GitRepositoryManager(repo_path)
        file_manager = GitFileOperationManager(git_manager)

        print("✓ 文件操作管理器初始化成功")

        # 创建配置文件
        config_file = Path(repo_path) / "config.yaml"
        original_config = """# 应用配置
app:
  name: "Demo App"
  version: "1.0.0"
  debug: false

database:
  host: "localhost"
  port: 5432
  name: "demo_db"
"""
        config_file.write_text(original_config)
        git_manager.repo.index.add([str(config_file)])
        git_manager.atomic_commit("config: add initial configuration")
        print("✓ 创建初始配置文件")

        # 安全替换配置文件
        updated_config = """# 应用配置
app:
  name: "Demo App"
  version: "1.1.0"
  debug: true

database:
  host: "production.db.example.com"
  port: 5432
  name: "prod_db"
  ssl: true

logging:
  level: "INFO"
  file: "app.log"
"""
        success = file_manager.safe_replace_file(
            str(config_file),
            updated_config,
            create_backup=True
        )
        print(f"✓ 配置文件更新: {'成功' if success else '失败'}")

        if success:
            # 提交配置更新
            git_manager.repo.index.add([str(config_file)])
            commit_hash = git_manager.atomic_commit(
                "config: update configuration for production\n\n- Update app version to 1.1.0\n- Enable debug mode\n- Update database connection\n- Add logging configuration",
                allow_empty=False
            )
            print(f"✓ 配置更新提交: {commit_hash[:8]}")

        # 批量文件操作
        operations = [
            {
                "type": "create",
                "path": str(Path(repo_path) / "utils.py"),
                "content": """# 工具函数模块

def format_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def calculate_checksum(data):
    import hashlib
    return hashlib.md5(data.encode()).hexdigest()
"""
            },
            {
                "type": "create",
                "path": str(Path(repo_path) / "requirements.txt"),
                "content": """# 项目依赖
requests>=2.28.0
pyyaml>=6.0
python-dateutil>=2.8.0
"""
            }
        ]

        success = file_manager.batch_file_operations(operations)
        print(f"✓ 批量文件操作: {'成功' if success else '失败'}")

        if success:
            # 提交批量更改
            git_manager.repo.index.add(["utils.py", "requirements.txt"])
            commit_hash = git_manager.atomic_commit(
                "feat: add utility module and dependencies",
                allow_empty=False
            )
            print(f"✓ 批量更改提交: {commit_hash[:8]}")

    except Exception as e:
        print(f"✗ 文件操作失败: {e}")
    finally:
        # 清理演示仓库
        shutil.rmtree(Path(repo_path).parent, ignore_errors=True)


def demo_error_handling():
    """演示错误处理"""
    print("\n" + "="*60)
    print("演示3: 错误处理和恢复")
    print("="*60)

    # 创建演示仓库
    repo_path = create_demo_repository()

    try:
        git_manager = GitRepositoryManager(repo_path)
        error_handler = GitErrorHandler(git_manager)

        print("✓ 错误处理器初始化成功")

        # 模拟网络错误
        @handle_git_errors(git_manager, "demo_network_operation")
        def simulate_network_error():
            raise ConnectionError("Network timeout during git push")

        try:
            simulate_network_error()
        except GitOperationError as e:
            print(f"✓ 网络错误处理成功: {e}")

        # 模拟文件权限错误
        @handle_git_errors(git_manager, "demo_permission_error")
        def simulate_permission_error():
            raise PermissionError("Permission denied: .git/objects")

        try:
            simulate_permission_error()
        except GitOperationError as e:
            print(f"✓ 权限错误处理成功: {e}")

        # 演示重试机制
        call_count = 0

        def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary network failure")
            return "操作最终成功"

        try:
            result = error_handler.retry_with_backoff(flaky_operation)
            print(f"✓ 重试机制演示: {result} (重试了 {call_count-1} 次)")
        except Exception as e:
            print(f"✗ 重试机制失败: {e}")

        # 显示错误统计
        stats = error_handler.get_error_statistics()
        print(f"✓ 错误统计: 总计 {stats['total_errors']} 个错误")

        if stats['total_errors'] > 0:
            print("  错误类型分布:")
            for error_type, count in stats['error_types'].items():
                print(f"    {error_type}: {count}")

    except Exception as e:
        print(f"✗ 错误处理演示失败: {e}")
    finally:
        # 清理演示仓库
        shutil.rmtree(Path(repo_path).parent, ignore_errors=True)


def demo_backup_recovery():
    """演示备份和恢复"""
    print("\n" + "="*60)
    print("演示4: 备份和恢复机制")
    print("="*60)

    # 创建演示仓库
    repo_path = create_demo_repository()

    try:
        git_manager = GitRepositoryManager(repo_path)

        print("✓ 备份恢复演示开始")

        # 创建初始状态备份
        initial_backup = git_manager.create_backup("initial_state")
        print(f"✓ 创建初始备份: {Path(initial_backup).name}")

        # 添加一些更改
        feature_file = Path(repo_path) / "feature.py"
        feature_file.write_text("# 新功能文件\nprint('Hello from feature!')")
        git_manager.repo.index.add([str(feature_file)])
        git_manager.atomic_commit("feat: add feature file")
        print("✓ 添加新功能文件")

        # 创建第二个备份
        feature_backup = git_manager.create_backup("with_feature")
        print(f"✓ 创建功能备份: {Path(feature_backup).name}")

        # 添加更多更改
        config_file = Path(repo_path) / "config.json"
        config_file.write_text('{"debug": true, "version": "2.0"}')
        git_manager.repo.index.add([str(config_file)])
        git_manager.atomic_commit("config: add debug configuration")
        print("✓ 添加配置文件")

        # 演示恢复到初始状态
        print("\n--- 恢复到初始状态 ---")
        success = git_manager.restore_backup(Path(initial_backup).name, force=True)
        print(f"✓ 恢复操作: {'成功' if success else '失败'}")

        if success:
            # 检查文件状态
            if not feature_file.exists():
                print("✓ feature.py 已被移除（恢复成功）")
            if not config_file.exists():
                print("✓ config.json 已被移除（恢复成功）")

        # 演示恢复到功能状态
        print("\n--- 恢复到功能状态 ---")
        success = git_manager.restore_backup(Path(feature_backup).name, force=True)
        print(f"✓ 恢复操作: {'成功' if success else '失败'}")

        if success:
            # 检查文件状态
            if feature_file.exists():
                print("✓ feature.py 已恢复")
            if not config_file.exists():
                print("✓ config.json 仍然不存在（符合预期）")

        # 演示备份清理
        print("\n--- 备份清理 ---")
        # 创建一些额外的备份
        for i in range(5):
            git_manager.create_backup(f"extra_backup_{i}")

        deleted_count = git_manager.cleanup_old_backups(keep_count=3)
        print(f"✓ 清理了 {deleted_count} 个旧备份，保留3个最新备份")

    except Exception as e:
        print(f"✗ 备份恢复演示失败: {e}")
    finally:
        # 清理演示仓库
        shutil.rmtree(Path(repo_path).parent, ignore_errors=True)


def main():
    """主演示函数"""
    print("GitPython 安全操作最佳实践演示")
    print("="*60)
    print("本演示将展示以下功能:")
    print("1. 基本Git安全操作")
    print("2. 安全文件操作")
    print("3. 错误处理和恢复")
    print("4. 备份和恢复机制")
    print("5. 原子性操作保证")
    print("6. 并发安全处理")

    try:
        # 执行各个演示
        demo_basic_operations()
        demo_file_operations()
        demo_error_handling()
        demo_backup_recovery()

        print("\n" + "="*60)
        print("✓ 所有演示完成！")
        print("="*60)

        print("\n主要学习要点:")
        print("• 使用 safe_operation_context 确保操作安全")
        print("• 重要操作前总是创建备份")
        print("• 使用 atomic_commit 确保提交的原子性")
        print("• 利用错误处理器的自动恢复功能")
        print("• 定期清理备份以节省存储空间")
        print("• 所有操作都有完整的日志记录")

    except KeyboardInterrupt:
        print("\n演示被用户中断")
    except Exception as e:
        print(f"\n演示过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()