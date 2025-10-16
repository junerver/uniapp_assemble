"""
构建结果 API。

提供构建产物的查询、下载和管理功能。
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..config.database import get_async_session
from ..models.build_result import BuildResult, FileType
from ..services.apk_service import APKService
from ..services.build_service import BuildService
from ..utils.exceptions import (
    BuildError,
    ValidationError,
    create_not_found_exception,
    handle_service_error
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/results", tags=["构建结果"])


class BuildResultResponse(BaseModel):
    """构建结果响应模型。"""
    id: str
    build_task_id: str
    file_type: str
    file_path: str
    filename: str
    file_size: int
    file_size_mb: float
    file_hash: Optional[str]
    metadata: Optional[Dict[str, Any]]
    created_at: Optional[str]

    @classmethod
    def from_build_result(cls, build_result: BuildResult) -> "BuildResultResponse":
        """从BuildResult模型创建响应对象。"""
        return cls(**build_result.to_dict())


class APKInfoResponse(BaseModel):
    """APK信息响应模型。"""
    file_name: str
    file_path: str
    file_size: int
    file_size_mb: float
    file_hash: Optional[str]
    build_variant: Optional[str]
    package_info: Optional[Dict[str, Any]]
    permissions: List[str]
    activities: List[str]
    services: List[str]
    native_libs: List[Dict[str, Any]]
    resources: List[Dict[str, Any]]
    manifest_valid: bool
    created_at: Optional[str]


class BuildResultsListResponse(BaseModel):
    """构建结果列表响应模型。"""
    build_task_id: str
    total_count: int
    apk_count: int
    log_count: int
    metadata_count: int
    total_size: int
    results: List[BuildResultResponse]


def get_apk_service(session=Depends(get_async_session)) -> APKService:
    """获取APK服务实例。"""
    return APKService(session)


def get_build_service(session=Depends(get_async_session)) -> BuildService:
    """获取构建服务实例。"""
    return BuildService(session)


@router.get("/tasks/{task_id}/results", response_model=BuildResultsListResponse)
async def get_build_results(
    task_id: str,
    file_type: Optional[str] = Query(None, description="文件类型过滤 (apk/log/metadata)"),
    service: APKService = Depends(get_apk_service)
) -> BuildResultsListResponse:
    """
    获取构建任务的产物列表。

    Args:
        task_id: 任务ID
        file_type: 文件类型过滤
        service: APK服务

    Returns:
        构建结果列表

    Raises:
        HTTPException: 获取失败
    """
    try:
        # 获取所有构建结果
        all_results = await service.get_build_results(task_id)

        # 按文件类型过滤
        if file_type:
            all_results = [
                result for result in all_results
                if result.get("file_type") == file_type
            ]

        # 统计信息
        apk_count = len([r for r in all_results if r.get("file_type") == "apk"])
        log_count = len([r for r in all_results if r.get("file_type") == "log"])
        metadata_count = len([r for r in all_results if r.get("file_type") == "metadata"])
        total_size = sum(r.get("file_size", 0) for r in all_results)

        # 转换为响应模型
        result_responses = [
            BuildResultResponse(**result) for result in all_results
        ]

        return BuildResultsListResponse(
            build_task_id=task_id,
            total_count=len(all_results),
            apk_count=apk_count,
            log_count=log_count,
            metadata_count=metadata_count,
            total_size=total_size,
            results=result_responses
        )

    except Exception as e:
        logger.error(f"获取构建结果失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取构建结果失败: {str(e)}")


@router.get("/tasks/{task_id}/apks", response_model=List[APKInfoResponse])
async def get_apk_files(
    task_id: str,
    service: APKService = Depends(get_apk_service)
) -> List[APKInfoResponse]:
    """
    获取构建任务的APK文件列表。

    Args:
        task_id: 任务ID
        service: APK服务

    Returns:
        APK文件列表

    Raises:
        HTTPException: 获取失败
    """
    try:
        apk_results = await service.get_apk_results(task_id)

        apk_responses = []
        for result in apk_results:
            metadata = result.get("metadata", {})

            apk_response = APKInfoResponse(
                file_name=metadata.get("file_name", result.get("filename", "")),
                file_path=result.get("file_path", ""),
                file_size=result.get("file_size", 0),
                file_size_mb=result.get("file_size_mb", 0),
                file_hash=result.get("file_hash"),
                build_variant=metadata.get("build_variant"),
                package_info=metadata.get("package_info"),
                permissions=metadata.get("permissions", []),
                activities=metadata.get("activities", []),
                services=metadata.get("services", []),
                native_libs=metadata.get("native_libs", []),
                resources=metadata.get("resources", []),
                manifest_valid=metadata.get("manifest_valid", False),
                created_at=result.get("created_at")
            )
            apk_responses.append(apk_response)

        return apk_responses

    except Exception as e:
        logger.error(f"获取APK文件列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取APK文件列表失败: {str(e)}")


@router.get("/tasks/{task_id}/apks/{apk_id}/info", response_model=APKInfoResponse)
async def get_apk_info(
    task_id: str,
    apk_id: str,
    service: APKService = Depends(get_apk_service)
) -> APKInfoResponse:
    """
    获取特定APK文件的详细信息。

    Args:
        task_id: 任务ID
        apk_id: APK结果ID
        service: APK服务

    Returns:
        APK详细信息

    Raises:
        HTTPException: 获取失败
    """
    try:
        # 从所有构建结果中找到指定的APK
        all_results = await service.get_build_results(task_id)

        apk_result = None
        for result in all_results:
            if result.get("id") == apk_id and result.get("file_type") == "apk":
                apk_result = result
                break

        if not apk_result:
            raise HTTPException(status_code=404, detail=f"APK文件不存在: {apk_id}")

        metadata = apk_result.get("metadata", {})

        return APKInfoResponse(
            file_name=metadata.get("file_name", apk_result.get("filename", "")),
            file_path=apk_result.get("file_path", ""),
            file_size=apk_result.get("file_size", 0),
            file_size_mb=apk_result.get("file_size_mb", 0),
            file_hash=apk_result.get("file_hash"),
            build_variant=metadata.get("build_variant"),
            package_info=metadata.get("package_info"),
            permissions=metadata.get("permissions", []),
            activities=metadata.get("activities", []),
            services=metadata.get("services", []),
            native_libs=metadata.get("native_libs", []),
            resources=metadata.get("resources", []),
            manifest_valid=metadata.get("manifest_valid", False),
            created_at=apk_result.get("created_at")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取APK详细信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取APK详细信息失败: {str(e)}")


@router.get("/files/{file_id}/download")
async def download_file(
    file_id: str,
    service: APKService = Depends(get_apk_service)
) -> FileResponse:
    """
    下载构建产物文件。

    Args:
        file_id: 文件ID
        service: APK服务

    Returns:
        文件响应

    Raises:
        HTTPException: 下载失败
    """
    try:
        # 获取构建结果信息
        build_result = await service.get_build_result_by_id(file_id)
        if not build_result:
            raise HTTPException(status_code=404, detail=f"文件不存在: {file_id}")

        file_path = build_result.get("file_path")
        filename = build_result.get("filename", f"file_{file_id}")

        # 验证文件是否存在
        from pathlib import Path
        path = Path(file_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"文件不存在: {filename}")

        # 确定媒体类型
        media_type = "application/octet-stream"  # 默认
        if filename.endswith('.apk'):
            media_type = "application/vnd.android.package-archive"
        elif filename.endswith('.log'):
            media_type = "text/plain"
        elif filename.endswith('.json'):
            media_type = "application/json"

        logger.info(f"下载构建产物: {file_id} -> {filename}")
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type=media_type
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"下载文件失败: {str(e)}")


@router.delete("/tasks/{task_id}/results")
async def clear_build_results(
    task_id: str,
    file_type: Optional[str] = Query(None, description="要删除的文件类型，不指定则删除所有"),
    service: APKService = Depends(get_apk_service)
) -> Dict[str, Any]:
    """
    清理构建任务的产物文件。

    Args:
        task_id: 任务ID
        file_type: 文件类型过滤
        service: APK服务

    Returns:
        删除结果

    Raises:
        HTTPException: 删除失败
    """
    try:
        # 这里需要实现删除逻辑
        raise HTTPException(status_code=501, detail="清理结果功能尚未实现")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"清理构建结果失败: {e}")
        raise HTTPException(status_code=500, detail=f"清理构建结果失败: {str(e)}")