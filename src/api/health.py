"""
健康检查API端点。

提供系统健康状态检查功能。
"""

import logging
from typing import Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from ..config.database import get_async_session
from ..config.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/health", tags=["Health"])


@router.get("/")
async def health_check() -> Dict[str, Any]:
    """
    基础健康检查。

    Returns:
        健康状态信息
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "Android项目资源包替换构建工具"
    }


@router.get("/detailed")
async def detailed_health_check(
    session: AsyncSession = Depends(get_async_session)
) -> Dict[str, Any]:
    """
    详细健康检查，包括数据库连接状态。

    Args:
        session: 数据库会话

    Returns:
        详细健康状态信息
    """
    settings = get_settings()

    # 检查数据库连接
    db_healthy = False
    db_error = None
    try:
        result = await session.execute(text("SELECT 1"))
        if result.scalar() == 1:
            db_healthy = True
    except Exception as e:
        logger.error(f"数据库健康检查失败: {e}")
        db_error = str(e)

    # 检查上传目录
    upload_dir_exists = settings.upload_dir.exists()
    upload_dir_writable = False
    if upload_dir_exists:
        try:
            test_file = settings.upload_dir / ".health_check"
            test_file.write_text("test")
            test_file.unlink()
            upload_dir_writable = True
        except Exception as e:
            logger.warning(f"上传目录不可写: {e}")

    # 检查临时目录
    temp_dir_exists = settings.temp_dir.exists()
    temp_dir_writable = False
    if temp_dir_exists:
        try:
            test_file = settings.temp_dir / ".health_check"
            test_file.write_text("test")
            test_file.unlink()
            temp_dir_writable = True
        except Exception as e:
            logger.warning(f"临时目录不可写: {e}")

    # 总体健康状态
    overall_healthy = (
        db_healthy and
        upload_dir_exists and
        upload_dir_writable and
        temp_dir_exists and
        temp_dir_writable
    )

    return {
        "status": "healthy" if overall_healthy else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "Android项目资源包替换构建工具",
        "version": "1.0.0",
        "components": {
            "database": {
                "status": "healthy" if db_healthy else "unhealthy",
                "error": db_error
            },
            "upload_directory": {
                "status": "healthy" if (upload_dir_exists and upload_dir_writable) else "unhealthy",
                "exists": upload_dir_exists,
                "writable": upload_dir_writable,
                "path": str(settings.upload_dir)
            },
            "temp_directory": {
                "status": "healthy" if (temp_dir_exists and temp_dir_writable) else "unhealthy",
                "exists": temp_dir_exists,
                "writable": temp_dir_writable,
                "path": str(settings.temp_dir)
            }
        },
        "environment": {
            "debug": settings.debug,
            "cors_enabled": len(settings.cors_origins) > 0
        }
    }


@router.get("/liveness")
async def liveness_probe() -> Dict[str, str]:
    """
    Kubernetes liveness probe端点。

    Returns:
        存活状态
    """
    return {"status": "alive"}


@router.get("/readiness")
async def readiness_probe(
    session: AsyncSession = Depends(get_async_session)
) -> Dict[str, str]:
    """
    Kubernetes readiness probe端点。

    Args:
        session: 数据库会话

    Returns:
        就绪状态
    """
    try:
        # 检查数据库连接
        result = await session.execute(text("SELECT 1"))
        if result.scalar() == 1:
            return {"status": "ready"}
        else:
            return {"status": "not_ready", "reason": "database_check_failed"}
    except Exception as e:
        logger.error(f"就绪检查失败: {e}")
        return {"status": "not_ready", "reason": str(e)}
