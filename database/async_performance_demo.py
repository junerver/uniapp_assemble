"""
Android项目构建工具 - 异步数据库性能演示

展示：
1. 异步数据库操作性能
2. 并发访问控制
3. 事务管理
4. 连接池优化
5. 性能基准测试
"""

import asyncio
import logging
import random
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any
import json

from .async_database import (
    AsyncDatabaseManager, AsyncDatabaseService,
    init_async_database, close_async_database,
    async_database_service
)
from .models import (
    ProjectCreate, BuildCreate, BuildLogCreate, GitOperationCreate,
    BuildStatus, GitOperationType, ProjectType
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AsyncPerformanceDemo:
    """异步数据库性能演示类"""

    def __init__(self):
        self.db_service = async_database_service

    async def setup_demo(self) -> bool:
        """设置演示环境"""
        try:
            logger.info("=== 初始化异步数据库演示环境 ===")

            # 初始化数据库
            await init_async_database()

            # 检查数据库健康状态
            health = await self.db_service.health_check()
            logger.info(f"数据库健康状态: {health['status']}")
            logger.info(f"可用表: {health['tables']}")

            return True

        except Exception as e:
            logger.error(f"设置演示环境失败: {e}")
            return False

    async def create_test_data(self, project_count: int = 10, builds_per_project: int = 20) -> bool:
        """创建测试数据"""
        logger.info(f"=== 创建测试数据: {project_count} 个项目，每个项目 {builds_per_project} 个构建 ===")

        try:
            start_time = time.time()

            # 创建项目
            projects = []
            for i in range(project_count):
                project_data = ProjectCreate(
                    name=f"async-test-project-{i+1}",
                    description=f"异步测试项目 {i+1}",
                    project_type=random.choice(list(ProjectType)),
                    repository_url=f"https://github.com/example/async-test-{i+1}.git",
                    local_path=f"/tmp/async-test-{i+1}",
                    branch="main",
                    build_command=f"./gradlew assemble{'Debug' if i % 2 == 0 else 'Release'}",
                    environment_vars={
                        "ANDROID_HOME": "/opt/android-sdk",
                        "JAVA_HOME": "/opt/java-11"
                    },
                    build_timeout=random.randint(1200, 3600),
                    tags=[f"async-test", f"type-{i % 3}"]
                )

                project = await self.db_service.projects.create(project_data)
                projects.append(project)
                logger.debug(f"创建项目: {project.name}")

            # 为每个项目创建构建
            for project in projects:
                for j in range(builds_per_project):
                    # 获取下一个构建编号
                    build_number = await self.db_service.builds.get_next_build_number(project.id)

                    build_data = BuildCreate(
                        project_id=project.id,
                        build_type="debug" if j % 3 == 0 else "release",
                        triggered_by=random.choice(["manual", "webhook", "scheduler"]),
                        commit_hash=f"{''.join(random.choices('0123456789abcdef', k=40))}",
                        branch=random.choice(["main", "develop", f"feature-{j}"])
                    )

                    build = await self.db_service.builds.create(build_data)

                    # 随机设置构建状态
                    if j < builds_per_project - 1:
                        status = random.choice(["success", "failed", "cancelled"])
                        await self.db_service.builds.update_build_status(
                            build.id,
                            status,
                            started_at=datetime.utcnow() - timedelta(minutes=random.randint(1, 120)),
                            completed_at=datetime.utcnow() - timedelta(minutes=random.randint(1, 60)),
                            duration_seconds=random.randint(60, 3600),
                            exit_code=0 if status == "success" else 1,
                            artifact_path=f"/tmp/build-{build.id}.apk",
                            artifact_size=random.randint(1000000, 50000000),
                            memory_usage_mb=random.randint(100, 2000),
                            cpu_usage_percent=random.randint(10, 90)
                        )
                    else:
                        # 最后一个设置为运行中
                        await self.db_service.builds.update_build_status(
                            build.id,
                            "running",
                            started_at=datetime.utcnow() - timedelta(minutes=random.randint(1, 30))
                        )

                    # 为部分构建创建日志
                    if random.random() < 0.7:  # 70% 的构建有日志
                        log_count = random.randint(10, 100)
                        logs = []
                        for k in range(log_count):
                            log_data = {
                                "build_id": build.id,
                                "sequence_number": k + 1,
                                "level": random.choice(["DEBUG", "INFO", "WARN", "ERROR"]),
                                "message": f"构建日志消息 {k+1} - {random.choice(['编译', '链接', '打包', '测试'])}操作",
                                "source": random.choice(["gradle", "compiler", "test-runner", "packager"])
                            }
                            logs.append(log_data)

                        await self.db_service.build_logs.batch_create_logs(logs)

            duration = time.time() - start_time
            logger.info(f"测试数据创建完成，耗时: {duration:.2f}秒")
            return True

        except Exception as e:
            logger.error(f"创建测试数据失败: {e}")
            return False

    async def benchmark_concurrent_reads(self, concurrency: int = 100, operations: int = 1000):
        """并发读取性能基准测试"""
        logger.info(f"=== 并发读取测试: {concurrency} 并发, {operations} 操作 ===")

        start_time = time.time()

        async def read_operation(operation_id: int):
            """单个读取操作"""
            try:
                # 随机选择读取操作
                operation_type = random.choice([
                    "get_project",
                    "get_builds",
                    "get_logs",
                    "get_stats"
                ])

                if operation_type == "get_project":
                    project = await self.db_service.projects.get(random.randint(1, 50))
                    return {"type": "project", "success": project is not None}

                elif operation_type == "get_builds":
                    builds = await self.db_service.builds.get_multi(limit=20)
                    return {"type": "builds", "success": True, "count": len(builds)}

                elif operation_type == "get_logs":
                    logs = await self.db_service.build_logs.get_multi(limit=50)
                    return {"type": "logs", "success": True, "count": len(logs)}

                else:  # get_stats
                    stats = await self.db_service.builds.get_build_statistics()
                    return {"type": "stats", "success": True}

            except Exception as e:
                return {"type": operation_type, "success": False, "error": str(e)}

        # 创建并发任务
        semaphore = asyncio.Semaphore(concurrency)

        async def limited_read(operation_id: int):
            async with semaphore:
                return await read_operation(operation_id)

        tasks = [limited_read(i) for i in range(operations)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        duration = time.time() - start_time

        # 分析结果
        successful_results = [r for r in results if isinstance(r, dict) and r.get("success")]
        failed_results = [r for r in results if isinstance(r, dict) and not r.get("success")]
        exceptions = [r for r in results if isinstance(r, Exception)]

        # 统计操作类型
        operation_counts = {}
        for result in successful_results:
            op_type = result["type"]
            operation_counts[op_type] = operation_counts.get(op_type, 0) + 1

        logger.info(f"并发读取测试结果:")
        logger.info(f"  测试时长: {duration:.2f}秒")
        logger.info(f"  总操作数: {operations}")
        logger.info(f"  成功操作: {len(successful_results)}")
        logger.info(f"  失败操作: {len(failed_results)}")
        logger.info(f"  异常数量: {len(exceptions)}")
        logger.info(f"  吞吐量: {len(successful_results) / duration:.2f} ops/s")
        logger.info(f"  操作类型分布: {operation_counts}")

        return {
            "duration": duration,
            "total_operations": operations,
            "successful": len(successful_results),
            "failed": len(failed_results),
            "exceptions": len(exceptions),
            "throughput": len(successful_results) / duration,
            "operation_counts": operation_counts
        }

    async def benchmark_concurrent_writes(self, concurrency: int = 50, operations: int = 500):
        """并发写入性能基准测试"""
        logger.info(f"=== 并发写入测试: {concurrency} 并发, {operations} 操作 ===")

        start_time = time.time()

        async def write_operation(operation_id: int):
            """单个写入操作"""
            try:
                operation_type = random.choice([
                    "create_project",
                    "create_build",
                    "create_log",
                    "update_status"
                ])

                if operation_type == "create_project":
                    project_data = ProjectCreate(
                        name=f"bench-project-{operation_id}",
                        project_type=ProjectType.ANDROID_NATIVE,
                        repository_url=f"https://github.com/bench/{operation_id}.git",
                        local_path=f"/tmp/bench-{operation_id}"
                    )
                    project = await self.db_service.projects.create(project_data)
                    return {"type": "project", "success": True, "id": project.id}

                elif operation_type == "create_build":
                    # 先确保有项目
                    projects = await self.db_service.projects.get_multi(limit=10)
                    if projects:
                        project = random.choice(projects)
                        build_number = await self.db_service.builds.get_next_build_number(project.id)
                        build_data = BuildCreate(
                            project_id=project.id,
                            build_type="debug",
                            triggered_by="benchmark"
                        )
                        build = await self.db_service.builds.create(build_data)
                        return {"type": "build", "success": True, "id": build.id}
                    else:
                        return {"type": "build", "success": False, "error": "no projects"}

                elif operation_type == "create_log":
                    builds = await self.db_service.builds.get_multi(limit=10)
                    if builds:
                        build = random.choice(builds)
                        log_data = {
                            "build_id": build.id,
                            "sequence_number": 1,
                            "level": "INFO",
                            "message": f"Benchmark log {operation_id}",
                            "source": "benchmark"
                        }
                        success = await self.db_service.build_logs.batch_create_logs([log_data])
                        return {"type": "log", "success": success}
                    else:
                        return {"type": "log", "success": False, "error": "no builds"}

                else:  # update_status
                    builds = await self.db_service.builds.get_by_status("running", limit=10)
                    if builds:
                        build = random.choice(builds)
                        success = await self.db_service.builds.update_build_status(
                            build.id,
                            random.choice(["success", "failed"])
                        )
                        return {"type": "update", "success": success}
                    else:
                        return {"type": "update", "success": False, "error": "no running builds"}

            except Exception as e:
                return {"type": operation_type, "success": False, "error": str(e)}

        # 创建并发任务
        semaphore = asyncio.Semaphore(concurrency)

        async def limited_write(operation_id: int):
            async with semaphore:
                return await write_operation(operation_id)

        tasks = [limited_write(i) for i in range(operations)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        duration = time.time() - start_time

        # 分析结果
        successful_results = [r for r in results if isinstance(r, dict) and r.get("success")]
        failed_results = [r for r in results if isinstance(r, dict) and not r.get("success")]
        exceptions = [r for r in results if isinstance(r, Exception)]

        # 统计操作类型
        operation_counts = {}
        for result in successful_results:
            op_type = result["type"]
            operation_counts[op_type] = operation_counts.get(op_type, 0) + 1

        logger.info(f"并发写入测试结果:")
        logger.info(f"  测试时长: {duration:.2f}秒")
        logger.info(f"  总操作数: {operations}")
        logger.info(f"  成功操作: {len(successful_results)}")
        logger.info(f"  失败操作: {len(failed_results)}")
        logger.info(f"  异常数量: {len(exceptions)}")
        logger.info(f"  吞吐量: {len(successful_results) / duration:.2f} ops/s")
        logger.info(f"  操作类型分布: {operation_counts}")

        return {
            "duration": duration,
            "total_operations": operations,
            "successful": len(successful_results),
            "failed": len(failed_results),
            "exceptions": len(exceptions),
            "throughput": len(successful_results) / duration,
            "operation_counts": operation_counts
        }

    async def benchmark_mixed_workload(self, duration_seconds: int = 60, max_concurrency: int = 50):
        """混合工作负载基准测试"""
        logger.info(f"=== 混合工作负载测试: 持续 {duration_seconds} 秒，最大并发 {max_concurrency} ===")

        end_time = time.time() + duration_seconds
        operation_count = 0
        error_count = 0
        operation_times = []

        semaphore = asyncio.Semaphore(max_concurrency)

        async def mixed_operation():
            nonlocal operation_count, error_count
            operation_id = operation_count
            start_time = time.time()

            try:
                # 随机选择操作类型
                operation_weights = [
                    ("read_project", 0.2),
                    ("read_builds", 0.2),
                    ("read_stats", 0.1),
                    ("create_log", 0.3),
                    ("update_status", 0.2)
                ]

                operation_type = random.choices(
                    [op[0] for op in operation_weights],
                    weights=[op[1] for op in operation_weights]
                )[0]

                if operation_type == "read_project":
                    project = await self.db_service.projects.get(random.randint(1, 100))

                elif operation_type == "read_builds":
                    builds = await self.db_service.builds.get_multi(limit=20)

                elif operation_type == "read_stats":
                    stats = await self.db_service.builds.get_build_statistics()

                elif operation_type == "create_log":
                    builds = await self.db_service.builds.get_multi(limit=10)
                    if builds:
                        build = random.choice(builds)
                        logs = [{
                            "build_id": build.id,
                            "sequence_number": random.randint(1, 1000),
                            "level": random.choice(["INFO", "DEBUG", "WARN"]),
                            "message": f"Mixed workload log {operation_id}",
                            "source": "mixed_test"
                        }]
                        await self.db_service.build_logs.batch_create_logs(logs)

                else:  # update_status
                    running_builds = await self.db_service.builds.get_by_status("running", limit=5)
                    if running_builds:
                        build = random.choice(running_builds)
                        new_status = random.choice(["success", "failed"])
                        await self.db_service.builds.update_build_status(
                            build.id,
                            new_status,
                            completed_at=datetime.utcnow(),
                            duration_seconds=random.randint(60, 600)
                        )

                operation_count += 1
                duration = time.time() - start_time
                operation_times.append(duration)

            except Exception as e:
                error_count += 1
                logger.debug(f"操作失败: {e}")

        # 持续执行混合操作
        tasks = []
        while time.time() < end_time:
            if len(tasks) < max_concurrency:
                task = asyncio.create_task(mixed_operation())
                tasks.append(task)

            # 清理已完成的任务
            tasks = [t for t in tasks if not t.done()]

            # 短暂休息
            await asyncio.sleep(0.01)

        # 等待剩余任务完成
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # 计算统计信息
        total_duration = time.time() - (end_time - duration_seconds)
        throughput = operation_count / total_duration
        error_rate = (error_count / (operation_count + error_count)) * 100 if (operation_count + error_count) > 0 else 0

        avg_response_time = sum(operation_times) / len(operation_times) if operation_times else 0
        max_response_time = max(operation_times) if operation_times else 0
        min_response_time = min(operation_times) if operation_times else 0

        logger.info(f"混合工作负载测试结果:")
        logger.info(f"  测试时长: {total_duration:.2f}s")
        logger.info(f"  总操作数: {operation_count}")
        logger.info(f"  错误数: {error_count}")
        logger.info(f"  吞吐量: {throughput:.2f} ops/s")
        logger.info(f"  错误率: {error_rate:.2f}%")
        logger.info(f"  平均响应时间: {avg_response_time:.3f}s")
        logger.info(f"  最大响应时间: {max_response_time:.3f}s")
        logger.info(f"  最小响应时间: {min_response_time:.3f}s")

        return {
            "duration": total_duration,
            "total_operations": operation_count,
            "errors": error_count,
            "throughput": throughput,
            "error_rate": error_rate,
            "avg_response_time": avg_response_time,
            "max_response_time": max_response_time,
            "min_response_time": min_response_time
        }

    async def demonstrate_transaction_management(self):
        """演示事务管理"""
        logger.info("=== 事务管理演示 ===")

        try:
            # 成功的事务
            async with self.db_service.transaction() as session:
                # 创建项目
                project_data = ProjectCreate(
                    name="transaction-test-project",
                    project_type=ProjectType.ANDROID_NATIVE,
                    repository_url="https://github.com/test/transaction.git",
                    local_path="/tmp/transaction-test"
                )
                project = await self.db_service.projects.create(project_data)

                # 创建构建
                build_data = BuildCreate(
                    project_id=project.id,
                    build_type="debug",
                    triggered_by="transaction_test"
                )
                build = await self.db_service.builds.create(build_data)

                # 创建日志
                logs = [{
                    "build_id": build.id,
                    "sequence_number": 1,
                    "level": "INFO",
                    "message": "Transaction test log",
                    "source": "transaction_test"
                }]
                await self.db_service.build_logs.batch_create_logs(logs)

                logger.info(f"事务成功创建: 项目 {project.id}, 构建 {build.id}")

            # 失败的事务（演示回滚）
            try:
                async with self.db_service.transaction() as session:
                    # 创建一个项目
                    project_data = ProjectCreate(
                        name="rollback-test-project",
                        project_type=ProjectType.ANDROID_NATIVE,
                        repository_url="https://github.com/test/rollback.git",
                        local_path="/tmp/rollback-test"
                    )
                    project = await self.db_service.projects.create(project_data)

                    # 故意引发错误
                    raise ValueError("模拟事务错误")

            except ValueError as e:
                logger.info(f"事务按预期回滚: {e}")

                # 验证回滚是否成功
                exists = await self.db_service.projects.exists(name="rollback-test-project")
                logger.info(f"回滚验证 - 项目是否存在: {exists}")

            # 带重试的事务
            await self.db_service.execute_with_retry(
                lambda session: self.db_service.projects.create(
                    ProjectCreate(
                        name="retry-test-project",
                        project_type=ProjectType.REACT_NATIVE,
                        repository_url="https://github.com/test/retry.git",
                        local_path="/tmp/retry-test"
                    )
                ),
                max_retries=3
            )
            logger.info("带重试的事务执行成功")

        except Exception as e:
            logger.error(f"事务管理演示失败: {e}")

    async def demonstrate_batch_operations(self):
        """演示批量操作"""
        logger.info("=== 批量操作演示 ===")

        try:
            # 批量创建日志
            start_time = time.time()
            batch_size = 1000

            # 获取一个构建ID
            builds = await self.db_service.builds.get_multi(limit=1)
            if builds:
                build_id = builds[0].id

                # 创建大量日志
                logs = []
                for i in range(batch_size):
                    logs.append({
                        "build_id": build_id,
                        "sequence_number": i + 1,
                        "level": random.choice(["DEBUG", "INFO", "WARN", "ERROR"]),
                        "message": f"批量测试日志 {i+1}",
                        "source": "batch_test"
                    })

                success = await self.db_service.build_logs.batch_create_logs(logs)
                duration = time.time() - start_time

                logger.info(f"批量创建 {batch_size} 条日志: {'成功' if success else '失败'}")
                logger.info(f"批量操作耗时: {duration:.3f}秒")
                logger.info(f"平均每条日志耗时: {duration/batch_size*1000:.3f}毫秒")

                # 验证批量创建结果
                created_logs = await self.db_service.build_logs.get_build_logs(build_id, limit=batch_size + 100)
                logger.info(f"验证结果: 实际创建日志数量 {len(created_logs)}")

        except Exception as e:
            logger.error(f"批量操作演示失败: {e}")

    async def demonstrate_performance_monitoring(self):
        """演示性能监控"""
        logger.info("=== 性能监控演示 ===")

        try:
            # 获取数据库健康状态
            health = await self.db_service.health_check()
            logger.info(f"数据库健康状态: {health['status']}")
            logger.info(f"数据库性能指标: {health.get('performance_metrics', {})}")

            # 获取数据库统计信息
            stats = await self.db_service.get_database_statistics()
            logger.info(f"数据库统计信息: {json.dumps(stats, indent=2, ensure_ascii=False)}")

        except Exception as e:
            logger.error(f"性能监控演示失败: {e}")

    async def cleanup_demo_data(self):
        """清理演示数据"""
        logger.info("=== 清理演示数据 ===")

        try:
            # 删除测试项目
            test_projects = await self.db_service.projects.get_multi(limit=1000)
            deleted_count = 0

            for project in test_projects:
                if any(keyword in project.name.lower() for keyword in [
                    "async-test-project", "bench-project", "transaction-test",
                    "retry-test", "rollback-test"
                ]):
                    await self.db_service.projects.delete(project.id)
                    deleted_count += 1

            logger.info(f"清理完成，删除了 {deleted_count} 个测试项目")

        except Exception as e:
            logger.error(f"清理演示数据失败: {e}")

    async def run_full_demo(self):
        """运行完整演示"""
        logger.info("开始异步数据库性能演示")

        try:
            # 1. 设置环境
            if not await self.setup_demo():
                return

            # 2. 创建测试数据
            if not await self.create_test_data(project_count=5, builds_per_project=10):
                return

            # 3. 运行性能测试
            read_results = await self.benchmark_concurrent_reads(concurrency=50, operations=500)
            write_results = await self.benchmark_concurrent_writes(concurrency=25, operations=200)
            mixed_results = await self.benchmark_mixed_workload(duration_seconds=30, max_concurrency=30)

            # 4. 功能演示
            await self.demonstrate_transaction_management()
            await self.demonstrate_batch_operations()
            await self.demonstrate_performance_monitoring()

            # 5. 输出总结报告
            logger.info("=== 演示总结报告 ===")
            logger.info(f"并发读取吞吐量: {read_results['throughput']:.2f} ops/s")
            logger.info(f"并发写入吞吐量: {write_results['throughput']:.2f} ops/s")
            logger.info(f"混合工作负载吞吐量: {mixed_results['throughput']:.2f} ops/s")
            logger.info(f"混合工作负载平均响应时间: {mixed_results['avg_response_time']:.3f}s")

            # 6. 清理数据
            await self.cleanup_demo_data()

            logger.info("异步数据库性能演示完成")

        except Exception as e:
            logger.error(f"演示运行失败: {e}")

        finally:
            # 关闭数据库连接
            await close_async_database()
            logger.info("数据库连接已关闭")


async def main():
    """主函数"""
    demo = AsyncPerformanceDemo()
    await demo.run_full_demo()


if __name__ == "__main__":
    asyncio.run(main())