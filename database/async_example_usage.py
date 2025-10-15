"""
Android项目构建工具 - 异步数据库使用示例

展示如何在项目中使用异步数据库功能：
1. 基本CRUD操作
2. 复杂查询
3. 事务管理
4. 批量操作
5. 性能监控
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from .async_database import (
    init_async_database, close_async_database,
    async_database_service
)
from .models import (
    ProjectCreate, BuildCreate, BuildLogCreate, GitOperationCreate,
    BuildStatus, GitOperationType, ProjectType
)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AsyncDatabaseExample:
    """异步数据库使用示例"""

    def __init__(self):
        self.db_service = async_database_service

    async def setup(self):
        """初始化数据库"""
        await init_async_database()
        logger.info("异步数据库初始化完成")

    async def cleanup(self):
        """清理资源"""
        await close_async_database()
        logger.info("数据库连接已关闭")

    async def example_basic_crud(self):
        """基本CRUD操作示例"""
        logger.info("=== 基本CRUD操作示例 ===")

        try:
            # 1. 创建项目
            project_data = ProjectCreate(
                name="async-demo-project",
                description="异步演示项目",
                project_type=ProjectType.ANDROID_NATIVE,
                repository_url="https://github.com/example/async-demo.git",
                local_path="/tmp/async-demo",
                branch="main",
                build_command="./gradlew assembleDebug",
                environment_vars={
                    "ANDROID_HOME": "/opt/android-sdk",
                    "JAVA_HOME": "/opt/java-11"
                },
                build_timeout=1800,
                tags=["demo", "async", "android"]
            )

            project = await self.db_service.projects.create(project_data)
            logger.info(f"创建项目成功: ID={project.id}, 名称={project.name}")

            # 2. 查询项目
            found_project = await self.db_service.projects.get(project.id)
            logger.info(f"查询项目: {found_project.name if found_project else '未找到'}")

            # 3. 更新项目
            update_data = {
                "description": "更新后的异步演示项目",
                "build_timeout": 2400
            }
            updated_project = await self.db_service.projects.update(found_project, update_data)
            logger.info(f"更新项目成功: 新描述={updated_project.description}")

            # 4. 查询所有项目
            all_projects = await self.db_service.projects.get_multi(limit=10)
            logger.info(f"总项目数: {len(all_projects)}")

            # 5. 搜索项目
            search_results = await self.db_service.projects.search_projects("async")
            logger.info(f"搜索'async'结果: {len(search_results)} 个项目")

            # 6. 删除项目
            await self.db_service.projects.delete(project.id)
            logger.info("项目删除成功")

        except Exception as e:
            logger.error(f"CRUD操作失败: {e}")

    async def example_build_management(self):
        """构建管理示例"""
        logger.info("=== 构建管理示例 ===")

        try:
            # 1. 创建项目
            project_data = ProjectCreate(
                name="build-demo-project",
                project_type=ProjectType.ANDROID_NATIVE,
                repository_url="https://github.com/example/build-demo.git",
                local_path="/tmp/build-demo"
            )
            project = await self.db_service.projects.create(project_data)

            # 2. 创建构建
            build_number = await self.db_service.builds.get_next_build_number(project.id)
            build_data = BuildCreate(
                project_id=project.id,
                build_type="debug",
                triggered_by="manual",
                commit_hash="abc123def456",
                branch="feature/async-demo"
            )
            build = await self.db_service.builds.create(build_data)
            logger.info(f"创建构建成功: ID={build.id}, 构建号={build_number}")

            # 3. 更新构建状态
            await self.db_service.builds.update_build_status(
                build.id,
                BuildStatus.RUNNING,
                started_at=datetime.utcnow()
            )
            logger.info(f"构建状态更新为: {BuildStatus.RUNNING}")

            # 4. 添加构建日志
            log_entries = [
                {
                    "build_id": build.id,
                    "sequence_number": 1,
                    "level": "INFO",
                    "message": "开始构建...",
                    "source": "gradle"
                },
                {
                    "build_id": build.id,
                    "sequence_number": 2,
                    "level": "INFO",
                    "message": "编译源代码",
                    "source": "gradle"
                },
                {
                    "build_id": build.id,
                    "sequence_number": 3,
                    "level": "WARN",
                    "message": "发现已弃用的API使用",
                    "source": "compiler"
                },
                {
                    "build_id": build.id,
                    "sequence_number": 4,
                    "level": "INFO",
                    "message": "构建完成",
                    "source": "gradle"
                }
            ]

            success = await self.db_service.build_logs.batch_create_logs(log_entries)
            logger.info(f"批量创建日志: {'成功' if success else '失败'}")

            # 5. 完成构建
            await self.db_service.builds.update_build_status(
                build.id,
                BuildStatus.SUCCESS,
                completed_at=datetime.utcnow(),
                duration_seconds=120,
                exit_code=0,
                artifact_path="/tmp/app-debug.apk",
                artifact_size=2048000
            )
            logger.info(f"构建完成: 状态={BuildStatus.SUCCESS}")

            # 6. 获取构建统计
            stats = await self.db_service.builds.get_build_statistics(project.id)
            logger.info(f"构建统计: {stats}")

            # 7. 获取项目构建历史
            build_history = await self.db_service.builds.get_by_project(project.id, limit=10)
            logger.info(f"构建历史: {len(build_history)} 个构建")

        except Exception as e:
            logger.error(f"构建管理失败: {e}")

    async def example_git_operations(self):
        """Git操作示例"""
        logger.info("=== Git操作示例 ===")

        try:
            # 1. 创建项目
            project_data = ProjectCreate(
                name="git-demo-project",
                project_type=ProjectType.FLUTTER,
                repository_url="https://github.com/example/git-demo.git",
                local_path="/tmp/git-demo"
            )
            project = await self.db_service.projects.create(project_data)

            # 2. 记录Git操作
            git_op_data = GitOperationCreate(
                project_id=project.id,
                operation_type=GitOperationType.CLONE,
                commit_hash="def789abc012",
                commit_message="Initial commit"
            )
            git_op = await self.db_service.git_operations.create(git_op_data)
            logger.info(f"创建Git操作记录: ID={git_op.id}, 类型={git_op.operation_type}")

            # 3. 更新操作状态
            await self.db_service.git_operations.update(git_op, {
                "status": "completed",
                "success": True,
                "completed_at": datetime.utcnow(),
                "duration_seconds": 45,
                "files_changed": 150,
                "insertions": 2000,
                "deletions": 50
            })
            logger.info(f"Git操作完成: 成功={git_op.success}")

            # 4. 记录更多Git操作
            operations = [
                {
                    "project_id": project.id,
                    "operation_type": GitOperationType.PULL,
                    "commit_hash": "abc456def789",
                    "commit_message": "Update dependencies"
                },
                {
                    "project_id": project.id,
                    "operation_type": GitOperationType.BRANCH,
                    "commit_hash": "ghi789jkl012",
                    "commit_message": "Create feature branch",
                    "from_branch": "main",
                    "to_branch": "feature/new-ui"
                }
            ]

            for op_data in operations:
                op = await self.db_service.git_operations.create(GitOperationCreate(**op_data))
                await self.db_service.git_operations.update(op, {
                    "status": "completed",
                    "success": True,
                    "completed_at": datetime.utcnow(),
                    "duration_seconds": random.randint(10, 60)
                })

            # 5. 获取项目Git历史
            git_history = await self.db_service.git_operations.get_project_git_history(project.id, limit=10)
            logger.info(f"Git操作历史: {len(git_history)} 条记录")

        except Exception as e:
            logger.error(f"Git操作记录失败: {e}")

    async def example_advanced_queries(self):
        """高级查询示例"""
        logger.info("=== 高级查询示例 ===")

        try:
            # 1. 获取所有活跃项目的构建统计
            projects_with_stats = await self.db_service.projects.get_projects_with_build_stats()
            logger.info(f"项目构建统计: {len(projects_with_stats)} 个项目")

            for project_stat in projects_with_stats[:3]:  # 只显示前3个
                logger.info(f"  项目: {project_stat['name']}, "
                          f"构建数: {project_stat['total_builds']}, "
                          f"成功率: {project_stat['successful_builds']}")

            # 2. 获取运行中的构建
            running_builds = await self.db_service.builds.get_running_builds()
            logger.info(f"运行中的构建: {len(running_builds)} 个")

            # 3. 获取最近的Git操作
            recent_operations = await self.db_service.git_operations.get_recent_operations(hours=24)
            logger.info(f"最近24小时的Git操作: {len(recent_operations)} 个")

            # 4. 获取错误日志
            async with self.db_service.transaction() as session:
                from sqlalchemy import text
                result = await session.execute(text("""
                    SELECT bl.*, b.project_id, p.name as project_name
                    FROM build_logs bl
                    JOIN builds b ON bl.build_id = b.id
                    JOIN projects p ON b.project_id = p.id
                    WHERE bl.level = 'ERROR'
                    AND bl.timestamp >= datetime('now', '-7 days')
                    ORDER BY bl.timestamp DESC
                    LIMIT 10
                """))
                error_logs = [dict(row) for row in result]

            logger.info(f"最近7天的错误日志: {len(error_logs)} 条")
            for log in error_logs[:3]:  # 只显示前3条
                logger.info(f"  项目: {log['project_name']}, 消息: {log['message'][:50]}...")

        except Exception as e:
            logger.error(f"高级查询失败: {e}")

    async def example_transaction_management(self):
        """事务管理示例"""
        logger.info("=== 事务管理示例 ===")

        try:
            # 1. 成功的事务
            async with self.db_service.transaction() as session:
                # 创建项目
                project_data = ProjectCreate(
                    name="transaction-project",
                    project_type=ProjectType.REACT_NATIVE,
                    repository_url="https://github.com/example/transaction.git",
                    local_path="/tmp/transaction"
                )
                project = await self.db_service.projects.create(project_data)

                # 创建构建
                build_data = BuildCreate(
                    project_id=project.id,
                    build_type="release",
                    triggered_by="transaction_demo"
                )
                build = await self.db_service.builds.create(build_data)

                logger.info(f"事务成功创建: 项目 {project.id}, 构建 {build.id}")

            # 2. 带重试的操作
            async def create_project_with_retry():
                return await self.db_service.projects.create(
                    ProjectCreate(
                        name="retry-project",
                        project_type=ProjectType.IONIC,
                        repository_url="https://github.com/example/retry.git",
                        local_path="/tmp/retry"
                    )
                )

            project = await self.db_service.execute_with_retry(
                create_project_with_retry,
                max_retries=3
            )
            logger.info(f"带重试的操作成功: 项目 {project.id}")

            # 3. 失败事务演示（注释掉以避免实际错误）
            """
            try:
                async with self.db_service.transaction() as session:
                    project = await self.db_service.projects.create(
                        ProjectCreate(
                            name="fail-project",
                            project_type=ProjectType.CORDOVA,
                            repository_url="https://github.com/example/fail.git",
                            local_path="/tmp/fail"
                        )
                    )
                    # 故意引发错误
                    raise ValueError("模拟事务失败")
            except ValueError as e:
                logger.info(f"事务按预期失败并回滚: {e}")
            """

        except Exception as e:
            logger.error(f"事务管理失败: {e}")

    async def example_performance_monitoring(self):
        """性能监控示例"""
        logger.info("=== 性能监控示例 ===")

        try:
            # 1. 数据库健康检查
            health = await self.db_service.health_check()
            logger.info(f"数据库健康状态: {health['status']}")
            logger.info(f"表数量: {len(health['tables'])}")
            logger.info(f"记录统计: {health['record_counts']}")

            # 2. 数据库统计信息
            stats = await self.db_service.get_database_statistics()
            logger.info(f"总项目数: {stats['total_records']['projects']}")
            logger.info(f"总构建数: {stats['total_records']['builds']}")
            logger.info(f"总日志数: {stats['total_records']['build_logs']}")

            # 3. 最近活动统计
            recent = stats['recent_activity']
            logger.info(f"最近7天构建数: {recent['builds_last_7_days']}")
            logger.info(f"最近7天日志数: {recent['logs_last_7_days']}")

            # 4. 构建状态分布
            if stats['build_statistics']:
                logger.info("构建状态分布:")
                for stat in stats['build_statistics']:
                    logger.info(f"  {stat['status']}: {stat['count']} 个构建, "
                              f"平均耗时: {stat['avg_duration']:.1f}s" if stat['avg_duration'] else "N/A")

        except Exception as e:
            logger.error(f"性能监控失败: {e}")

    async def example_cleanup_operations(self):
        """清理操作示例"""
        logger.info("=== 清理操作示例 ===")

        try:
            # 1. 清理旧数据
            cleanup_stats = await self.db_service.cleanup_old_data(days=30)
            logger.info(f"数据清理结果: {cleanup_stats}")

            # 2. 清理示例数据
            demo_projects = await self.db_service.projects.get_multi(limit=100)
            deleted_count = 0

            for project in demo_projects:
                if any(keyword in project.name.lower() for keyword in [
                    "demo-project", "build-demo-project", "git-demo-project",
                    "transaction-project", "retry-project"
                ]):
                    await self.db_service.projects.delete(project.id)
                    deleted_count += 1

            logger.info(f"清理完成，删除了 {deleted_count} 个示例项目")

        except Exception as e:
            logger.error(f"清理操作失败: {e}")

    async def run_all_examples(self):
        """运行所有示例"""
        logger.info("开始运行异步数据库示例")

        try:
            await self.setup()

            # 运行各种示例
            await self.example_basic_crud()
            await self.example_build_management()
            await self.example_git_operations()
            await self.example_advanced_queries()
            await self.example_transaction_management()
            await self.example_performance_monitoring()

            # 清理
            await self.example_cleanup_operations()

            logger.info("所有示例运行完成")

        except Exception as e:
            logger.error(f"示例运行失败: {e}")

        finally:
            await self.cleanup()


async def main():
    """主函数"""
    example = AsyncDatabaseExample()
    await example.run_all_examples()


if __name__ == "__main__":
    asyncio.run(main())