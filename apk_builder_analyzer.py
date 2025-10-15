"""
APK构建结果解析和分析模块
提供APK文件检测、信息提取、质量分析等功能
"""

import asyncio
import json
import re
import subprocess
import tempfile
import zipfile
from typing import Dict, Any, List, Optional, Tuple, Union
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
import xml.etree.ElementTree as ET
import logging

logger = logging.getLogger(__name__)


@dataclass
class APKInfo:
    """APK文件信息"""
    file_path: str
    file_size: int
    package_name: str
    version_name: str
    version_code: int
    min_sdk_version: int
    target_sdk_version: int
    max_sdk_version: Optional[int]
    permissions: List[str]
    activities: List[str]
    services: List[str]
    receivers: List[str]
    providers: List[str]
    application_label: str
    icon_path: Optional[str]
    debuggable: bool
    allow_backup: bool
    uses_cleartext_traffic: bool
    build_time: Optional[datetime]
    signature_info: Dict[str, Any] = field(default_factory=dict)
    native_libraries: List[str] = field(default_factory=list)
    dex_files: List[str] = field(default_factory=list)


@dataclass
class BuildAnalysis:
    """构建分析结果"""
    build_id: str
    success: bool
    build_duration: float
    apk_info: Optional[APKInfo]
    warnings: List[str]
    errors: List[str]
    performance_metrics: Dict[str, Any]
    quality_score: float
    recommendations: List[str]


class APKAnalyzer:
    """APK分析器"""

    def __init__(self, aapt_path: Optional[str] = None):
        self.aapt_path = aapt_path or self._find_aapt()
        self.temp_dir = Path(tempfile.gettempdir()) / "apk_analysis"
        self.temp_dir.mkdir(exist_ok=True)

    def _find_aapt(self) -> Optional[str]:
        """查找AAPT工具路径"""
        possible_paths = [
            # Android SDK paths
            "/opt/android-sdk/build-tools/*/aapt",
            "/opt/android-sdk/build-tools/*/aapt2",
            "~/Android/Sdk/build-tools/*/aapt",
            "~/Android/Sdk/build-tools/*/aapt2",
            # System paths
            "/usr/bin/aapt",
            "/usr/local/bin/aapt",
            # Windows paths
            "C:\\Android\\Sdk\\build-tools\\*\\aapt.exe",
            "C:\\Android\\Sdk\\build-tools\\*\\aapt2.exe"
        ]

        import glob
        for pattern in possible_paths:
            matches = glob.glob(pattern)
            if matches:
                return matches[0]

        return None

    async def analyze_apk(self, apk_path: str) -> Optional[APKInfo]:
        """分析APK文件"""
        apk_file = Path(apk_path)

        if not apk_file.exists():
            logger.error(f"APK文件不存在: {apk_path}")
            return None

        try:
            # 基本文件信息
            file_size = apk_file.stat().st_size

            # 使用AAPT获取详细信息
            aapt_info = await self._get_aapt_info(apk_path)

            # 解析AndroidManifest.xml
            manifest_info = await self._parse_manifest(apk_path)

            # 分析DEX文件
            dex_info = await self._analyze_dex_files(apk_path)

            # 分析native库
            native_info = await self._analyze_native_libraries(apk_path)

            # 合并信息
            apk_info = APKInfo(
                file_path=str(apk_file),
                file_size=file_size,
                package_name=manifest_info.get('package', ''),
                version_name=manifest_info.get('versionName', ''),
                version_code=int(manifest_info.get('versionCode', 0)),
                min_sdk_version=int(manifest_info.get('minSdkVersion', 0)),
                target_sdk_version=int(manifest_info.get('targetSdkVersion', 0)),
                max_sdk_version=manifest_info.get('maxSdkVersion'),
                permissions=manifest_info.get('permissions', []),
                activities=manifest_info.get('activities', []),
                services=manifest_info.get('services', []),
                receivers=manifest_info.get('receivers', []),
                providers=manifest_info.get('providers', []),
                application_label=manifest_info.get('label', ''),
                icon_path=manifest_info.get('icon'),
                debuggable=manifest_info.get('debuggable', False),
                allow_backup=manifest_info.get('allowBackup', True),
                uses_cleartext_traffic=manifest_info.get('usesCleartextTraffic', False),
                build_time=await self._get_build_time(apk_path),
                signature_info=await self._analyze_signature(apk_path),
                native_libraries=native_info.get('libraries', []),
                dex_files=dex_info.get('files', [])
            )

            return apk_info

        except Exception as e:
            logger.error(f"分析APK失败: {apk_path}, 错误: {e}")
            return None

    async def _get_aapt_info(self, apk_path: str) -> Dict[str, Any]:
        """使用AAPT获取APK信息"""
        if not self.aapt_path:
            return {}

        try:
            cmd = [self.aapt_path, 'dump', 'badging', apk_path]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error(f"AAPT分析失败: {stderr.decode()}")
                return {}

            output = stdout.decode('utf-8')
            return self._parse_aapt_output(output)

        except Exception as e:
            logger.error(f"AAPT分析错误: {e}")
            return {}

    def _parse_aapt_output(self, output: str) -> Dict[str, Any]:
        """解析AAPT输出"""
        info = {}

        # 解析包名和版本
        package_match = re.search(r'package: name=\'([^\']+)\' versionCode=\'(\d+)\' versionName=\'([^\']+)\'', output)
        if package_match:
            info['package'] = package_match.group(1)
            info['versionCode'] = int(package_match.group(2))
            info['versionName'] = package_match.group(3)

        # 解析SDK版本
        sdk_match = re.search(r'sdkVersion:\'(\d+)\'', output)
        if sdk_match:
            info['minSdkVersion'] = int(sdk_match.group(1))

        target_sdk_match = re.search(r'targetSdkVersion:\'(\d+)\'', output)
        if target_sdk_match:
            info['targetSdkVersion'] = int(target_sdk_match.group(1))

        # 解析权限
        permissions = re.findall(r'uses-permission: name=\'([^\']+)\'', output)
        info['permissions'] = permissions

        # 解析应用标签
        label_match = re.search(r'application-label:\'([^\']+)\'', output)
        if label_match:
            info['label'] = label_match.group(1)

        # 解析图标
        icon_match = re.search(r'application-icon-\d+:\'([^\']+)\'', output)
        if icon_match:
            info['icon'] = icon_match.group(1)

        return info

    async def _parse_manifest(self, apk_path: str) -> Dict[str, Any]:
        """解析AndroidManifest.xml"""
        manifest_info = {}

        try:
            with zipfile.ZipFile(apk_path, 'r') as zip_file:
                # 查找AndroidManifest.xml
                manifest_path = None
                for name in zip_file.namelist():
                    if name.endswith('AndroidManifest.xml'):
                        manifest_path = name
                        break

                if not manifest_path:
                    return manifest_info

                # 提取并解析manifest
                with zip_file.open(manifest_path) as manifest_file:
                    content = manifest_file.read()

                # 这里需要使用AXMLPrinter或其他工具来解析二进制XML
                # 简化版本：使用aapt获取信息
                aapt_info = await self._get_aapt_info(apk_path)
                manifest_info.update(aapt_info)

                # 解析组件
                await self._parse_components(content, manifest_info)

        except Exception as e:
            logger.error(f"解析manifest失败: {e}")

        return manifest_info

    async def _parse_components(self, content: bytes, info: Dict[str, Any]):
        """解析Android组件"""
        # 简化实现，实际需要AXML解析器
        # 这里只是示例结构
        info['activities'] = []
        info['services'] = []
        info['receivers'] = []
        info['providers'] = []

    async def _analyze_dex_files(self, apk_path: str) -> Dict[str, Any]:
        """分析DEX文件"""
        dex_info = {'files': [], 'count': 0}

        try:
            with zipfile.ZipFile(apk_path, 'r') as zip_file:
                for name in zip_file.namelist():
                    if name.endswith('.dex'):
                        dex_info['files'].append(name)
                        dex_info['count'] += 1

        except Exception as e:
            logger.error(f"分析DEX文件失败: {e}")

        return dex_info

    async def _analyze_native_libraries(self, apk_path: str) -> Dict[str, Any]:
        """分析native库"""
        native_info = {'libraries': [], 'architectures': set()}

        try:
            with zipfile.ZipFile(apk_path, 'r') as zip_file:
                for name in zip_file.namelist():
                    if name.startswith('lib/') and name.endswith('.so'):
                        parts = name.split('/')
                        if len(parts) >= 3:
                            arch = parts[1]
                            lib_name = parts[2]

                            native_info['libraries'].append({
                                'name': lib_name,
                                'architecture': arch,
                                'path': name
                            })
                            native_info['architectures'].add(arch)

        except Exception as e:
            logger.error(f"分析native库失败: {e}")

        native_info['architectures'] = list(native_info['architectures'])
        return native_info

    async def _get_build_time(self, apk_path: str) -> Optional[datetime]:
        """获取构建时间"""
        try:
            # 获取APK文件的修改时间
            file_path = Path(apk_path)
            timestamp = file_path.stat().st_mtime
            return datetime.fromtimestamp(timestamp)

        except Exception as e:
            logger.error(f"获取构建时间失败: {e}")
            return None

    async def _analyze_signature(self, apk_path: str) -> Dict[str, Any]:
        """分析签名信息"""
        signature_info = {}

        try:
            # 使用apksigner或其他工具分析签名
            # 这里是简化实现
            signature_info = {
                'signed': True,
                'algorithm': 'unknown',
                'issuer': 'unknown'
            }

        except Exception as e:
            logger.error(f"分析签名失败: {e}")

        return signature_info


class BuildResultAnalyzer:
    """构建结果分析器"""

    def __init__(self):
        self.apk_analyzer = APKAnalyzer()
        self.quality_thresholds = {
            'max_apk_size': 50 * 1024 * 1024,  # 50MB
            'max_permissions': 50,
            'max_activities': 100,
            'min_target_sdk': 30,
            'recommended_min_sdk': 21
        }

    async def analyze_build_result(
        self,
        build_id: str,
        apk_path: Optional[str],
        build_logs: List[str],
        build_duration: float
    ) -> BuildAnalysis:
        """分析构建结果"""

        warnings = []
        errors = []
        recommendations = []
        performance_metrics = {}

        # 分析APK
        apk_info = None
        if apk_path and Path(apk_path).exists():
            apk_info = await self.apk_analyzer.analyze_apk(apk_path)
            if apk_info:
                warnings.extend(self._analyze_apk_quality(apk_info))
                recommendations.extend(self._generate_recommendations(apk_info))
                performance_metrics.update(self._calculate_performance_metrics(apk_info))

        # 分析构建日志
        log_warnings, log_errors = self._analyze_build_logs(build_logs)
        warnings.extend(log_warnings)
        errors.extend(log_errors)

        # 计算质量分数
        quality_score = self._calculate_quality_score(apk_info, warnings, errors, build_duration)

        return BuildAnalysis(
            build_id=build_id,
            success=apk_info is not None and len(errors) == 0,
            build_duration=build_duration,
            apk_info=apk_info,
            warnings=warnings,
            errors=errors,
            performance_metrics=performance_metrics,
            quality_score=quality_score,
            recommendations=recommendations
        )

    def _analyze_apk_quality(self, apk_info: APKInfo) -> List[str]:
        """分析APK质量"""
        warnings = []

        # 检查文件大小
        if apk_info.file_size > self.quality_thresholds['max_apk_size']:
            warnings.append(f"APK文件过大: {apk_info.file_size / (1024*1024):.1f}MB")

        # 检查权限数量
        if len(apk_info.permissions) > self.quality_thresholds['max_permissions']:
            warnings.append(f"权限过多: {len(apk_info.permissions)}个")

        # 检查目标SDK版本
        if apk_info.target_sdk_version < self.quality_thresholds['min_target_sdk']:
            warnings.append(f"目标SDK版本过低: {apk_info.target_sdk_version}")

        # 检查调试模式
        if apk_info.debuggable:
            warnings.append("应用处于调试模式，生产环境应禁用")

        # 检查备份权限
        if apk_info.allow_backup:
            warnings.append("允许备份，可能存在安全风险")

        # 检查明文流量
        if apk_info.uses_cleartext_traffic:
            warnings.append("允许明文流量，存在安全风险")

        # 检查native库
        if not apk_info.native_libraries:
            warnings.append("未检测到native库，可能影响性能")

        return warnings

    def _generate_recommendations(self, apk_info: APKInfo) -> List[str]:
        """生成优化建议"""
        recommendations = []

        # APK大小优化
        if apk_info.file_size > 20 * 1024 * 1024:
            recommendations.append("考虑使用ProGuard/R8进行代码混淆和压缩")
            recommendations.append("优化图片资源，使用WebP格式")
            recommendations.append("移除未使用的资源和库")

        # 权限优化
        if len(apk_info.permissions) > 20:
            recommendations.append("审查权限使用，移除不必要的权限")

        # 版本建议
        if apk_info.target_sdk_version < 33:
            recommendations.append("建议更新目标SDK版本到最新版本")

        # 安全建议
        if apk_info.debuggable:
            recommendations.append("生产环境必须禁用调试模式")

        if apk_info.allow_backup:
            recommendations.append("考虑禁用备份功能以提高安全性")

        return recommendations

    def _calculate_performance_metrics(self, apk_info: APKInfo) -> Dict[str, Any]:
        """计算性能指标"""
        metrics = {}

        # 文件大小分级
        size_mb = apk_info.file_size / (1024 * 1024)
        if size_mb < 10:
            metrics['size_grade'] = 'excellent'
        elif size_mb < 25:
            metrics['size_grade'] = 'good'
        elif size_mb < 50:
            metrics['size_grade'] = 'acceptable'
        else:
            metrics['size_grade'] = 'poor'

        # 权限评分
        perm_count = len(apk_info.permissions)
        if perm_count < 10:
            metrics['permission_grade'] = 'excellent'
        elif perm_count < 25:
            metrics['permission_grade'] = 'good'
        elif perm_count < 50:
            metrics['permission_grade'] = 'acceptable'
        else:
            metrics['permission_grade'] = 'poor'

        # 架构支持
        arch_count = len(set(lib['architecture'] for lib in apk_info.native_libraries))
        metrics['architecture_support'] = {
            'count': arch_count,
            'architectures': list(set(lib['architecture'] for lib in apk_info.native_libraries))
        }

        # 组件复杂度
        total_components = (len(apk_info.activities) +
                           len(apk_info.services) +
                           len(apk_info.receivers) +
                           len(apk_info.providers))
        metrics['component_complexity'] = {
            'total': total_components,
            'activities': len(apk_info.activities),
            'services': len(apk_info.services),
            'receivers': len(apk_info.receivers),
            'providers': len(apk_info.providers)
        }

        return metrics

    def _analyze_build_logs(self, logs: List[str]) -> Tuple[List[str], List[str]]:
        """分析构建日志"""
        warnings = []
        errors = []

        warning_patterns = [
            r'WARNING:',
            r'deprecated',
            r'obsolete',
            r'unsupported'
        ]

        error_patterns = [
            r'ERROR:',
            r'FAILED:',
            r'Exception:',
            r'error: failed',
            r'Build failed'
        ]

        for log_line in logs:
            log_line_lower = log_line.lower()

            # 检查警告
            for pattern in warning_patterns:
                if re.search(pattern, log_line_lower):
                    warnings.append(log_line.strip())
                    break

            # 检查错误
            for pattern in error_patterns:
                if re.search(pattern, log_line_lower):
                    errors.append(log_line.strip())
                    break

        return warnings, errors

    def _calculate_quality_score(
        self,
        apk_info: Optional[APKInfo],
        warnings: List[str],
        errors: List[str],
        build_duration: float
    ) -> float:
        """计算质量分数 (0-100)"""
        if not apk_info or errors:
            return 0.0

        score = 100.0

        # 错误扣分
        score -= len(errors) * 20

        # 警告扣分
        score -= len(warnings) * 5

        # APK大小扣分
        size_mb = apk_info.file_size / (1024 * 1024)
        if size_mb > 50:
            score -= 30
        elif size_mb > 25:
            score -= 15
        elif size_mb > 10:
            score -= 5

        # 权限数量扣分
        if len(apk_info.permissions) > 50:
            score -= 20
        elif len(apk_info.permissions) > 25:
            score -= 10

        # SDK版本扣分
        if apk_info.target_sdk_version < 30:
            score -= 15

        # 构建时间影响
        if build_duration > 600:  # 10分钟
            score -= 10
        elif build_duration > 300:  # 5分钟
            score -= 5

        return max(0.0, min(100.0, score))


class APKDetector:
    """APK文件检测器"""

    @staticmethod
    def find_apk_files(project_path: str) -> List[str]:
        """查找项目中的APK文件"""
        apk_files = []
        project_root = Path(project_path)

        # 常见的APK输出目录
        search_paths = [
            project_root / "app" / "build" / "outputs" / "apk",
            project_root / "build" / "outputs" / "apk",
            project_root / "outputs" / "apk"
        ]

        for search_path in search_paths:
            if search_path.exists():
                apk_files.extend(
                    str(f) for f in search_path.rglob("*.apk")
                    if f.is_file()
                )

        return apk_files

    @staticmethod
    def get_latest_apk(apk_files: List[str]) -> Optional[str]:
        """获取最新的APK文件"""
        if not apk_files:
            return None

        latest_apk = None
        latest_time = 0

        for apk_file in apk_files:
            file_path = Path(apk_file)
            if file_path.exists():
                mtime = file_path.stat().st_mtime
                if mtime > latest_time:
                    latest_time = mtime
                    latest_apk = apk_file

        return latest_apk

    @staticmethod
    def validate_apk(apk_path: str) -> Tuple[bool, str]:
        """验证APK文件"""
        apk_file = Path(apk_path)

        if not apk_file.exists():
            return False, "APK文件不存在"

        if not apk_file.suffix.lower() == '.apk':
            return False, "文件扩展名不是.apk"

        if apk_file.stat().st_size == 0:
            return False, "APK文件为空"

        try:
            with zipfile.ZipFile(apk_path, 'r') as zip_file:
                # 检查必要文件
                required_files = ['AndroidManifest.xml']
                for required_file in required_files:
                    if not any(f.endswith(required_file) for f in zip_file.namelist()):
                        return False, f"缺少必要文件: {required_file}"

                # 检查classes.dex
                dex_files = [f for f in zip_file.namelist() if f.endswith('.dex')]
                if not dex_files:
                    return False, "APK中没有找到DEX文件"

            return True, "APK文件有效"

        except zipfile.BadZipFile:
            return False, "APK文件损坏"
        except Exception as e:
            return False, f"验证APK时出错: {str(e)}"


# 使用示例
async def example_apk_analysis():
    """APK分析示例"""

    # 创建分析器
    analyzer = BuildResultAnalyzer()

    # 模拟构建结果
    build_id = "build_001"
    apk_path = "/path/to/app.apk"  # 替换为实际APK路径
    build_logs = [
        "Task :app:compileDebugKotlin",
        "Task :app:processDebugResources",
        "Task :app:packageDebug",
        "BUILD SUCCESSFUL in 2m 15s"
    ]
    build_duration = 135.0

    # 分析构建结果
    analysis = await analyzer.analyze_build_result(
        build_id,
        apk_path,
        build_logs,
        build_duration
    )

    print(f"构建ID: {analysis.build_id}")
    print(f"构建成功: {analysis.success}")
    print(f"质量分数: {analysis.quality_score:.1f}")
    print(f"构建时长: {analysis.build_duration:.1f}秒")

    if analysis.apk_info:
        apk = analysis.apk_info
        print(f"包名: {apk.package_name}")
        print(f"版本: {apk.version_name} ({apk.version_code})")
        print(f"文件大小: {apk.file_size / (1024*1024):.1f}MB")
        print(f"权限数量: {len(apk.permissions)}")

    print(f"警告数量: {len(analysis.warnings)}")
    for warning in analysis.warnings:
        print(f"  - {warning}")

    print(f"错误数量: {len(analysis.errors)}")
    for error in analysis.errors:
        print(f"  - {error}")

    print(f"优化建议:")
    for recommendation in analysis.recommendations:
        print(f"  - {recommendation}")


if __name__ == "__main__":
    asyncio.run(example_apk_analysis())