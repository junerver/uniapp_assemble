"""
Gradle构建工具模块。

提供Gradle项目构建、日志收集和产物提取功能。
"""

import asyncio
import logging
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, AsyncGenerator
import subprocess
import json

from ..utils.exceptions import BuildError

logger = logging.getLogger(__name__)


class GradleUtils:
    """Gradle工具类。"""

    def __init__(self, project_path: str):
        """
        初始化Gradle工具。

        Args:
            project_path: Android项目路径
        """
        import sys
        self.project_path = Path(project_path)
        # Windows使用gradlew.bat，Linux/Mac使用gradlew
        if sys.platform == "win32":
            self.gradle_wrapper = self.project_path / "gradlew.bat"
        else:
            self.gradle_wrapper = self.project_path / "gradlew"
        self.gradle_properties = self.project_path / "gradle.properties"

    def is_gradle_project(self) -> bool:
        """
        检查是否为有效的Gradle项目。

        Returns:
            如果是Gradle项目返回True，否则返回False
        """
        # 检查gradlew文件是否存在
        if not self.gradle_wrapper.exists():
            # 检查是否有build.gradle文件
            build_files = list(self.project_path.glob("**/build.gradle*"))
            if not build_files:
                return False

        # 检查是否有gradle目录
        gradle_dir = self.project_path / "gradle"
        return gradle_dir.exists()

    def get_gradle_version(self) -> Optional[str]:
        """
        获取Gradle版本。

        Returns:
            Gradle版本字符串，如果无法获取则返回None
        """
        # 尝试从gradle-wrapper.properties获取版本
        wrapper_properties = self.project_path / "gradle" / "wrapper" / "gradle-wrapper.properties"
        if wrapper_properties.exists():
            try:
                with open(wrapper_properties, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.startswith('distributionUrl='):
                            # 解析版本号: https://services.gradle.org/distributions/gradle-8.4-bin.zip
                            match = re.search(r'gradle-(\d+\.\d+(\.\d+)?)', line)
                            if match:
                                return match.group(1)
            except Exception as e:
                logger.warning(f"读取gradle-wrapper.properties失败: {e}")

        # 尝试从gradle.properties获取版本
        if self.gradle_properties.exists():
            try:
                with open(self.gradle_properties, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.startswith('gradleVersion='):
                            return line.split('=')[1].strip()
            except Exception as e:
                logger.warning(f"读取gradle.properties失败: {e}")

        return None

    def get_available_tasks(self) -> List[str]:
        """
        获取可用的Gradle任务列表。

        Returns:
            任务名称列表
        """
        try:
            result = subprocess.run(
                [str(self.gradle_wrapper), "tasks", "--all"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                tasks = []
                for line in result.stdout.split('\n'):
                    # 解析任务名称，格式通常为: assembleDebug - Assembles the Debug build
                    match = re.match(r'^([a-zA-Z][a-zA-Z0-9:]*)\s*-\s*.+', line)
                    if match:
                        tasks.append(match.group(1))
                return sorted(tasks)
            else:
                logger.error(f"获取Gradle任务失败: {result.stderr}")
                return []

        except subprocess.TimeoutExpired:
            logger.error("获取Gradle任务超时")
            return []
        except Exception as e:
            logger.error(f"获取Gradle任务异常: {e}")
            return []

    def get_build_variants(self) -> List[str]:
        """
        获取可用的构建变体。

        Returns:
            构建变体列表
        """
        try:
            result = subprocess.run(
                [str(self.gradle_wrapper), "properties"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                variants = []
                for line in result.stdout.split('\n'):
                    if line.strip().startswith('android.buildTypes'):
                        # 解析构建类型
                        types_match = re.search(r'\{([^}]+)\}', line)
                        if types_match:
                            types = [t.strip() for t in types_match.group(1).split(',')]
                            variants.extend(types)

                return list(set(variants))
            else:
                logger.error(f"获取构建变体失败: {result.stderr}")
                return []

        except Exception as e:
            logger.error(f"获取构建变体异常: {e}")
            return []

    def get_build_flavors(self) -> List[str]:
        """
        获取可用的构建风味。

        Returns:
            构建风味列表
        """
        try:
            result = subprocess.run(
                [str(self.gradle_wrapper), "properties"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                flavors = []
                for line in result.stdout.split('\n'):
                    if line.strip().startswith('android.productFlavors'):
                        # 解析产品风味
                        flavors_match = re.search(r'\{([^}]+)\}', line)
                        if flavors_match:
                            flavors = [f.strip() for f in flavors_match.group(1).split(',')]
                            flavors.extend(flavors)

                return list(set(flavors))
            else:
                logger.error(f"获取构建风味失败: {result.stderr}")
                return []

        except Exception as e:
            logger.error(f"获取构建风味异常: {e}")
            return []

    async def execute_build_async(
        self,
        build_type: str = "clean :app:assembleRelease",
        config_options: Optional[Dict[str, Any]] = None
    ) -> subprocess.Popen:
        """
        异步执行Gradle构建。

        Args:
            build_type: 构建类型，如 "assembleDebug"
            config_options: 构建配置选项

        Returns:
            异步进程对象

        Raises:
            BuildError: 构建执行失败
        """
        if not self.is_gradle_project():
            raise BuildError(f"不是有效的Gradle项目: {self.project_path}")

        # 构建命令 - 支持多任务命令(如 "clean :app:assembleRelease")
        cmd = [str(self.gradle_wrapper)]
        # 将build_type按空格分割,支持多个任务
        build_tasks = build_type.split()
        cmd.extend(build_tasks)

        # 添加配置选项
        if config_options:
            if config_options.get("parallel", True):
                cmd.append("--parallel")

            if config_options.get("daemon", True):
                cmd.append("--daemon")

            if config_options.get("stacktrace", False):
                cmd.append("--stacktrace")

            if config_options.get("info", False):
                cmd.append("--info")

            if config_options.get("continue", False):
                cmd.append("--continue")

        # 设置环境变量
        env = os.environ.copy()
        if config_options and config_options.get("java_home"):
            env["JAVA_HOME"] = config_options["java_home"]

        # 简化配置：让Gradle使用其默认JVM设置
        # 移除了复杂的GRADLE_OPTS配置，避免JVM启动失败
        # 用户反馈：只需要在项目目录下执行 ./gradlew clean :app:assembleRelease 命令即可

        # 仅在用户明确指定时才设置GRADLE_USER_HOME
        if config_options and config_options.get("gradle_user_home"):
            env["GRADLE_USER_HOME"] = config_options["gradle_user_home"]

        timeout_minutes = config_options.get("timeout_minutes", 30) if config_options else 30

        logger.info(f"开始执行Gradle构建: {' '.join(cmd)}")
        logger.info(f"工作目录: {self.project_path}")

        try:
            # Windows上asyncio不支持subprocess,使用同步subprocess.Popen
            # 创建进程对象（不等待完成）
            import sys
            if sys.platform == "win32":
                # Windows: 使用CREATE_NO_WINDOW避免弹出控制台窗口
                import subprocess
                process = subprocess.Popen(
                    cmd,
                    cwd=str(self.project_path),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                )
            else:
                # Unix/Linux: 使用asyncio subprocess
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=self.project_path,
                    env=env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

            logger.info(f"Gradle构建进程已启动，PID: {process.pid}")
            return process

        except asyncio.TimeoutError:
            error_msg = f"Gradle构建启动超时 ({timeout_minutes} 分钟)"
            logger.error(error_msg)
            raise BuildError(error_msg)
        except Exception as e:
            error_msg = f"启动Gradle构建失败: {str(e)}"
            logger.error(error_msg)
            raise BuildError(error_msg)

    def get_build_artifacts(self) -> List[Dict[str, Any]]:
        """
        获取构建产物。

        Returns:
            构建产物列表
        """
        artifacts = []
        build_dir = self.project_path / "app" / "build" / "outputs"

        if not build_dir.exists():
            return artifacts

        # 查找APK文件
        apk_dir = build_dir / "apk"
        if apk_dir.exists():
            for apk_file in apk_dir.rglob("*.apk"):
                stat = apk_file.stat()
                artifacts.append({
                    "type": "apk",
                    "name": apk_file.name,
                    "path": str(apk_file),
                    "size": stat.st_size,
                    "modified_time": stat.st_mtime,
                    "variant": self._extract_variant_from_path(apk_file)
                })

        # 查找AAB文件
        aab_dir = build_dir / "bundle"
        if aab_dir.exists():
            for aab_file in aab_dir.rglob("*.aab"):
                stat = aab_file.stat()
                artifacts.append({
                    "type": "aab",
                    "name": aab_file.name,
                    "path": str(aab_file),
                    "size": stat.st_size,
                    "modified_time": stat.st_mtime,
                    "variant": self._extract_variant_from_path(aab_file)
                })

        return sorted(artifacts, key=lambda x: x["modified_time"], reverse=True)

    def _extract_variant_from_path(self, file_path: Path) -> str:
        """
        从文件路径提取构建变体信息。

        Args:
            file_path: 文件路径

        Returns:
            构建变体字符串
        """
        path_parts = file_path.parts
        for part in reversed(path_parts):
            if part in ["debug", "release", "staging", "prod"]:
                return part
        return "unknown"

    def get_project_info(self) -> Dict[str, Any]:
        """
        获取项目信息。

        Returns:
            项目信息字典
        """
        info = {
            "is_gradle_project": self.is_gradle_project(),
            "gradle_version": self.get_gradle_version(),
            "available_tasks": self.get_available_tasks(),
            "build_variants": self.get_build_variants(),
            "build_flavors": self.get_build_flavors(),
            "project_path": str(self.project_path)
        }

        # 尝试读取应用信息
        manifest_path = self.project_path / "app" / "src" / "main" / "AndroidManifest.xml"
        if manifest_path.exists():
            try:
                import xml.etree.ElementTree as ET
                tree = ET.parse(manifest_path)
                root = tree.getroot()

                package_name = root.get("package")
                version_code = root.get("{http://schemas.android.com/apk/res/android}versionCode")
                version_name = root.get("{http://schemas.android.com/apk/res/android}versionName")

                info.update({
                    "package_name": package_name,
                    "version_code": version_code,
                    "version_name": version_name
                })
            except Exception as e:
                logger.warning(f"解析AndroidManifest.xml失败: {e}")

        return info

    def clean_build_cache(self) -> bool:
        """
        清理构建缓存。

        Returns:
            清理是否成功
        """
        try:
            result = subprocess.run(
                [str(self.gradle_wrapper), "clean"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                logger.info("构建缓存清理成功")
                return True
            else:
                logger.error(f"构建缓存清理失败: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("构建缓存清理超时")
            return False
        except Exception as e:
            logger.error(f"构建缓存清理异常: {e}")
            return False

    def validate_build_environment(self) -> Dict[str, Any]:
        """
        验证构建环境。

        Returns:
            验证结果字典
        """
        validation = {
            "valid": True,
            "issues": [],
            "warnings": []
        }

        # 检查Gradle项目
        if not self.is_gradle_project():
            validation["valid"] = False
            validation["issues"].append("不是有效的Gradle项目")
            return validation

        # 检查Gradle版本
        gradle_version = self.get_gradle_version()
        if not gradle_version:
            validation["warnings"].append("无法确定Gradle版本")
        else:
            # 检查版本是否过旧
            try:
                major_version = int(gradle_version.split('.')[0])
                if major_version < 7:
                    validation["warnings"].append(f"Gradle版本较旧 ({gradle_version})，建议升级到7.0+")
            except (ValueError, IndexError):
                validation["warnings"].append(f"无法解析Gradle版本: {gradle_version}")

        # 检查Java环境
        try:
            result = subprocess.run(
                ["java", "-version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                validation["valid"] = False
                validation["issues"].append("Java环境不可用")
            else:
                # 解析Java版本
                java_version = result.stderr.split('\n')[0] if result.stderr else result.stdout.split('\n')[0]
                if "1.8" in java_version:
                    validation["warnings"].append("使用Java 8，建议升级到Java 11+")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            validation["valid"] = False
            validation["issues"].append("Java环境不可用")

        # 检查Android SDK
        android_home = os.environ.get("ANDROID_HOME")
        if not android_home:
            validation["warnings"].append("未设置ANDROID_HOME环境变量")
        elif not Path(android_home).exists():
            validation["valid"] = False
            validation["issues"].append(f"ANDROID_HOME路径不存在: {android_home}")

        return validation