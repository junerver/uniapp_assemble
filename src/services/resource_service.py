"""
资源替换服务。

负责处理Android项目资源的替换操作，包括资源包解压、备份、替换和验证。
"""

import asyncio
import logging
import os
import shutil
import time
import zipfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import tempfile
import json
import re

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.android_project import AndroidProject
from ..utils.exceptions import BuildError, ValidationError
from ..utils.git_utils import GitUtils

logger = logging.getLogger(__name__)


class ResourceService:
    """资源替换服务类。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def replace_resources(
        self,
        project_path: str,
        resource_package_path: str,
        git_branch: str,
        config_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        执行资源替换操作。

        Args:
            project_path: Android项目路径
            resource_package_path: 资源包路径
            git_branch: Git分支
            config_options: 配置选项

        Returns:
            替换结果字典

        Raises:
            BuildError: 替换失败
            ValidationError: 验证失败
        """
        project_path = Path(project_path)
        resource_package_path = Path(resource_package_path)

        # 验证输入
        await self._validate_replacement_inputs(project_path, resource_package_path)

        # 创建备份
        backup_info = await self._create_project_backup(project_path, git_branch)

        # 解压资源包
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            extracted_resources = await self._extract_resource_package(
                resource_package_path, temp_path
            )

            # 执行资源替换
            replacement_result = await self._perform_resource_replacement(
                project_path, extracted_resources, config_options or {}
            )

            # 验证替换结果
            validation_result = await self._validate_replacement_result(
                project_path, extracted_resources
            )

        result = {
            "success": True,
            "backup_info": backup_info,
            "replacement_result": replacement_result,
            "validation_result": validation_result,
            "git_branch": git_branch
        }

        logger.info(f"资源替换完成: {project_path}")
        return result

    async def _validate_replacement_inputs(
        self,
        project_path: Path,
        resource_package_path: Path
    ) -> None:
        """验证替换输入参数。"""
        # 检查项目路径
        if not project_path.exists():
            raise ValidationError(f"项目路径不存在: {project_path}")

        if not project_path.is_dir():
            raise ValidationError(f"项目路径不是目录: {project_path}")

        # 检查是否为Android项目
        manifest_path = project_path / "app" / "src" / "main" / "AndroidManifest.xml"
        if not manifest_path.exists():
            raise ValidationError(f"不是有效的Android项目，缺少AndroidManifest.xml: {manifest_path}")

        # 检查资源包
        if not resource_package_path.exists():
            raise ValidationError(f"资源包不存在: {resource_package_path}")

        if not resource_package_path.is_file():
            raise ValidationError(f"资源包不是文件: {resource_package_path}")

        if resource_package_path.suffix.lower() != '.zip':
            raise ValidationError(f"资源包必须是ZIP文件: {resource_package_path}")

        # 验证ZIP文件完整性
        try:
            with zipfile.ZipFile(resource_package_path, 'r') as zip_file:
                zip_file.testzip()
        except zipfile.BadZipFile as e:
            raise ValidationError(f"资源包ZIP文件损坏: {e}")

    async def _create_project_backup(
        self,
        project_path: Path,
        git_branch: str
    ) -> Dict[str, Any]:
        """创建项目备份。"""
        try:
            # 创建Git备份
            backup_result = GitUtils.create_backup(project_path, f"before_resource_replacement_{git_branch}")
            backup_path = backup_result.get("backup_path") if backup_result.get("success") else None

            return {
                "backup_path": backup_path,
                "backup_type": "git",
                "git_branch": git_branch,
                "created_at": Path(backup_path).stat().st_mtime if backup_path else None
            }

        except Exception as e:
            logger.warning(f"Git备份失败，尝试文件系统备份: {e}")

            # 文件系统备份
            backup_dir = project_path.parent / f"{project_path.name}_backup_{int(time.time())}"
            try:
                shutil.copytree(project_path, backup_dir)
                return {
                    "backup_path": str(backup_dir),
                    "backup_type": "filesystem",
                    "created_at": backup_dir.stat().st_mtime
                }
            except Exception as backup_e:
                raise BuildError(f"创建备份失败: {backup_e}")

    async def _extract_resource_package(
        self,
        resource_package_path: Path,
        temp_path: Path
    ) -> Dict[str, Any]:
        """解压资源包。"""
        extracted_files = []
        resource_structure = {}

        try:
            with zipfile.ZipFile(resource_package_path, 'r') as zip_file:
                # 获取文件列表
                file_list = zip_file.namelist()

                # 检查资源包结构
                resource_structure = await self._analyze_resource_structure(file_list)

                # 解压所有文件
                for file_info in zip_file.infolist():
                    if not file_info.is_dir():
                        # 解压文件
                        extracted_path = zip_file.extract(file_info, temp_path)
                        extracted_files.append({
                            "source_path": file_info.filename,
                            "extracted_path": extracted_path,
                            "size": file_info.file_size,
                            "modified_time": file_info.date_time
                        })

            logger.info(f"资源包解压完成，共 {len(extracted_files)} 个文件")

            return {
                "temp_path": str(temp_path),
                "extracted_files": extracted_files,
                "structure": resource_structure
            }

        except Exception as e:
            raise BuildError(f"解压资源包失败: {e}")

    async def _analyze_resource_structure(self, file_list: List[str]) -> Dict[str, Any]:
        """分析资源包结构。"""
        structure = {
            "resources": {
                "drawable": [],
                "layout": [],
                "values": [],
                "mipmap": [],
                "raw": [],
                "other": []
            },
            "assets": [],
            "libs": [],
            "manifest": None,
            "other_files": []
        }

        # Android资源目录模式
        resource_patterns = {
            "drawable": re.compile(r"^res/drawable[^/]*/"),
            "layout": re.compile(r"^res/layout[^/]*/"),
            "values": re.compile(r"^res/values[^/]*/"),
            "mipmap": re.compile(r"^res/mipmap[^/]*/"),
            "raw": re.compile(r"^res/raw[^/]*/")
        }

        for file_path in file_list:
            if file_path.endswith('/'):
                continue  # 跳过目录

            # 检查是否为AndroidManifest.xml
            if file_path.endswith("AndroidManifest.xml"):
                structure["manifest"] = file_path

            # 检查是否为资源文件
            elif file_path.startswith("res/"):
                categorized = False
                for resource_type, pattern in resource_patterns.items():
                    if pattern.match(file_path):
                        structure["resources"][resource_type].append(file_path)
                        categorized = True
                        break
                if not categorized:
                    structure["resources"]["other"].append(file_path)

            # 检查是否为assets文件
            elif file_path.startswith("assets/"):
                structure["assets"].append(file_path)

            # 检查是否为库文件
            elif file_path.startswith("lib/") or file_path.endswith(".jar") or file_path.endswith(".aar"):
                structure["libs"].append(file_path)

            else:
                structure["other_files"].append(file_path)

        return structure

    async def _perform_resource_replacement(
        self,
        project_path: Path,
        extracted_resources: Dict[str, Any],
        config_options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行资源替换。"""
        temp_path = Path(extracted_resources["temp_path"])
        replaced_files = []
        skipped_files = []
        error_files = []

        # 获取替换配置
        replace_mode = config_options.get("replace_mode", "backup_existing")  # backup_existing, overwrite, skip
        target_patterns = config_options.get("target_patterns", [])  # 目标文件模式

        for file_info in extracted_resources["extracted_files"]:
            source_path = Path(file_info["extracted_path"])
            relative_path = file_info["source_path"]
            target_path = project_path / relative_path

            try:
                # 检查是否需要替换
                if target_patterns and not any(pattern.match(relative_path) for pattern in target_patterns):
                    skipped_files.append({
                        "path": relative_path,
                        "reason": "不匹配目标模式"
                    })
                    continue

                # 执行替换
                if await self._replace_single_file(
                    source_path, target_path, replace_mode
                ):
                    replaced_files.append({
                        "path": relative_path,
                        "size": file_info["size"],
                        "action": "replaced"
                    })
                else:
                    skipped_files.append({
                        "path": relative_path,
                        "reason": "未替换"
                    })

            except Exception as e:
                error_files.append({
                    "path": relative_path,
                    "error": str(e)
                })
                logger.error(f"替换文件失败 {relative_path}: {e}")

        result = {
            "replaced_files": replaced_files,
            "skipped_files": skipped_files,
            "error_files": error_files,
            "total_files": len(extracted_resources["extracted_files"]),
            "success_count": len(replaced_files),
            "error_count": len(error_files)
        }

        if error_files:
            logger.warning(f"替换完成，但有 {len(error_files)} 个文件失败")

        return result

    async def _replace_single_file(
        self,
        source_path: Path,
        target_path: Path,
        replace_mode: str
    ) -> bool:
        """替换单个文件。"""
        try:
            # 创建目标目录
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # 处理现有文件
            if target_path.exists():
                if replace_mode == "skip":
                    return False

                elif replace_mode == "backup_existing":
                    # 备份现有文件
                    backup_path = target_path.with_suffix(f"{target_path.suffix}.backup")
                    shutil.copy2(target_path, backup_path)

                elif replace_mode != "overwrite":
                    # 默认行为：备份现有文件
                    backup_path = target_path.with_suffix(f"{target_path.suffix}.backup")
                    shutil.copy2(target_path, backup_path)

            # 复制新文件
            shutil.copy2(source_path, target_path)
            return True

        except Exception as e:
            logger.error(f"替换单个文件失败 {source_path} -> {target_path}: {e}")
            return False

    async def _validate_replacement_result(
        self,
        project_path: Path,
        extracted_resources: Dict[str, Any]
    ) -> Dict[str, Any]:
        """验证替换结果。"""
        validation_result = {
            "valid": True,
            "issues": [],
            "warnings": [],
            "checks": {}
        }

        try:
            # 检查项目结构完整性
            await self._check_project_structure(project_path, validation_result)

            # 检查关键文件存在性
            await self._check_critical_files(project_path, validation_result)

            # 检查资源文件有效性
            await self._check_resource_files(project_path, validation_result)

            # 检查AndroidManifest.xml有效性
            await self._check_android_manifest(project_path, validation_result)

        except Exception as e:
            validation_result["valid"] = False
            validation_result["issues"].append(f"验证过程出错: {e}")

        return validation_result

    async def _check_project_structure(
        self,
        project_path: Path,
        validation_result: Dict[str, Any]
    ) -> None:
        """检查项目结构完整性。"""
        app_path = project_path / "app"
        if not app_path.exists():
            validation_result["valid"] = False
            validation_result["issues"].append("缺少app目录")
            return

        # 检查标准Android目录
        required_dirs = [
            "app/src/main",
            "app/src/main/res",
            "app/src/main/java"
        ]

        for dir_path in required_dirs:
            full_path = project_path / dir_path
            if not full_path.exists():
                validation_result["warnings"].append(f"缺少标准目录: {dir_path}")

        validation_result["checks"]["project_structure"] = "通过"

    async def _check_critical_files(
        self,
        project_path: Path,
        validation_result: Dict[str, Any]
    ) -> None:
        """检查关键文件存在性。"""
        critical_files = [
            "app/src/main/AndroidManifest.xml",
            "app/build.gradle"
        ]

        for file_path in critical_files:
            full_path = project_path / file_path
            if not full_path.exists():
                validation_result["valid"] = False
                validation_result["issues"].append(f"缺少关键文件: {file_path}")

        validation_result["checks"]["critical_files"] = "通过"

    async def _check_resource_files(
        self,
        project_path: Path,
        validation_result: Dict[str, Any]
    ) -> None:
        """检查资源文件有效性。"""
        res_path = project_path / "app" / "src" / "main" / "res"
        if not res_path.exists():
            return

        # 检查资源文件语法
        issues = []
        for root, dirs, files in os.walk(res_path):
            for file in files:
                file_path = Path(root) / file

                if file.endswith(".xml"):
                    # 验证XML文件语法
                    try:
                        import xml.etree.ElementTree as ET
                        ET.parse(file_path)
                    except ET.ParseError as e:
                        issues.append(f"XML文件语法错误 {file_path.relative_to(res_path)}: {e}")

        if issues:
            validation_result["issues"].extend(issues)

        validation_result["checks"]["resource_files"] = "通过"

    async def _check_android_manifest(
        self,
        project_path: Path,
        validation_result: Dict[str, Any]
    ) -> None:
        """检查AndroidManifest.xml有效性。"""
        manifest_path = project_path / "app" / "src" / "main" / "AndroidManifest.xml"

        if not manifest_path.exists():
            return

        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(manifest_path)
            root = tree.getroot()

            # 基本结构检查
            if root.tag != "manifest":
                validation_result["issues"].append("AndroidManifest.xml根元素不是manifest")

            # 检查package属性
            package_name = root.get("package")
            if not package_name:
                validation_result["issues"].append("AndroidManifest.xml缺少package属性")

            validation_result["checks"]["android_manifest"] = "通过"

        except Exception as e:
            validation_result["valid"] = False
            validation_result["issues"].append(f"AndroidManifest.xml验证失败: {e}")

    async def analyze_resource_package(
        self,
        resource_package_path: str
    ) -> Dict[str, Any]:
        """
        分析资源包内容（不执行替换）。

        Args:
            resource_package_path: 资源包路径

        Returns:
            分析结果
        """
        resource_package_path = Path(resource_package_path)

        if not resource_package_path.exists():
            raise ValidationError(f"资源包不存在: {resource_package_path}")

        try:
            with zipfile.ZipFile(resource_package_path, 'r') as zip_file:
                file_list = zip_file.namelist()
                structure = await self._analyze_resource_structure(file_list)

                # 获取文件统计信息
                total_size = sum(info.file_size for info in zip_file.infolist() if not info.is_dir())
                file_count = len([f for f in file_list if not f.endswith('/')])

                return {
                    "structure": structure,
                    "total_size": total_size,
                    "file_count": file_count,
                    "package_path": str(resource_package_path)
                }

        except Exception as e:
            raise BuildError(f"分析资源包失败: {e}")