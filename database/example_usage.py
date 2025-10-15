"""
Android项目构建工具 - 数据库使用示例

展示如何使用数据库模块的各种功能：
1. 基本CRUD操作
2. 构建日志管理
3. 数据迁移
4. 备份和恢复
5. 性能优化
"""

import logging
from datetime import datetime, timedelta
from typing import List

from . import (
    # 核心组件
    init_database, close_database, database_service, migration_manager, backup_manager,
    storage_optimizer, log_storage,

    # 模型
    ProjectCreate, BuildCreate, BuildLogCreate, GitOperationCreate,
    BuildStatus, GitOperationType, ProjectType,

    # 仓储
    ProjectRepository, BuildRepository, BuildLogRepository, GitOperationRepository
)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseExample:
    """数据库使用示例类"""

    def __init__(self):
        """初始化示例"""
        self.db_service = database_service
        self.projects = ProjectRepository(database_service)
        self.builds = BuildRepository(database_service)
        self.build_logs = BuildLogRepository(database_service)
        self.git_operations = GitOperationRepository(database_service)

    def setup_database(self) -> bool:
        """设置数据库"""
        try:
            logger.info("=== 初始化数据库 ===")

            # 初始化数据库连接
            init_database()

            # 执行迁移到最新版本
            success = migration_manager.migrate_up()
            if success:
                logger.info("数据库迁移完成")
            else:
                logger.error("数据库迁移失败")
                return False

            # 检查数据库健康状态
            health = database_service.health_check()
            logger.info(f"数据库健康状态: {health}")

            return True

        except Exception as e:
            logger.error(f"设置数据库失败: {e}")
            return False

    def example_project_crud(self) -> None:
        """项目CRUD操作示例"""
        logger.info("=== 项目CRUD操作示例 ===")

        try:
            with self.db_service.transaction() as session:
                # 1. 创建项目
                project_data = ProjectCreate(
                    name="android-demo-app",
                    description="Android演示应用",
                    project_type=ProjectType.ANDROID_NATIVE,
                    repository_url="https://github.com/example/android-demo-app.git",
                    local_path="/tmp/android-demo-app",
                    branch="main",
                    build_command="./gradlew assembleDebug",
                    environment_vars={
                        "ANDROID_HOME": "/opt/android-sdk",
                        "JAVA_HOME": "/opt/java-11"
                    },
                    build_timeout=1800,
                    tags=["demo", "android", "gradle"]
                )

                project = self.projects.create(session, project_data)
                logger.info(f"创建项目成功: ID={project.id}, 名称={project.name}")

                # 2. 查询项目
                found_project = self.projects.get(session, project.id)
                logger.info(f"查询项目: {found_project.name if found_project else '未找到'}")

                # 3. 更新项目
                update_data = {
                    "description": "更新后的Android演示应用",
                    "build_timeout": 2400
                }
                updated_project = self.projects.update(session, found_project, update_data)
                logger.info(f"更新项目成功: 新描述={updated_project.description}")

                # 4. 查询所有项目
                all_projects = self.projects.get_multi(session, limit=10)
                logger.info(f"总项目数: {len(all_projects)}")

                # 5. 按类型查询项目
                android_projects = self.projects.get_by_type(session, ProjectType.ANDROID_NATIVE)
                logger.info(f"Android项目数: {len(android_projects)}")

        except Exception as e:
            logger.error(f"项目CRUD操作失败: {e}")

    def example_build_management(self) -> None:
        """构建管理示例"""
        logger.info("=== 构建管理示例 ===")

        try:
            with self.db_service.transaction() as session:
                # 获取第一个项目
                project = self.projects.get_multi(session, limit=1)[0]

                # 1. 创建构建
                build_data = BuildCreate(
                    project_id=project.id,
                    build_type="debug",
                    triggered_by="manual",
                    commit_hash="abc123def456",
                    branch="feature/new-ui"
                )

                build = self.builds.create(session, build_data)
                logger.info(f"创建构建成功: ID={build.id}, 构建号={build.build_number}")

                # 2. 更新构建状态
                build_update = {
                    "status": BuildStatus.RUNNING,
                    "started_at": datetime.utcnow()
                }
                updated_build = self.builds.update(session, build, build_update)
                logger.info(f"更新构建状态: {updated_build.status}")

                # 3. 添加构建日志
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
                    }
                ]

                # 批量存储日志
                success_count, failure_count = log_storage.batch_store_logs(log_entries)
                logger.info(f"批量存储日志: 成功={success_count}, 失败={failure_count}")

                # 4. 完成构建
                build_complete = {
                    "status": BuildStatus.SUCCESS,
                    "completed_at": datetime.utcnow(),
                    "duration_seconds": 300,
                    "exit_code": 0,
                    "artifact_path": "/tmp/app-debug.apk",
                    "artifact_size": 1024000
                }
                completed_build = self.builds.update(session, updated_build, build_complete)
                logger.info(f"构建完成: 状态={completed_build.status}, 耗时={completed_build.duration_seconds}秒")

                # 5. 获取构建统计
                stats = self.builds.get_build_statistics(session, project.id)
                logger.info(f"构建统计: {stats}")

        except Exception as e:
            logger.error(f"构建管理失败: {e}")

    def example_git_operations(self) -> None:
        """Git操作示例"""
        logger.info("=== Git操作示例 ===")

        try:
            with self.db_service.transaction() as session:
                # 获取第一个项目
                project = self.projects.get_multi(session, limit=1)[0]

                # 1. 记录Git操作
                git_op_data = GitOperationCreate(
                    project_id=project.id,
                    operation_type=GitOperationType.CLONE,
                    commit_hash="abc123def456",
                    commit_message="Initial commit"
                )

                git_op = self.git_operations.create(session, git_op_data)
                logger.info(f"创建Git操作记录: ID={git_op.id}, 类型={git_op.operation_type}")

                # 2. 更新操作状态
                git_update = {
                    "status": "completed",
                    "success": True,
                    "completed_at": datetime.utcnow(),
                    "duration_seconds": 45,
                    "files_changed": 150,
                    "insertions": 2000,
                    "deletions": 50
                }
                updated_git_op = self.git_operations.update(session, git_op, git_update)
                logger.info(f"Git操作完成: 成功={updated_git_op.success}, 文件变更={updated_git_op.files_changed}")

                # 3. 获取项目Git历史
                git_history = self.git_operations.get_project_git_history(session, project.id, limit=10)
                logger.info(f"Git操作历史: {len(git_history)} 条记录")

        except Exception as e:
            logger.error(f"Git操作记录失败: {e}")

    def example_log_management(self) -> None:
        """日志管理示例"""
        logger.info("=== 日志管理示例 ===")

        try:
            with self.db_service.transaction() as session:
                # 获取第一个构建
                build = self.builds.get_multi(session, limit=1)[0]

                # 1. 获取构建日志
                logs = log_storage.get_build_logs(build.id, limit=100)
                logger.info(f"获取构建日志: {len(logs)} 条记录")

                # 2. 按级别过滤日志
                error_logs = log_storage.get_build_logs(build.id, level="ERROR", limit=50)
                logger.info(f"错误日志: {len(error_logs)} 条记录")

                # 3. 存储大型日志（自动压缩）
                large_message = "这是一个很长的日志消息..." * 1000  # 约25KB
                log_storage.store_log_entry(
                    build_id=build.id,
                    sequence_number=100,
                    level="INFO",
                    message=large_message,
                    source="test"
                )
                logger.info("存储大型日志完成（自动压缩）")

                # 4. 获取存储统计
                storage_stats = log_storage.get_storage_stats()
                logger.info(f"日志存储统计: {storage_stats}")

        except Exception as e:
            logger.error(f"日志管理失败: {e}")

    def example_backup_restore(self) -> None:
        """备份恢复示例"""
        logger.info("=== 备份恢复示例 ===")

        try:
            # 1. 创建备份
            backup_path = backup_manager.create_backup("example_backup")
            if backup_path:
                logger.info(f"创建备份成功: {backup_path}")
            else:
                logger.error("创建备份失败")
                return

            # 2. 列出所有备份
            backups = backup_manager.list_backups()
            logger.info(f"可用备份: {len(backups)} 个")
            for backup in backups[:3]:  # 只显示前3个
                logger.info(f"  - {backup['name']} ({backup['size']} bytes)")

            # 3. 模拟数据修改
            with self.db_service.transaction() as session:
                project_data = ProjectCreate(
                    name="temp-project",
                    project_type=ProjectType.ANDROID_NATIVE,
                    repository_url="https://github.com/example/temp.git",
                    local_path="/tmp/temp"
                )
                temp_project = self.projects.create(session, project_data)
                logger.info(f"创建临时项目: ID={temp_project.id}")

            # 4. 恢复备份（注意：这会覆盖当前数据）
            # restore_success = backup_manager.restore_backup(backup_path)
            # if restore_success:
            #     logger.info("恢复备份成功")
            # else:
            #     logger.error("恢复备份失败")

            logger.info("备份恢复示例完成（恢复操作已注释）")

        except Exception as e:
            logger.error(f"备份恢复失败: {e}")

    def example_performance_optimization(self) -> None:
        """性能优化示例"""
        logger.info("=== 性能优化示例 ===")

        try:
            # 1. 获取存储统计
            storage_info = storage_optimizer.get_storage_statistics()
            logger.info(f"存储统计信息:")
            logger.info(f"  数据库文件大小: {storage_info.get('database_file_size_mb', 0):.2f} MB")
            logger.info(f"  估算总大小: {storage_info.get('total_estimated_size_mb', 0):.2f} MB")

            # 显示表统计
            table_stats = storage_info.get('table_statistics', [])
            for table in table_stats[:5]:  # 只显示前5个表
                logger.info(f"  表 {table['table_name']}: {table['record_count']} 条记录, "
                          f"{table['estimated_size_mb']:.2f} MB")

            # 2. 执行数据库优化
            optimization_results = storage_optimizer.optimize_database()
            logger.info(f"优化结果: {optimization_results}")

            # 3. 显示优化建议
            recommendations = storage_info.get('optimization_recommendations', [])
            if recommendations:
                logger.info("优化建议:")
                for rec in recommendations:
                    logger.info(f"  - {rec}")
            else:
                logger.info("当前存储状态良好，无优化建议")

        except Exception as e:
            logger.error(f"性能优化失败: {e}")

    def example_advanced_queries(self) -> None:
        """高级查询示例"""
        logger.info("=== 高级查询示例 ===")

        try:
            with self.db_service.transaction() as session:
                # 1. 项目构建成功率统计
                success_rate_query = """
                    SELECT
                        p.name as project_name,
                        COUNT(b.id) as total_builds,
                        COUNT(CASE WHEN b.status = 'success' THEN 1 END) as successful_builds,
                        ROUND(
                            COUNT(CASE WHEN b.status = 'success' THEN 1 END) * 100.0 /
                            COUNT(b.id), 2
                        ) as success_rate
                    FROM projects p
                    LEFT JOIN builds b ON p.id = b.project_id
                    GROUP BY p.id, p.name
                    ORDER BY success_rate DESC
                """

                result = session.execute(text(success_rate_query))
                project_stats = [dict(row) for row in result]

                logger.info("项目构建成功率统计:")
                for stat in project_stats:
                    logger.info(f"  {stat['project_name']}: {stat['success_rate']}% "
                              f"({stat['successful_builds']}/{stat['total_builds']})")

                # 2. 最近7天的构建趋势
                trend_query = """
                    SELECT
                        DATE(started_at) as build_date,
                        COUNT(*) as builds_count,
                        COUNT(CASE WHEN status = 'success' THEN 1 END) as success_count,
                        COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_count
                    FROM builds
                    WHERE started_at >= datetime('now', '-7 days')
                    GROUP BY DATE(started_at)
                    ORDER BY build_date DESC
                """

                result = session.execute(text(trend_query))
                build_trend = [dict(row) for row in result]

                logger.info("最近7天构建趋势:")
                for day in build_trend:
                    logger.info(f"  {day['build_date']}: 总计{day['builds_count']} "
                              f"(成功{day['success_count']}, 失败{day['failed_count']})")

        except Exception as e:
            logger.error(f"高级查询失败: {e}")

    def cleanup_example(self) -> None:
        """清理示例数据"""
        logger.info("=== 清理示例数据 ===")

        try:
            with self.db_service.transaction() as session:
                # 删除临时项目
                temp_projects = self.projects.get_multi(session, **{"name": "temp-project"})
                for project in temp_projects:
                    self.projects.remove(session, project.id)
                    logger.info(f"删除临时项目: {project.name}")

            logger.info("示例数据清理完成")

        except Exception as e:
            logger.error(f"清理示例数据失败: {e}")


def main():
    """主函数 - 运行所有示例"""
    logger.info("开始数据库使用示例")

    example = DatabaseExample()

    try:
        # 1. 设置数据库
        if not example.setup_database():
            logger.error("数据库设置失败，退出示例")
            return

        # 2. 运行各种示例
        example.example_project_crud()
        example.example_build_management()
        example.example_git_operations()
        example.example_log_management()
        example.example_backup_restore()
        example.example_performance_optimization()
        example.example_advanced_queries()

        # 3. 清理示例数据
        example.cleanup_example()

        logger.info("所有示例运行完成")

    except Exception as e:
        logger.error(f"运行示例失败: {e}")

    finally:
        # 关闭数据库连接
        close_database()
        logger.info("数据库连接已关闭")


if __name__ == "__main__":
    main()