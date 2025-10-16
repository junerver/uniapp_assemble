"""
APK提取服务。

负责处理Android APK文件的扫描、提取和分析功能。
"""

import asyncio
import logging
import os
import shutil
import zipfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import tempfile
import xml.etree.ElementTree as ET

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.android_project import AndroidProject
from ..utils.exceptions import BuildError, ValidationError

logger = logging.getLogger(__name__)


class APKService:
    """APK提取服务类。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def extract_apk_files(
        self,
        project_path: str,
        config_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        扫描并提取APK文件。

        Args:
            project_path: Android项目路径
            config_options: 配置选项

        Returns:
            提取结果字典

        Raises:
            BuildError: 提取失败
            ValidationError: 验证失败
        """
        project_path = Path(project_path)

        # 验证输入
        await self._validate_project_path(project_path)

        # 扫描APK文件
        apk_files = await self._scan_apk_files(project_path)

        if not apk_files:
            logger.warning(f"未找到APK文件: {project_path}")
            return {
                "success": True,
                "apk_files": [],
                "total_count": 0,
                "total_size": 0,
                "message": "未找到APK文件"
            }

        # 分析APK文件
        analyzed_files = []
        total_size = 0

        for apk_file in apk_files:
            try:
                analysis = await self._analyze_apk_file(apk_file, config_options or {})
                analyzed_files.append(analysis)
                total_size += analysis["file_size"]
            except Exception as e:
                logger.error(f"分析APK文件失败 {apk_file}: {e}")
                analyzed_files.append({
                    "file_path": str(apk_file),
                    "file_name": apk_file.name,
                    "file_size": apk_file.stat().st_size,
                    "error": str(e)
                })

        # 按修改时间排序
        analyzed_files.sort(key=lambda x: x.get("modified_time", 0), reverse=True)

        result = {
            "success": True,
            "apk_files": analyzed_files,
            "total_count": len(analyzed_files),
            "total_size": total_size,
            "scan_path": str(project_path),
            "extracted_at": await self._get_current_timestamp()
        }

        logger.info(f"APK文件扫描完成: {len(analyzed_files)} 个文件")
        return result

    async def _validate_project_path(self, project_path: Path) -> None:
        """验证项目路径。"""
        if not project_path.exists():
            raise ValidationError(f"项目路径不存在: {project_path}")

        if not project_path.is_dir():
            raise ValidationError(f"项目路径不是目录: {project_path}")

    async def _scan_apk_files(self, project_path: Path) -> List[Path]:
        """扫描APK文件。"""
        apk_files = []

        # 常见的APK输出目录
        scan_paths = [
            project_path / "app" / "build" / "outputs" / "apk",
            project_path / "build" / "outputs" / "apk",
            project_path / "app" / "release",
            project_path / "app" / "debug",
            project_path  # 根目录扫描
        ]

        for scan_path in scan_paths:
            if scan_path.exists():
                apk_files.extend(scan_path.rglob("*.apk"))

        # 去重
        apk_files = list(set(apk_files))

        # 过滤掉无效的文件
        valid_apks = []
        for apk_file in apk_files:
            if apk_file.is_file() and apk_file.stat().st_size > 0:
                valid_apks.append(apk_file)

        return valid_apks

    async def _analyze_apk_file(
        self,
        apk_file: Path,
        config_options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """分析单个APK文件。"""
        stat = apk_file.stat()

        analysis = {
            "file_path": str(apk_file),
            "file_name": apk_file.name,
            "file_size": stat.st_size,
            "modified_time": stat.st_mtime,
            "created_time": stat.st_ctime,
            "file_hash": await self._calculate_file_hash(apk_file),
            "build_variant": await self._extract_build_variant(apk_file),
            "package_info": None,
            "permissions": [],
            "activities": [],
            "services": [],
            "native_libs": [],
            "resources": [],
            "manifest_valid": False
        }

        # 提取APK内容进行分析
        if config_options.get("deep_analysis", False):
            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)

                    # 解压APK
                    await self._extract_apk(apk_file, temp_path)

                    # 分析AndroidManifest.xml
                    manifest_info = await self._analyze_manifest(temp_path)
                    if manifest_info:
                        analysis.update(manifest_info)
                        analysis["manifest_valid"] = True

                    # 分析资源文件
                    if config_options.get("analyze_resources", True):
                        resource_info = await self._analyze_resources(temp_path)
                        analysis["resources"] = resource_info

                    # 分析原生库
                    if config_options.get("analyze_native_libs", True):
                        native_libs = await self._analyze_native_libs(temp_path)
                        analysis["native_libs"] = native_libs

            except Exception as e:
                logger.warning(f"深度分析APK失败 {apk_file}: {e}")
                analysis["analysis_error"] = str(e)

        return analysis

    async def _calculate_file_hash(self, file_path: Path) -> str:
        """计算文件哈希值。"""
        import hashlib

        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.error(f"计算文件哈希失败 {file_path}: {e}")
            return ""

    async def _extract_build_variant(self, apk_file: Path) -> str:
        """从文件路径提取构建变体信息。"""
        path_parts = apk_file.parts
        path_str = str(apk_file).lower()

        # 检查构建类型
        if "debug" in path_str:
            build_type = "debug"
        elif "release" in path_str:
            build_type = "release"
        elif "staging" in path_str:
            build_type = "staging"
        elif "prod" in path_str:
            build_type = "prod"
        else:
            build_type = "unknown"

        # 检查构建风味
        flavor = "unknown"
        for part in reversed(path_parts):
            if part not in ["apk", "outputs", "build", "app", "debug", "release", "staging", "prod"]:
                if part and part != apk_file.parent.name:
                    flavor = part
                    break

        return f"{flavor}-{build_type}" if flavor != "unknown" else build_type

    async def _extract_apk(self, apk_file: Path, extract_path: Path) -> None:
        """解压APK文件。"""
        try:
            with zipfile.ZipFile(apk_file, 'r') as zip_file:
                zip_file.extractall(extract_path)
        except zipfile.BadZipFile as e:
            raise BuildError(f"无效的APK文件: {e}")

    async def _analyze_manifest(self, extract_path: Path) -> Optional[Dict[str, Any]]:
        """分析AndroidManifest.xml。"""
        manifest_path = extract_path / "AndroidManifest.xml"

        if not manifest_path.exists():
            return None

        try:
            # 解析二进制XML（简化处理）
            tree = ET.parse(manifest_path)
            root = tree.getroot()

            # 提取包信息
            package_info = {
                "package_name": root.get("package"),
                "version_code": root.get("{http://schemas.android.com/apk/res/android}versionCode"),
                "version_name": root.get("{http://schemas.android.com/apk/res/android}versionName"),
                "compile_sdk": root.get("{http://schemas.android.com/apk/res/android}compileSdkVersion"),
                "target_sdk": root.get("{http://schemas.android.com/apk/res/android}targetSdkVersion"),
                "min_sdk": root.get("{http://schemas.android.com/apk/res/android}minSdkVersion")
            }

            # 提取权限
            permissions = []
            for child in root:
                if child.tag == "uses-permission":
                    permission = child.get("{http://schemas.android.com/apk/res/android}name")
                    if permission:
                        permissions.append(permission)

            # 提取组件
            activities = []
            services = []
            receivers = []
            providers = []

            for child in root:
                if child.tag == "application":
                    for component in child:
                        name = component.get("{http://schemas.android.com/apk/res/android}name")
                        if name:
                            if component.tag == "activity":
                                activities.append(name)
                            elif component.tag == "service":
                                services.append(name)
                            elif component.tag == "receiver":
                                receivers.append(name)
                            elif component.tag == "provider":
                                providers.append(name)

            return {
                "package_info": package_info,
                "permissions": permissions,
                "activities": activities,
                "services": services,
                "receivers": receivers,
                "providers": providers
            }

        except Exception as e:
            logger.warning(f"解析AndroidManifest.xml失败: {e}")
            return None

    async def _analyze_resources(self, extract_path: Path) -> List[Dict[str, Any]]:
        """分析资源文件。"""
        res_path = extract_path / "res"
        if not res_path.exists():
            return []

        resources = []

        for root, dirs, files in os.walk(res_path):
            for file in files:
                file_path = Path(root) / file
                relative_path = file_path.relative_to(res_path)

                resource_info = {
                    "name": file,
                    "path": str(relative_path),
                    "type": await self._get_resource_type(file_path),
                    "size": file_path.stat().st_size
                }

                resources.append(resource_info)

        return resources

    async def _get_resource_type(self, file_path: Path) -> str:
        """获取资源类型。"""
        parent_dir = file_path.parent.name.lower()
        extension = file_path.suffix.lower()

        if parent_dir.startswith("drawable"):
            return "drawable"
        elif parent_dir.startswith("layout"):
            return "layout"
        elif parent_dir.startswith("values"):
            return "values"
        elif parent_dir.startswith("mipmap"):
            return "mipmap"
        elif parent_dir.startswith("raw"):
            return "raw"
        elif parent_dir.startswith("anim"):
            return "animation"
        elif parent_dir.startswith("color"):
            return "color"
        elif parent_dir.startswith("menu"):
            return "menu"
        elif extension in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
            return "image"
        elif extension in [".xml"]:
            return "xml"
        elif extension in [".json"]:
            return "json"
        else:
            return "other"

    async def _analyze_native_libs(self, extract_path: Path) -> List[Dict[str, Any]]:
        """分析原生库文件。"""
        lib_path = extract_path / "lib"
        if not lib_path.exists():
            return []

        native_libs = []

        for arch_dir in lib_path.iterdir():
            if arch_dir.is_dir():
                arch_name = arch_dir.name  # arm64-v8a, armeabi-v7a, etc.

                for lib_file in arch_dir.iterdir():
                    if lib_file.is_file() and lib_file.suffix == ".so":
                        lib_info = {
                            "name": lib_file.name,
                            "architecture": arch_name,
                            "size": lib_file.stat().st_size,
                            "path": str(lib_file.relative_to(extract_path))
                        }
                        native_libs.append(lib_info)

        return native_libs

    async def _get_current_timestamp(self) -> str:
        """获取当前时间戳。"""
        from datetime import datetime
        return datetime.utcnow().isoformat()

    async def get_apk_info(self, apk_file_path: str) -> Dict[str, Any]:
        """
        获取单个APK文件的详细信息。

        Args:
            apk_file_path: APK文件路径

        Returns:
            APK信息字典
        """
        apk_file = Path(apk_file_path)

        if not apk_file.exists():
            raise ValidationError(f"APK文件不存在: {apk_file_path}")

        # 基本分析
        analysis = await self._analyze_apk_file(apk_file, {"deep_analysis": True})

        return analysis

    async def compare_apk_files(
        self,
        apk_file1: str,
        apk_file2: str
    ) -> Dict[str, Any]:
        """
        比较两个APK文件的差异。

        Args:
            apk_file1: 第一个APK文件路径
            apk_file2: 第二个APK文件路径

        Returns:
            比较结果字典
        """
        file1 = Path(apk_file1)
        file2 = Path(apk_file2)

        if not file1.exists() or not file2.exists():
            raise ValidationError("APK文件不存在")

        # 分析两个文件
        analysis1 = await self.get_apk_info(apk_file1)
        analysis2 = await self.get_apk_info(apk_file2)

        comparison = {
            "file1": {
                "name": file1.name,
                "size": analysis1["file_size"],
                "hash": analysis1["file_hash"]
            },
            "file2": {
                "name": file2.name,
                "size": analysis2["file_size"],
                "hash": analysis2["file_hash"]
            },
            "differences": {
                "size_diff": analysis2["file_size"] - analysis1["file_size"],
                "hash_same": analysis1["file_hash"] == analysis2["file_hash"],
                "build_variant_diff": analysis1["build_variant"] != analysis2["build_variant"]
            }
        }

        # 比较包信息
        if analysis1.get("package_info") and analysis2.get("package_info"):
            pkg1 = analysis1["package_info"]
            pkg2 = analysis2["package_info"]

            comparison["package_differences"] = {
                "version_code_diff": pkg1.get("version_code") != pkg2.get("version_code"),
                "version_name_diff": pkg1.get("version_name") != pkg2.get("version_name"),
                "package_name_diff": pkg1.get("package_name") != pkg2.get("package_name")
            }

        # 比较权限
        permissions1 = set(analysis1.get("permissions", []))
        permissions2 = set(analysis2.get("permissions", []))

        comparison["permission_differences"] = {
            "added": list(permissions2 - permissions1),
            "removed": list(permissions1 - permissions2),
            "common": list(permissions1 & permissions2)
        }

        return comparison