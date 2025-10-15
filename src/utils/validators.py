"""
数据验证工具模块。

提供资源包验证、文件路径验证和输入数据验证功能。
"""

import logging
import re
import zipfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Set

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """验证错误基类。"""
    pass


class ResourcePackageValidator:
    """资源包验证器。"""

    # Android资源文件扩展名
    VALID_RESOURCE_EXTENSIONS: Set[str] = {
        '.xml',      # 布局、值、动画等
        '.png',      # 图片资源
        '.jpg',      # 图片资源
        '.jpeg',     # 图片资源
        '.webp',     # 图片资源
        '.9.png',    # 9-patch图片
        '.gif',      # 动画图片
        '.svg',      # 矢量图形
        '.json',     # 配置文件
        '.ttf',      # 字体文件
        '.otf',      # 字体文件
        '.mp3',      # 音频资源
        '.wav',      # 音频资源
        '.ogg',      # 音频资源
        '.mp4',      # 视频资源
        '.avi',      # 视频资源
    }

    # Android资源目录名称
    VALID_RESOURCE_DIRS: Set[str] = {
        'drawable', 'drawable-hdpi', 'drawable-mdpi', 'drawable-xhdpi',
        'drawable-xxhdpi', 'drawable-xxxhdpi', 'drawable-nodpi',
        'mipmap', 'mipmap-hdpi', 'mipmap-mdpi', 'mipmap-xhdpi',
        'mipmap-xxhdpi', 'mipmap-xxxhdpi',
        'layout', 'layout-land', 'layout-port', 'layout-sw600dp',
        'values', 'values-zh', 'values-en', 'values-night',
        'anim', 'animator', 'color', 'font', 'menu', 'raw', 'xml'
    }

    @staticmethod
    def validate_zip_file(file_path: str | Path) -> Dict[str, Any]:
        """
        验证ZIP文件是否有效且可以解压。

        Args:
            file_path: ZIP文件路径

        Returns:
            验证结果字典，包含：
            - is_valid: 是否有效
            - file_count: 文件数量
            - total_size: 总大小（字节）
            - errors: 错误列表

        Raises:
            ValidationError: 如果文件不存在或无法读取
        """
        errors = []
        file_count = 0
        total_size = 0

        try:
            path = Path(file_path)
            if not path.exists():
                raise ValidationError(f"文件不存在: {file_path}")

            if not path.is_file():
                raise ValidationError(f"不是文件: {file_path}")

            # 检查文件扩展名
            if path.suffix.lower() not in {'.zip', '.rar', '.7z'}:
                errors.append(f"不支持的压缩文件类型: {path.suffix}")

            # 尝试打开ZIP文件
            try:
                with zipfile.ZipFile(path, 'r') as zip_file:
                    # 测试ZIP完整性
                    bad_file = zip_file.testzip()
                    if bad_file:
                        errors.append(f"ZIP文件损坏，首个损坏文件: {bad_file}")

                    # 统计文件信息
                    for info in zip_file.infolist():
                        if not info.is_dir():
                            file_count += 1
                            total_size += info.file_size

            except zipfile.BadZipFile:
                errors.append("无效的ZIP文件格式")
            except Exception as e:
                errors.append(f"读取ZIP文件失败: {str(e)}")

            return {
                "is_valid": len(errors) == 0,
                "file_count": file_count,
                "total_size": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "errors": errors
            }

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"验证ZIP文件失败: {e}")
            raise ValidationError(f"验证ZIP文件失败: {str(e)}")

    @staticmethod
    def validate_resource_package(file_path: str | Path) -> Dict[str, Any]:
        """
        验证资源包是否符合Android资源结构。

        Args:
            file_path: 资源包文件路径

        Returns:
            验证结果字典，包含：
            - is_valid: 是否有效
            - has_resources: 是否包含Android资源文件
            - resource_dirs: 发现的资源目录列表
            - resource_files: 资源文件数量
            - warnings: 警告列表
            - errors: 错误列表

        Raises:
            ValidationError: 如果文件不存在或无法读取
        """
        errors = []
        warnings = []
        resource_dirs = set()
        resource_files = 0

        try:
            path = Path(file_path)

            # 首先验证ZIP文件完整性
            zip_validation = ResourcePackageValidator.validate_zip_file(path)
            if not zip_validation["is_valid"]:
                errors.extend(zip_validation["errors"])
                return {
                    "is_valid": False,
                    "has_resources": False,
                    "resource_dirs": [],
                    "resource_files": 0,
                    "warnings": warnings,
                    "errors": errors
                }

            # 检查资源结构
            with zipfile.ZipFile(path, 'r') as zip_file:
                file_list = zip_file.namelist()

                for file_name in file_list:
                    file_path_obj = Path(file_name)

                    # 跳过目录项
                    if file_name.endswith('/'):
                        continue

                    # 检查文件扩展名
                    if file_path_obj.suffix.lower() in ResourcePackageValidator.VALID_RESOURCE_EXTENSIONS:
                        resource_files += 1

                        # 检查是否在有效的资源目录中
                        parts = file_path_obj.parts
                        for part in parts:
                            # 检查目录名是否匹配资源目录模式
                            if any(part.startswith(res_dir) for res_dir in ResourcePackageValidator.VALID_RESOURCE_DIRS):
                                resource_dirs.add(part)

            # 添加警告
            if resource_files == 0:
                warnings.append("未发现任何Android资源文件")

            if len(resource_dirs) == 0:
                warnings.append("未发现标准Android资源目录结构")

            # 资源包大小检查
            if zip_validation["total_size"] > 500 * 1024 * 1024:  # 500MB
                warnings.append(f"资源包较大 ({zip_validation['total_size_mb']} MB)，可能影响处理速度")

            return {
                "is_valid": len(errors) == 0,
                "has_resources": resource_files > 0,
                "resource_dirs": sorted(list(resource_dirs)),
                "resource_files": resource_files,
                "total_files": zip_validation["file_count"],
                "total_size_mb": zip_validation["total_size_mb"],
                "warnings": warnings,
                "errors": errors
            }

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"验证资源包失败: {e}")
            raise ValidationError(f"验证资源包失败: {str(e)}")


class PathValidator:
    """路径验证器。"""

    @staticmethod
    def is_safe_path(base_path: str | Path, target_path: str | Path) -> bool:
        """
        检查目标路径是否在基础路径内（防止路径遍历攻击）。

        Args:
            base_path: 基础路径
            target_path: 目标路径

        Returns:
            如果路径安全返回True，否则返回False
        """
        try:
            base = Path(base_path).resolve()
            target = Path(target_path).resolve()

            # 检查target是否在base内
            return str(target).startswith(str(base))
        except Exception as e:
            logger.warning(f"路径安全检查失败: {e}")
            return False

    @staticmethod
    def validate_project_path(path: str | Path) -> Dict[str, Any]:
        """
        验证Android项目路径是否有效。

        Args:
            path: 项目路径

        Returns:
            验证结果字典
        """
        errors = []
        warnings = []

        try:
            project_path = Path(path)

            # 检查路径是否存在
            if not project_path.exists():
                errors.append(f"路径不存在: {path}")
                return {
                    "is_valid": False,
                    "is_android_project": False,
                    "errors": errors,
                    "warnings": warnings
                }

            # 检查是否为目录
            if not project_path.is_dir():
                errors.append(f"不是目录: {path}")
                return {
                    "is_valid": False,
                    "is_android_project": False,
                    "errors": errors,
                    "warnings": warnings
                }

            # 检查Android项目标识文件
            has_build_gradle = (project_path / "build.gradle").exists() or (project_path / "build.gradle.kts").exists()
            has_settings_gradle = (project_path / "settings.gradle").exists() or (project_path / "settings.gradle.kts").exists()
            has_app_module = (project_path / "app").exists()

            is_android_project = has_build_gradle or has_settings_gradle

            if not is_android_project:
                warnings.append("未检测到Android项目标识文件（build.gradle或settings.gradle）")

            if not has_app_module:
                warnings.append("未检测到app模块目录")

            return {
                "is_valid": len(errors) == 0,
                "is_android_project": is_android_project,
                "has_build_gradle": has_build_gradle,
                "has_settings_gradle": has_settings_gradle,
                "has_app_module": has_app_module,
                "errors": errors,
                "warnings": warnings
            }

        except Exception as e:
            logger.error(f"验证项目路径失败: {e}")
            return {
                "is_valid": False,
                "is_android_project": False,
                "errors": [f"验证失败: {str(e)}"],
                "warnings": warnings
            }


class InputValidator:
    """输入数据验证器。"""

    @staticmethod
    def validate_project_name(name: str) -> bool:
        """
        验证项目名称是否有效。

        Args:
            name: 项目名称

        Returns:
            如果名称有效返回True，否则返回False
        """
        if not name or len(name.strip()) == 0:
            return False

        # 项目名称规则：1-100字符，字母、数字、下划线、中划线
        pattern = r'^[a-zA-Z0-9_\-\u4e00-\u9fa5]{1,100}$'
        return re.match(pattern, name) is not None

    @staticmethod
    def validate_branch_name(name: str) -> bool:
        """
        验证Git分支名称是否有效。

        Args:
            name: 分支名称

        Returns:
            如果名称有效返回True，否则返回False
        """
        if not name or len(name.strip()) == 0:
            return False

        # Git分支名称规则（简化版）
        # 不能包含空格、~、^、:、?、*、[、\、连续点号..等
        invalid_chars = {' ', '~', '^', ':', '?', '*', '[', '\\'}
        if any(char in name for char in invalid_chars):
            return False

        if '..' in name or name.startswith('.') or name.endswith('.'):
            return False

        return True

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        清理文件名，移除不安全字符。

        Args:
            filename: 原始文件名

        Returns:
            清理后的文件名
        """
        # 移除路径分隔符
        sanitized = filename.replace('/', '_').replace('\\', '_')

        # 移除其他不安全字符
        unsafe_chars = '<>:"|?*'
        for char in unsafe_chars:
            sanitized = sanitized.replace(char, '_')

        # 移除前导/尾随空格和点号
        sanitized = sanitized.strip(' .')

        return sanitized
