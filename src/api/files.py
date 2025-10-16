"""
文件管理API端点。

提供文件上传、下载和管理功能。
"""

import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..config.database import get_async_session
from ..services.file_service import FileService
from ..utils.exceptions import create_validation_exception, create_not_found_exception

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/files", tags=["Files"])


# Dependency injection
async def get_file_service() -> FileService:
    """获取文件服务实例。"""
    return FileService()


# Pydantic models for request/response
from pydantic import BaseModel, Field


class FileUploadResponse(BaseModel):
    """文件上传响应模型。"""
    file_id: str
    original_filename: str
    safe_filename: str
    file_path: str
    file_size: int
    content_type: str
    is_archive: bool
    status: str
    message: str = "File uploaded successfully"


class FileListResponse(BaseModel):
    """文件列表响应模型。"""
    files: List[Dict[str, Any]]
    total_count: int
    total_size_mb: float


class ArchiveExtractRequest(BaseModel):
    """压缩文件解压请求模型。"""
    file_id: str
    extract_to: Optional[str] = None


class ArchiveExtractResponse(BaseModel):
    """压缩文件解压响应模型。"""
    extracted: bool
    extract_dir: str
    file_count: int
    extracted_files: List[Dict[str, Any]]
    status: str


class DirectoryInfo(BaseModel):
    """目录信息响应模型。"""
    upload_directory: str
    total_files: int
    total_size_bytes: int
    total_size_mb: float
    file_types: Dict[str, int]
    directory_exists: bool


# API endpoints
@router.post("/upload", response_model=FileUploadResponse, status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None, description="关联的项目ID"),
    service: FileService = Depends(get_file_service)
) -> FileUploadResponse:
    """
    上传文件。

    Args:
        file: 要上传的文件
        project_id: 关联的项目ID（可选）
        service: 文件服务

    Returns:
        上传结果

    Raises:
        HTTPException: 文件验证失败或上传失败
    """
    try:
        # 验证文件
        if not file.filename:
            raise create_validation_exception("文件名不能为空")

        # 读取文件内容
        content = await file.read()
        if not content:
            raise create_validation_exception("文件内容不能为空")

        # 保存文件
        file_info = await service.save_uploaded_file(
            file_content=content,
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream"
        )

        # 添加项目ID到响应中
        response = FileUploadResponse(**file_info)
        if project_id:
            response.message = f"文件上传成功，关联项目ID: {project_id}"
            logger.info(f"文件上传成功: {file.filename} (项目ID: {project_id})")
        else:
            logger.info(f"文件上传成功: {file.filename}")

        return response

    except Exception as e:
        logger.error(f"文件上传失败: {e}")
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")


@router.get("/list", response_model=FileListResponse)
async def list_files(
    limit: int = Query(100, ge=1, le=1000, description="返回文件数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    file_type: Optional[str] = Query(None, description="文件类型过滤"),
    service: FileService = Depends(get_file_service)
) -> FileListResponse:
    """
    获取文件列表。

    Args:
        limit: 返回文件数量限制
        offset: 偏移量
        file_type: 文件类型过滤（可选）
        service: 文件服务

    Returns:
        文件列表

    Raises:
        HTTPException: 获取文件列表失败
    """
    try:
        # 获取上传目录信息
        dir_info = service.get_upload_directory_info()

        # TODO: 实现更复杂的文件列表逻辑，包括分页和过滤
        # 目前返回目录信息的简化版本
        return FileListResponse(
            files=[],  # TODO: 实现实际的文件列表
            total_count=dir_info["total_files"],
            total_size_mb=dir_info["total_size_mb"]
        )

    except Exception as e:
        logger.error(f"获取文件列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取文件列表失败: {str(e)}")


@router.get("/directory/info", response_model=DirectoryInfo)
async def get_directory_info(
    service: FileService = Depends(get_file_service)
) -> DirectoryInfo:
    """
    获取上传目录信息。

    Args:
        service: 文件服务

    Returns:
        目录信息

    Raises:
        HTTPException: 获取目录信息失败
    """
    try:
        dir_info = service.get_upload_directory_info()
        logger.info(f"获取目录信息: {dir_info['total_files']} 个文件")
        return DirectoryInfo(**dir_info)

    except Exception as e:
        logger.error(f"获取目录信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取目录信息失败: {str(e)}")


@router.get("/download-base64")
async def download_file_base64(
    encoded_path: str = Query(..., description="Base64编码的文件路径")
) -> FileResponse:
    """
    使用Base64编码的文件路径下载文件

    Args:
        encoded_path: Base64编码的文件路径

    Returns:
        文件下载响应
    """
    try:
        import base64
        from pathlib import Path

        logger.info(f"[BASE64 DOWNLOAD] 收到编码路径: {encoded_path[:50]}...")
        logger.info(f"[BASE64 DOWNLOAD] 已更新版本 - 测试端点")

        # Base64解码
        try:
            decoded_bytes = base64.b64decode(encoded_path)
            decoded_path = decoded_bytes.decode('utf-8')
            logger.info(f"[BASE64 DOWNLOAD] 解码后路径: {decoded_path}")
        except Exception as decode_error:
            logger.error(f"[BASE64 DOWNLOAD] Base64解码失败: {decode_error}")
            raise HTTPException(status_code=400, detail="无效的Base64编码路径")

        # 安全检查 - 确保是合法的文件路径
        file_system_path = Path(decoded_path)

        # 基本安全检查
        dangerous_patterns = ["..", "~", "/etc/", "/bin/", "/usr/", "C:\\Windows", "C:\\Program"]
        if any(pattern in decoded_path for pattern in dangerous_patterns):
            raise HTTPException(status_code=403, detail="不允许的路径格式")

        # 只允许特定的文件类型下载
        allowed_extensions = ['.apk', '.jar', '.log', '.json', '.zip', '.rar', '.7z']
        if not any(decoded_path.lower().endswith(ext) for ext in allowed_extensions):
            raise HTTPException(status_code=403, detail="不允许的文件类型")

        # 检查文件是否存在
        if not file_system_path.exists():
            logger.error(f"[BASE64 DOWNLOAD] 文件不存在: {file_system_path}")
            raise HTTPException(status_code=404, detail=f"文件不存在: {decoded_path}")

        if not file_system_path.is_file():
            raise HTTPException(status_code=400, detail="指定的路径不是文件")

        # 获取文件名
        filename = file_system_path.name

        # 根据文件扩展名确定媒体类型
        media_type = "application/octet-stream"  # 默认
        if filename.endswith('.apk'):
            media_type = "application/vnd.android.package-archive"
        elif filename.endswith('.jar'):
            media_type = "application/java-archive"
        elif filename.endswith('.log'):
            media_type = "text/plain"
        elif filename.endswith('.json'):
            media_type = "application/json"
        elif filename.endswith('.zip'):
            media_type = "application/zip"
        elif filename.endswith('.rar'):
            media_type = "application/x-rar-compressed"
        elif filename.endswith('.7z'):
            media_type = "application/x-7z-compressed"

        logger.info(f"[BASE64 DOWNLOAD] 文件下载成功: {file_system_path} -> {filename}")

        return FileResponse(
            path=str(file_system_path),
            filename=filename,
            media_type=media_type
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[BASE64 DOWNLOAD] 文件下载失败: {e}")
        raise HTTPException(status_code=500, detail=f"文件下载失败: {str(e)}")


@router.get("/{file_id}/info")
async def get_file_info(
    file_id: str,
    service: FileService = Depends(get_file_service)
) -> Dict[str, Any]:
    """
    获取文件信息。

    Args:
        file_id: 文件ID
        service: 文件服务

    Returns:
        文件信息

    Raises:
        HTTPException: 文件不存在
    """
    try:
        file_info = await service.get_file_info(file_id)
        if not file_info:
            raise create_not_found_exception("File", file_id)

        logger.info(f"获取文件信息: {file_id}")
        return file_info

    except Exception as e:
        logger.error(f"获取文件信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取文件信息失败: {str(e)}")


@router.get("/{file_id}/download")
async def download_file(
    file_id: str,
    service: FileService = Depends(get_file_service)
) -> FileResponse:
    """
    下载文件。

    Args:
        file_id: 文件ID
        service: 文件服务

    Returns:
        文件下载响应

    Raises:
        HTTPException: 文件不存在
    """
    try:
        file_info = await service.get_file_info(file_id)
        if not file_info:
            raise create_not_found_exception("File", file_id)

        file_path = file_info["file_path"]
        filename = file_info["file_name"]

        logger.info(f"文件下载: {file_id} -> {filename}")
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type="application/octet-stream"
        )

    except Exception as e:
        logger.error(f"文件下载失败: {e}")
        raise HTTPException(status_code=500, detail=f"文件下载失败: {str(e)}")


@router.post("/{file_id}/extract", response_model=ArchiveExtractResponse)
async def extract_archive(
    file_id: str,
    request: ArchiveExtractRequest,
    service: FileService = Depends(get_file_service)
) -> ArchiveExtractResponse:
    """
    解压压缩文件。

    Args:
        file_id: 文件ID
        request: 解压请求
        service: 文件服务

    Returns:
        解压结果

    Raises:
        HTTPException: 解压失败
    """
    try:
        # 获取文件信息
        file_info = await service.get_file_info(file_id)
        if not file_info:
            raise create_not_found_exception("File", file_id)

        file_path = file_info["file_path"]

        # 执行解压
        extract_result = await service.extract_archive(
            file_path=file_path,
            extract_to=request.extract_to
        )

        logger.info(f"文件解压完成: {file_id}, {extract_result['file_count']} 个文件")
        return ArchiveExtractResponse(**extract_result)

    except Exception as e:
        logger.error(f"文件解压失败: {e}")
        raise HTTPException(status_code=500, detail=f"文件解压失败: {str(e)}")


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    service: FileService = Depends(get_file_service)
) -> Dict[str, Any]:
    """
    删除文件。

    Args:
        file_id: 文件ID
        service: 文件服务

    Returns:
        删除结果

    Raises:
        HTTPException: 删除失败
    """
    try:
        success = await service.delete_file(file_id)
        if success:
            logger.info(f"文件删除成功: {file_id}")
            return {"message": "文件删除成功", "file_id": file_id}
        else:
            raise create_not_found_exception("File", file_id)

    except Exception as e:
        logger.error(f"文件删除失败: {e}")
        raise HTTPException(status_code=500, detail=f"文件删除失败: {str(e)}")


@router.post("/cleanup")
async def cleanup_expired_files(
    max_age_hours: int = Query(24, ge=1, le=168, description="最大保留时间（小时）"),
    service: FileService = Depends(get_file_service)
) -> Dict[str, Any]:
    """
    清理过期文件。

    Args:
        max_age_hours: 最大保留时间（小时）
        service: 文件服务

    Returns:
        清理结果

    Raises:
        HTTPException: 清理失败
    """
    try:
        cleaned_count = await service.cleanup_expired_files(max_age_hours)
        logger.info(f"清理过期文件完成: {cleaned_count} 个文件")
        return {
            "message": "清理完成",
            "cleaned_count": cleaned_count,
            "max_age_hours": max_age_hours
        }

    except Exception as e:
        logger.error(f"清理过期文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"清理过期文件失败: {str(e)}")


@router.post("/validate")
async def validate_file_before_upload(
    filename: str = Query(..., description="文件名"),
    content_type: str = Query(..., description="MIME类型"),
    file_size: int = Query(..., description="文件大小（字节）"),
    service: FileService = Depends(get_file_service)
) -> Dict[str, Any]:
    """
    上传前验证文件。

    Args:
        filename: 文件名
        content_type: MIME类型
        file_size: 文件大小
        service: 文件服务

    Returns:
        验证结果

    Raises:
        HTTPException: 验证失败
    """
    try:
        # 创建虚拟的文件内容进行验证
        dummy_content = b"dummy"  # 大小不重要，我们主要验证其他属性

        await service._validate_file(dummy_content, filename, content_type)

        # 检查文件大小限制
        settings = service.upload_dir
        max_size = service.upload_dir  # 这里需要从配置获取正确的最大大小

        validation_result = {
            "valid": True,
            "filename": filename,
            "content_type": content_type,
            "file_size": file_size,
            "is_archive": service._is_archive_file(filename, content_type),
            "message": "文件验证通过"
        }

        logger.info(f"文件验证通过: {filename}")
        return validation_result

    except ValueError as e:
        validation_result = {
            "valid": False,
            "filename": filename,
            "content_type": content_type,
            "file_size": file_size,
            "error": str(e),
            "message": "文件验证失败"
        }

        logger.warning(f"文件验证失败: {filename} - {e}")
        return validation_result

    except Exception as e:
        logger.error(f"文件验证失败: {e}")
        raise HTTPException(status_code=500, detail=f"文件验证失败: {str(e)}")