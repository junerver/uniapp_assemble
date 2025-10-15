"""
完整的Gradle构建监控系统使用示例
整合所有模块，展示端到端的使用流程
"""

import asyncio
import json
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, List
import logging

# 导入我们的模块
from gradle_monitor import GradleBuildManager, BuildStatus
from fastapi_gradle_integration import create_app, ProjectManager
from task_timeout_manager import LongRunningTaskManager, ResourceLimits, TimeoutConfig
from apk_builder_analyzer import BuildResultAnalyzer, APKDetector
from performance_optimization_guide import PerformanceOptimizer, ConfigurationOptimizer, PerformanceLevel

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GradleBuildSystem:
    """完整的Gradle构建系统"""

    def __init__(self):
        # 初始化各个组件
        self.build_manager = GradleBuildManager(max_concurrent_builds=3)
        self.project_manager = ProjectManager()
        self.result_analyzer = BuildResultAnalyzer()
        self.config_optimizer = ConfigurationOptimizer()
        self.performance_optimizer = PerformanceOptimizer(self.config_optimizer.config)
        self.task_manager = LongRunningTaskManager()

        self.is_initialized = False

    async def initialize(self):
        """初始化系统"""
        if self.is_initialized:
            return

        logger.info("正在初始化Gradle构建系统...")

        # 启动各个组件
        await self.build_manager.start()
        await self.performance_optimizer.start_monitoring()
        await self.task_manager.start()

        # 系统优化
        self.config_optimizer.optimize_for_system()
        self.config_optimizer.set_performance_level(PerformanceLevel.HIGH_PERFORMANCE)

        self.is_initialized = True
        logger.info("Gradle构建系统初始化完成")

    async def shutdown(self):
        """关闭系统"""
        if not self.is_initialized:
            return

        logger.info("正在关闭Gradle构建系统...")

        await self.task_manager.stop()
        await self.performance_optimizer.stop_monitoring()
        await self.build_manager.stop()

        self.is_initialized = False
        logger.info("Gradle构建系统已关闭")

    async def create_project_from_zip(self, zip_path: str) -> Dict[str, Any]:
        """从ZIP文件创建项目"""
        logger.info(f"正在从ZIP文件创建项目: {zip_path}")

        try:
            # 这里应该调用实际的上传逻辑
            # 为了示例，我们模拟项目创建
            project_id = f"demo_project_{int(asyncio.get_event_loop().time())}"

            project_info = {
                "project_id": project_id,
                "project_path": f"/tmp/projects/{project_id}",
                "created_at": "2024-01-01T00:00:00",
                "status": "created"
            }

            logger.info(f"项目创建成功: {project_id}")
            return project_info

        except Exception as e:
            logger.error(f"创建项目失败: {e}")
            raise

    async def build_project(
        self,
        project_path: str,
        build_tasks: List[str] = None,
        timeout: int = 600
    ) -> Dict[str, Any]:
        """构建项目"""
        if not self.is_initialized:
            await self.initialize()

        if build_tasks is None:
            build_tasks = ["assembleDebug"]

        logger.info(f"开始构建项目: {project_path}, 任务: {build_tasks}")

        # 创建日志回调
        logs = []
        def log_callback(log_entry):
            logs.append(log_entry)
            print(f"[{log_entry['type']}] {log_entry['content']}")

        # 创建进度回调
        progress_data = {}
        def progress_callback(progress):
            progress_data.update({
                "percentage": progress.percentage,
                "current_step": progress.current_step,
                "current_file": progress.current_file
            })
            print(f"构建进度: {progress.percentage:.1f}% - {progress.current_step}")

        # 提交构建任务
        build_id = await self.build_manager.submit_build(
            project_path,
            build_tasks,
            timeout,
            log_callback,
            progress_callback
        )

        logger.info(f"构建任务已提交: {build_id}")

        # 等待构建完成
        result = await self._wait_for_build_completion(build_id)

        if result.status == BuildStatus.SUCCESS:
            # 分析构建结果
            analysis = await self.result_analyzer.analyze_build_result(
                build_id,
                result.apk_path,
                logs,
                result.duration or 0.0
            )

            return {
                "build_id": build_id,
                "status": "success",
                "apk_path": result.apk_path,
                "duration": result.duration,
                "analysis": {
                    "quality_score": analysis.quality_score,
                    "warnings": analysis.warnings,
                    "errors": analysis.errors,
                    "recommendations": analysis.recommendations
                },
                "apk_info": {
                    "package_name": analysis.apk_info.package_name if analysis.apk_info else "",
                    "version_name": analysis.apk_info.version_name if analysis.apk_info else "",
                    "file_size_mb": (analysis.apk_info.file_size / (1024*1024)) if analysis.apk_info else 0
                } if analysis.apk_info else None
            }
        else:
            return {
                "build_id": build_id,
                "status": "failed",
                "error": result.error_message,
                "duration": result.duration,
                "logs_count": len(logs)
            }

    async def _wait_for_build_completion(self, build_id: str, check_interval: float = 2.0) -> Any:
        """等待构建完成"""
        while True:
            result = await self.build_manager.get_build_status(build_id)

            if not result:
                raise Exception(f"构建任务不存在: {build_id}")

            if result.status in [BuildStatus.SUCCESS, BuildStatus.FAILED, BuildStatus.CANCELLED, BuildStatus.TIMEOUT]:
                return result

            await asyncio.sleep(check_interval)

    async def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        if not self.is_initialized:
            await self.initialize()

        # 获取活跃构建
        active_builds = []
        for build_id, result in self.build_manager.active_builds.items():
            active_builds.append({
                "build_id": build_id,
                "status": result.status.value,
                "progress": result.progress.percentage,
                "duration": (result.end_time - result.start_time).total_seconds() if result.end_time else 0
            })

        # 获取性能指标
        current_metrics = self.performance_optimizer.get_current_metrics()
        metrics_summary = self.performance_optimizer.get_metrics_summary()

        return {
            "system_status": "running",
            "active_builds": active_builds,
            "performance_metrics": current_metrics.__dict__ if current_metrics else {},
            "metrics_summary": metrics_summary,
            "configuration": {
                "max_concurrent_builds": self.config_optimizer.config.max_concurrent_builds,
                "max_memory_per_build": self.config_optimizer.config.max_memory_per_build,
                "performance_level": self.config_optimizer.performance_level.value
            }
        }

    async def cancel_build(self, build_id: str) -> bool:
        """取消构建"""
        success = await self.build_manager.cancel_build(build_id)
        if success:
            logger.info(f"构建已取消: {build_id}")
        else:
            logger.warning(f"无法取消构建: {build_id}")
        return success


async def demo_workflow():
    """演示完整的工作流程"""

    print("=" * 80)
    print("Gradle构建监控系统演示")
    print("=" * 80)

    # 创建构建系统
    build_system = GradleBuildSystem()

    try:
        # 初始化系统
        await build_system.initialize()

        # 显示系统状态
        print("\n1. 系统状态:")
        status = await build_system.get_system_status()
        print(json.dumps(status, indent=2, default=str))

        # 模拟项目创建
        print("\n2. 创建项目:")
        # 注意：这里使用模拟路径，实际使用时需要真实的项目路径
        project_path = "/path/to/android/project"  # 替换为实际路径

        print(f"使用项目路径: {project_path}")
        print("注意：此演示使用模拟路径，实际使用时请替换为真实的Android项目路径")

        # 开始构建
        print("\n3. 开始构建:")
        build_result = await build_system.build_project(
            project_path=project_path,
            build_tasks=["assembleDebug"],
            timeout=300
        )

        print(f"构建结果: {json.dumps(build_result, indent=2, default=str)}")

        # 显示最终系统状态
        print("\n4. 最终系统状态:")
        final_status = await build_system.get_system_status()
        print(json.dumps(final_status, indent=2, default=str))

    except Exception as e:
        logger.error(f"演示过程中发生错误: {e}")
        print(f"错误: {e}")

    finally:
        # 清理
        await build_system.shutdown()
        print("\n系统已关闭")


async def demo_performance_monitoring():
    """演示性能监控功能"""

    print("=" * 80)
    print("性能监控演示")
    print("=" * 80)

    # 创建配置优化器
    config_optimizer = ConfigurationOptimizer()
    config_optimizer.optimize_for_system()
    config_optimizer.set_performance_level(PerformanceLevel.HIGH_PERFORMANCE)

    print("配置优化结果:")
    print(f"最大并发构建数: {config_optimizer.config.max_concurrent_builds}")
    print(f"每个构建最大内存: {config_optimizer.config.max_memory_per_build}MB")
    print(f"Gradle堆大小: {config_optimizer.config.gradle_heap_size}")

    # 创建性能优化器
    performance_optimizer = PerformanceOptimizer(config_optimizer.config)
    await performance_optimizer.start_monitoring()

    try:
        # 监控一段时间
        print("\n正在监控系统性能...")
        await asyncio.sleep(10)

        # 获取性能指标
        current_metrics = performance_optimizer.get_current_metrics()
        if current_metrics:
            print(f"\n当前性能指标:")
            print(f"CPU使用率: {current_metrics.cpu_usage:.1f}%")
            print(f"内存使用率: {current_metrics.memory_usage:.1f}%")
            print(f"磁盘使用率: {current_metrics.disk_usage:.1f}%")

        metrics_summary = performance_optimizer.get_metrics_summary()
        if metrics_summary:
            print(f"\n性能指标摘要:")
            print(json.dumps(metrics_summary, indent=2))

    finally:
        await performance_optimizer.stop_monitoring()


async def demo_fastapi_integration():
    """演示FastAPI集成"""

    print("=" * 80)
    print("FastAPI集成演示")
    print("=" * 80)

    # 创建FastAPI应用
    app = create_app()

    print("FastAPI应用已创建")
    print("可用的API端点:")
    print("- POST /api/projects/upload - 上传项目")
    print("- GET /api/projects - 列出项目")
    print("- POST /api/builds - 提交构建")
    print("- GET /api/builds/{build_id} - 获取构建状态")
    print("- WebSocket /ws/{client_id} - 实时通信")
    print("- GET /health - 健康检查")
    print("- GET /api/stats - 系统统计")

    print("\n要启动API服务器，请运行:")
    print("uvicorn fastapi_gradle_integration:app --host 0.0.0.0 --port 8000")


def print_usage_examples():
    """打印使用示例"""

    print("=" * 80)
    print("使用示例")
    print("=" * 80)

    print("""
1. 基本使用:

from gradle_monitor import GradleBuildManager
from fastapi_gradle_integration import create_app

# 创建构建管理器
build_manager = GradleBuildManager()
await build_manager.start()

# 提交构建任务
build_id = await build_manager.submit_build(
    "/path/to/android/project",
    ["assembleDebug"],
    timeout=600
)

# 监控构建状态
result = await build_manager.get_build_status(build_id)
print(f"构建状态: {result.status}")

2. FastAPI集成:

import uvicorn
from fastapi_gradle_integration import app

# 启动API服务器
uvicorn.run(app, host="0.0.0.0", port=8000)

3. 性能优化:

from performance_optimization_guide import ConfigurationOptimizer, PerformanceLevel

config_optimizer = ConfigurationOptimizer()
config_optimizer.optimize_for_system()
config_optimizer.set_performance_level(PerformanceLevel.HIGH_PERFORMANCE)

4. APK分析:

from apk_builder_analyzer import BuildResultAnalyzer

analyzer = BuildResultAnalyzer()
analysis = await analyzer.analyze_build_result(
    build_id="build_001",
    apk_path="/path/to/app.apk",
    build_logs=[],
    build_duration=120.0
)

print(f"质量分数: {analysis.quality_score}")

5. 长时间任务管理:

from task_timeout_manager import LongRunningTaskManager, ResourceLimits

task_manager = LongRunningTaskManager(
    resource_limits=ResourceLimits(max_memory_mb=2048),
    timeout_config=TimeoutConfig(default_timeout=600)
)
await task_manager.start()

# 执行长时间运行的任务
result = await task_manager.execute_task(
    "task_001",
    long_running_coroutine(),
    timeout=600
)
""")


async def main():
    """主函数"""
    print("Gradle构建监控系统 - 完整演示")
    print("请选择要运行的演示:")
    print("1. 完整工作流程演示")
    print("2. 性能监控演示")
    print("3. FastAPI集成演示")
    print("4. 显示使用示例")
    print("5. 运行所有演示")

    try:
        choice = input("请输入选择 (1-5): ").strip()

        if choice == "1":
            await demo_workflow()
        elif choice == "2":
            await demo_performance_monitoring()
        elif choice == "3":
            await demo_fastapi_integration()
        elif choice == "4":
            print_usage_examples()
        elif choice == "5":
            await demo_workflow()
            await demo_performance_monitoring()
            await demo_fastapi_integration()
            print_usage_examples()
        else:
            print("无效选择，运行默认演示")
            await demo_workflow()

    except KeyboardInterrupt:
        print("\n演示被用户中断")
    except Exception as e:
        print(f"演示过程中发生错误: {e}")


if __name__ == "__main__":
    # 设置事件循环策略（Windows兼容性）
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    # 运行演示
    asyncio.run(main())