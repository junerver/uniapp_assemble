"""
APK管理API端点。

提供APK文件的扫描、提取、分析和管理功能。
"""

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from ..config.database import get_async_session
from ..services.apk_service import APKService
from ..utils.exceptions import (
    BuildError,
    ValidationError,
    create_not_found_exception,
    create_validation_exception
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/apks", tags=["APK Management"])


# Pydantic models for request/response
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class APKInfoResponse(BaseModel):
    """APK信息响应模型。"""
    file_path: str
    file_name: str
    file_size: int
    modified_time: float
    created_time: float
    file_hash: str
    build_variant: str
    package_info: Optional[Dict[str, Any]] = None
    permissions: List[str] = []
    activities: List[str] = []
    services: List[str] = []
    native_libs: List[Dict[str, Any]] = []
    resources: List[Dict[str, Any]] = []
    manifest_valid: bool = False
    analysis_error: Optional[str] = None


class APKScanRequest(BaseModel):
    """APK扫描请求模型。"""
    project_id: str = Field(..., description="项目ID")
    deep_analysis: bool = Field(False, description="是否执行深度分析")
    analyze_resources: bool = Field(True, description="是否分析资源文件")
    analyze_native_libs: bool = Field(True, description="是否分析原生库")


class APKScanResponse(BaseModel):
    """APK扫描响应模型。"""
    success: bool
    apk_files: List[APKInfoResponse]
    total_count: int
    total_size: int
    scan_path: str
    extracted_at: str
    message: Optional[str] = None


class APKComparisonRequest(BaseModel):
    """APK比较请求模型。"""
    apk_file1: str = Field(..., description="第一个APK文件路径")
    apk_file2: str = Field(..., description="第二个APK文件路径")


class APKComparisonResponse(BaseModel):
    """APK比较响应模型。"""
    file1: Dict[str, Any]
    file2: Dict[str, Any]
    differences: Dict[str, Any]
    package_differences: Optional[Dict[str, Any]] = None
    permission_differences: Dict[str, Any]


# Dependency injection
async def get_apk_service(session: AsyncSession = Depends(get_async_session)) -> APKService:
    """获取APK服务实例。"""
    return APKService(session)


# API endpoints
@router.post("/scan", response_model=APKScanResponse)
async def scan_apk_files(
    request: APKScanRequest,
    service: APKService = Depends(get_apk_service)
) -> Dict[str, Any]:
    """
    扫描项目中的APK文件。

    Args:
        request: APK扫描请求
        service: APK服务

    Returns:
        扫描结果

    Raises:
        HTTPException: 扫描失败
    """
    try:
        from ..services.android_service import AndroidProjectService
        android_service = AndroidProjectService(service.session)

        # 获取项目信息
        project = await android_service.get_project(request.project_id)

        # 执行扫描
        config_options = {
            "deep_analysis": request.deep_analysis,
            "analyze_resources": request.analyze_resources,
            "analyze_native_libs": request.analyze_native_libs
        }

        result = await service.extract_apk_files(
            project.path,
            config_options
        )

        # 转换为响应格式
        apk_files = []
        for apk in result["apk_files"]:
            if "error" not in apk:
                apk_files.append(APKInfoResponse(**apk))

        response = {
            "success": result["success"],
            "apk_files": apk_files,
            "total_count": result["total_count"],
            "total_size": result["total_size"],
            "scan_path": result["scan_path"],
            "extracted_at": result["extracted_at"],
            "message": result.get("message")
        }

        logger.info(f"APK扫描完成: {request.project_id}, 找到 {result['total_count']} 个文件")
        return response

    except Exception as e:
        logger.error(f"APK扫描失败: {e}")
        raise HTTPException(status_code=500, detail=f"APK扫描失败: {str(e)}")


@router.get("/projects/{project_id}/apks", response_model=APKScanResponse)
async def get_project_apk_files(
    project_id: str,
    deep_analysis: bool = Query(False, description="是否执行深度分析"),
    analyze_resources: bool = Query(True, description="是否分析资源文件"),
    analyze_native_libs: bool = Query(True, description="是否分析原生库"),
    service: APKService = Depends(get_apk_service)
) -> Dict[str, Any]:
    """
    获取项目的APK文件列表。

    Args:
        project_id: 项目ID
        deep_analysis: 是否执行深度分析
        analyze_resources: 是否分析资源文件
        analyze_native_libs: 是否分析原生库
        service: APK服务

    Returns:
        APK文件列表

    Raises:
        HTTPException: 获取失败
    """
    try:
        from ..services.android_service import AndroidProjectService
        android_service = AndroidProjectService(service.session)

        # 获取项目信息
        project = await android_service.get_project(project_id)

        # 执行扫描
        config_options = {
            "deep_analysis": deep_analysis,
            "analyze_resources": analyze_resources,
            "analyze_native_libs": analyze_native_libs
        }

        result = await service.extract_apk_files(
            project.path,
            config_options
        )

        # 转换为响应格式
        apk_files = []
        for apk in result["apk_files"]:
            if "error" not in apk:
                apk_files.append(APKInfoResponse(**apk))

        response = {
            "success": result["success"],
            "apk_files": apk_files,
            "total_count": result["total_count"],
            "total_size": result["total_size"],
            "scan_path": result["scan_path"],
            "extracted_at": result["extracted_at"],
            "message": result.get("message")
        }

        logger.info(f"获取项目APK文件: {project_id}, 找到 {result['total_count']} 个文件")
        return response

    except Exception as e:
        logger.error(f"获取项目APK文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取项目APK文件失败: {str(e)}")


@router.get("/files/{apk_file_path:path}/info", response_model=APKInfoResponse)
async def get_apk_file_info(
    apk_file_path: str,
    service: APKService = Depends(get_apk_service)
) -> Dict[str, Any]:
    """
    获取单个APK文件的详细信息。

    Args:
        apk_file_path: APK文件路径
        service: APK服务

    Returns:
        APK文件详细信息

    Raises:
        HTTPException: 获取失败
    """
    try:
        info = await service.get_apk_info(apk_file_path)
        return APKInfoResponse(**info)

    except ValidationError as e:
        raise create_validation_exception(str(e))
    except Exception as e:
        logger.error(f"获取APK文件信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取APK文件信息失败: {str(e)}")


@router.post("/compare", response_model=APKComparisonResponse)
async def compare_apk_files(
    request: APKComparisonRequest,
    service: APKService = Depends(get_apk_service)
) -> Dict[str, Any]:
    """
    比较两个APK文件的差异。

    Args:
        request: APK比较请求
        service: APK服务

    Returns:
        比较结果

    Raises:
        HTTPException: 比较失败
    """
    try:
        comparison = await service.compare_apk_files(
            request.apk_file1,
            request.apk_file2
        )

        logger.info(f"APK比较完成: {request.apk_file1} vs {request.apk_file2}")
        return APKComparisonResponse(**comparison)

    except ValidationError as e:
        raise create_validation_exception(str(e))
    except Exception as e:
        logger.error(f"APK比较失败: {e}")
        raise HTTPException(status_code=500, detail=f"APK比较失败: {str(e)}")


@router.get("/projects/{project_id}/latest-apk")
async def get_latest_apk(
    project_id: str,
    build_variant: Optional[str] = Query(None, description="构建变体过滤"),
    service: APKService = Depends(get_apk_service)
) -> Dict[str, Any]:
    """
    获取项目的最新APK文件。

    Args:
        project_id: 项目ID
        build_variant: 构建变体过滤
        service: APK服务

    Returns:
        最新APK文件信息

    Raises:
        HTTPException: 获取失败
    """
    try:
        from ..services.android_service import AndroidProjectService
        android_service = AndroidProjectService(service.session)

        # 获取项目信息
        project = await android_service.get_project(project_id)

        # 扫描APK文件
        result = await service.extract_apk_files(project.path, {"deep_analysis": False})

        if not result["apk_files"]:
            raise HTTPException(status_code=404, detail="未找到APK文件")

        # 过滤和排序
        apk_files = result["apk_files"]
        if build_variant:
            apk_files = [apk for apk in apk_files if apk.get("build_variant") == build_variant]

        if not apk_files:
            raise HTTPException(status_code=404, detail=f"未找到匹配构建变体 {build_variant} 的APK文件")

        # 获取最新的文件
        latest_apk = max(apk_files, key=lambda x: x.get("modified_time", 0))

        logger.info(f"获取最新APK: {project_id} -> {latest_apk['file_name']}")
        return latest_apk

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取最新APK失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取最新APK失败: {str(e)}")


@router.get("/projects/{project_id}/build-variants")
async def get_project_build_variants(
    project_id: str,
    service: APKService = Depends(get_apk_service)
) -> Dict[str, Any]:
    """
    获取项目的所有构建变体。

    Args:
        project_id: 项目ID
        service: APK服务

    Returns:
        构建变体列表

    Raises:
        HTTPException: 获取失败
    """
    try:
        from ..services.android_service import AndroidProjectService
        android_service = AndroidProjectService(service.session)

        # 获取项目信息
        project = await android_service.get_project(project_id)

        # 扫描APK文件
        result = await service.extract_apk_files(project.path, {"deep_analysis": False})

        if not result["apk_files"]:
            return {"build_variants": [], "total_count": 0}

        # 收集构建变体
        variants = {}
        for apk in result["apk_files"]:
            variant = apk.get("build_variant", "unknown")
            if variant not in variants:
                variants[variant] = {
                    "name": variant,
                    "count": 0,
                    "total_size": 0,
                    "latest_file": None,
                    "files": []
                }

            variants[variant]["count"] += 1
            variants[variant]["total_size"] += apk.get("file_size", 0)
            variants[variant]["files"].append(apk)

            # 更新最新文件
            current_latest = variants[variant]["latest_file"]
            if (not current_latest or
                apk.get("modified_time", 0) > current_latest.get("modified_time", 0)):
                variants[variant]["latest_file"] = apk

        # 转换为列表并排序
        variant_list = list(variants.values())
        variant_list.sort(key=lambda x: x["count"], reverse=True)

        logger.info(f"获取构建变体: {project_id}, 找到 {len(variant_list)} 个变体")
        return {
            "build_variants": variant_list,
            "total_count": len(variant_list)
        }

    except Exception as e:
        logger.error(f"获取构建变体失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取构建变体失败: {str(e)}")


@router.delete("/files/{apk_file_path:path}")
async def delete_apk_file(
    apk_file_path: str,
    confirm: bool = Query(False, description="确认删除"),
    service: APKService = Depends(get_apk_service)
) -> Dict[str, Any]:
    """
    删除APK文件。

    Args:
        apk_file_path: APK文件路径
        confirm: 确认删除
        service: APK服务

    Returns:
        删除结果

    Raises:
        HTTPException: 删除失败
    """
    if not confirm:
        raise HTTPException(status_code=400, detail="请确认删除操作")

    try:
        import os
        from pathlib import Path

        file_path = Path(apk_file_path)

        if not file_path.exists():
            raise create_not_found_exception("APK文件", apk_file_path)

        # 删除文件
        os.remove(file_path)

        logger.info(f"删除APK文件: {apk_file_path}")
        return {
            "message": "APK文件已删除",
            "file_path": apk_file_path
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除APK文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除APK文件失败: {str(e)}")


@router.get("/stats")
async def get_apk_stats(
    service: APKService = Depends(get_apk_service)
) -> Dict[str, Any]:
    """
    获取APK统计信息。

    Args:
        service: APK服务

    Returns:
        APK统计信息

    Raises:
        HTTPException: 获取失败
    """
    try:
        # 这里可以实现全局APK统计功能
        # 由于当前设计是基于项目的，这里返回基本统计信息

        stats = {
            "total_projects": 0,  # 需要从项目表获取
            "total_apks": 0,
            "total_size": 0,
            "common_build_variants": [],
            "recent_scans": []
        }

        logger.info("获取APK统计信息")
        return stats

    except Exception as e:
        logger.error(f"获取APK统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取APK统计失败: {str(e)}")