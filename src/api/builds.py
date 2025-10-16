"""
构建管理API端点。

提供构建任务的创建、执行、监控和管理功能。
"""

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from ..config.database import get_async_session
from ..models.build_task import BuildTask, TaskType, TaskStatus
from ..models.build_log import BuildLog, LogLevel
from ..services.build_service import BuildService
from ..utils.exceptions import (
    BuildError,
    ValidationError,
    create_not_found_exception,
    create_validation_exception,
    create_conflict_exception
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/builds", tags=["Builds"])


# Pydantic models for request/response
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any


class BuildTaskCreateRequest(BaseModel):
    """创建构建任务请求模型。"""
    project_id: str = Field(..., description="项目ID")
    task_type: TaskType = Field(..., description="任务类型")
    git_branch: str = Field(..., description="Git分支名称")
    resource_package_path: Optional[str] = Field(None, description="资源包路径")
    config_options: Optional[Dict[str, Any]] = Field(None, description="构建配置选项")

    @validator('resource_package_path')
    def validate_resource_package_path(cls, v, values):
        if values.get('task_type') == TaskType.RESOURCE_REPLACE and not v:
            raise ValueError("资源替换任务必须提供资源包路径")
        return v


class BuildTaskResponse(BaseModel):
    """构建任务响应模型。"""
    id: str
    project_id: str
    task_type: str
    status: str
    progress: int
    started_at: Optional[str]
    completed_at: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
    error_message: Optional[str]
    result_data: Optional[Dict[str, Any]]
    resource_package_path: Optional[str]
    git_branch: Optional[str]
    commit_hash: Optional[str]
    config_options: Optional[Dict[str, Any]]
    is_completed: bool
    is_running: bool
    duration_seconds: Optional[int]

    @classmethod
    def from_build_task(cls, task: BuildTask) -> "BuildTaskResponse":
        """从BuildTask模型创建响应对象。"""
        return cls(**task.to_dict())


class BuildLogResponse(BaseModel):
    """构建日志响应模型。"""
    id: str
    build_task_id: str
    log_level: str
    timestamp: str
    message: str
    source: Optional[str]
    line_number: Optional[int]
    created_at: Optional[str]

    @classmethod
    def from_build_log(cls, log: BuildLog) -> "BuildLogResponse":
        """从BuildLog模型创建响应对象。"""
        return cls(**log.to_dict())


class BuildSafetyCheckRequest(BaseModel):
    """构建安全检查请求模型。"""
    project_id: str = Field(..., description="项目ID")
    git_branch: str = Field(..., description="Git分支名称")
    force: bool = Field(False, description="是否强制执行，忽略安全检查")


# Dependency injection
async def get_build_service(session: AsyncSession = Depends(get_async_session)) -> BuildService:
    """获取构建服务实例。"""
    return BuildService(session)


# API endpoints
@router.post("/tasks", response_model=BuildTaskResponse, status_code=201)
async def create_build_task(
    request: BuildTaskCreateRequest,
    service: BuildService = Depends(get_build_service)
) -> BuildTask:
    """
    创建新的构建任务。

    Args:
        request: 构建任务创建请求
        service: 构建服务

    Returns:
        创建的构建任务信息

    Raises:
        HTTPException: 创建任务失败
    """
    try:
        task = await service.create_build_task(
            project_id=request.project_id,
            task_type=request.task_type,
            git_branch=request.git_branch,
            resource_package_path=request.resource_package_path,
            config_options=request.config_options
        )
        logger.info(f"创建构建任务成功: {task.id}")
        return BuildTaskResponse.from_build_task(task)

    except ValidationError as e:
        raise create_validation_exception(str(e))
    except Exception as e:
        logger.error(f"创建构建任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建构建任务失败: {str(e)}")


@router.get("/tasks/{task_id}", response_model=BuildTaskResponse)
async def get_build_task(
    task_id: str,
    service: BuildService = Depends(get_build_service)
) -> BuildTask:
    """
    获取构建任务详情。

    Args:
        task_id: 任务ID
        service: 构建服务

    Returns:
        构建任务详情

    Raises:
        HTTPException: 任务不存在
    """
    try:
        task_status = await service.get_task_status(task_id)
        if not task_status:
            raise create_not_found_exception("BuildTask", task_id)

        # 创建响应对象
        return BuildTaskResponse(**task_status)

    except Exception as e:
        logger.error(f"获取构建任务详情失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取构建任务详情失败: {str(e)}")


@router.post("/tasks/{task_id}/start", response_model=Dict[str, Any])
async def start_build_task(
    task_id: str,
    service: BuildService = Depends(get_build_service)
) -> Dict[str, Any]:
    """
    开始执行构建任务。

    Args:
        task_id: 任务ID
        service: 构建服务

    Returns:
        启动结果

    Raises:
        HTTPException: 启动失败
    """
    try:
        success = await service.start_build_task(task_id)
        if success:
            return {"message": "构建任务已开始执行", "task_id": task_id}
        else:
            raise HTTPException(status_code=500, detail="启动构建任务失败")

    except ValidationError as e:
        raise create_validation_exception(str(e))
    except Exception as e:
        logger.error(f"启动构建任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动构建任务失败: {str(e)}")


@router.post("/tasks/{task_id}/cancel", response_model=Dict[str, Any])
async def cancel_build_task(
    task_id: str,
    service: BuildService = Depends(get_build_service)
) -> Dict[str, Any]:
    """
    取消构建任务。

    Args:
        task_id: 任务ID
        service: 构建服务

    Returns:
        取消结果

    Raises:
        HTTPException: 取消失败
    """
    try:
        success = await service.cancel_build_task(task_id)
        if success:
            return {"message": "构建任务已取消", "task_id": task_id}
        else:
            raise HTTPException(status_code=500, detail="取消构建任务失败")

    except ValidationError as e:
        raise create_validation_exception(str(e))
    except Exception as e:
        logger.error(f"取消构建任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"取消构建任务失败: {str(e)}")


@router.get("/tasks/{task_id}/logs", response_model=List[BuildLogResponse])
async def get_build_task_logs(
    task_id: str,
    limit: int = Query(100, ge=1, le=1000, description="日志数量限制"),
    service: BuildService = Depends(get_build_service)
) -> List[BuildLogResponse]:
    """
    获取构建任务日志。

    Args:
        task_id: 任务ID
        limit: 日志数量限制
        service: 构建服务

    Returns:
        构建日志列表

    Raises:
        HTTPException: 获取失败
    """
    try:
        logs = await service.get_task_logs(task_id, limit)
        return [BuildLogResponse(**log) for log in logs]

    except Exception as e:
        logger.error(f"获取构建任务日志失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取构建任务日志失败: {str(e)}")


@router.get("/tasks/{task_id}/logs/stream")
async def stream_build_task_logs(
    task_id: str,
    service: BuildService = Depends(get_build_service)
):
    """
    实时流式获取构建任务日志。

    Args:
        task_id: 任务ID
        service: 构建服务

    Returns:
        服务器发送事件流
    """
    async def event_generator():
        try:
            async for log in service.stream_task_logs(task_id):
                yield {
                    "event": "log",
                    "data": log
                }

            # 发送完成事件
            yield {
                "event": "completed",
                "data": {"task_id": task_id, "status": "completed"}
            }

        except Exception as e:
            logger.error(f"流式日志生成失败: {e}")
            yield {
                "event": "error",
                "data": {"error": str(e)}
            }

    return EventSourceResponse(event_generator())


@router.get("/tasks/{task_id}/safety-check")
async def check_build_safety(
    task_id: str,
    service: BuildService = Depends(get_build_service)
) -> Dict[str, Any]:
    """
    执行构建安全检查。

    Args:
        task_id: 任务ID
        service: 构建服务

    Returns:
        安全检查结果

    Raises:
        HTTPException: 检查失败
    """
    try:
        # 获取任务信息
        task_status = await service.get_task_status(task_id)
        if not task_status:
            raise create_not_found_exception("BuildTask", task_id)

        # 执行Git安全检查
        from ..utils.git_utils import GitUtils
        from ..models.android_project import AndroidProject

        # 获取项目信息
        project = await service.session.get(AndroidProject, task_status["project_id"])
        if not project:
            raise create_not_found_exception("AndroidProject", task_status["project_id"])

        safety_result = GitUtils.check_safety(project.path, task_status["git_branch"])

        logger.info(f"构建安全检查完成: {task_id}, 安全: {safety_result['is_safe']}")
        return safety_result

    except Exception as e:
        logger.error(f"构建安全检查失败: {e}")
        raise HTTPException(status_code=500, detail=f"构建安全检查失败: {str(e)}")


@router.post("/tasks/{task_id}/safety-check/force")
async def force_build_with_safety_check(
    task_id: str,
    request: BuildSafetyCheckRequest,
    service: BuildService = Depends(get_build_service)
) -> Dict[str, Any]:
    """
    强制执行构建（忽略安全检查）。

    Args:
        task_id: 任务ID
        request: 安全检查请求
        service: 构建服务

    Returns:
        执行结果

    Raises:
        HTTPException: 执行失败
    """
    try:
        # 如果要求强制执行，跳过安全检查
        if not request.force:
            # 先执行安全检查
            from ..utils.git_utils import GitUtils
            from ..models.android_project import AndroidProject

            # 获取项目信息
            task_status = await service.get_task_status(task_id)
            if not task_status:
                raise create_not_found_exception("BuildTask", task_id)

            project = await service.session.get(AndroidProject, task_status["project_id"])
            if not project:
                raise create_not_found_exception("AndroidProject", task_status["project_id"])

            safety_result = GitUtils.check_safety(project.path, request.git_branch)
            if not safety_result["is_safe"]:
                raise create_validation_exception(
                    f"安全检查失败: {'; '.join(safety_result['issues'])}"
                )

        # 开始执行任务
        success = await service.start_build_task(task_id)
        if success:
            return {"message": "任务已开始执行", "task_id": task_id, "forced": request.force}
        else:
            raise HTTPException(status_code=500, detail="启动任务失败")

    except ValidationError as e:
        raise create_validation_exception(str(e))
    except Exception as e:
        logger.error(f"强制执行构建失败: {e}")
        raise HTTPException(status_code=500, detail=f"强制执行构建失败: {str(e)}")


@router.get("/tasks", response_model=List[BuildTaskResponse])
async def list_build_tasks(
    status: Optional[str] = Query(None, description="按状态过滤"),
    project_id: Optional[str] = Query(None, description="按项目ID过滤"),
    limit: int = Query(50, ge=1, le=100, description="数量限制"),
    service: BuildService = Depends(get_build_service)
) -> List[BuildTaskResponse]:
    """
    获取构建任务列表。

    Args:
        status: 按状态过滤
        project_id: 按项目ID过滤
        limit: 数量限制
        service: 构建服务

    Returns:
        构建任务列表

    Raises:
        HTTPException: 获取失败
    """
    try:
        active_tasks = await service.get_active_tasks()

        # 转换为响应格式
        task_responses = []
        for task in active_tasks[:limit]:
            task_responses.append(BuildTaskResponse.from_build_task(task))

        return task_responses

    except Exception as e:
        logger.error(f"获取构建任务列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取构建任务列表失败: {str(e)}")


@router.delete("/tasks/{task_id}")
async def delete_build_task(
    task_id: str,
    service: BuildService = Depends(get_build_service)
) -> Dict[str, Any]:
    """
    删除构建任务。

    Args:
        task_id: 任务ID
        service: 构建服务

    Returns:
        删除结果

    Raises:
        HTTPException: 删除失败
    """
    try:
        # 获取任务状态
        task_status = await service.get_task_status(task_id)
        if not task_status:
            raise create_not_found_exception("BuildTask", task_id)

        # 只能删除已完成的任务
        if not task_status["is_completed"]:
            raise create_conflict_exception(
                "只能删除已完成的任务"
            )

        # 删除任务（这里需要实现软删除逻辑）
        # TODO: 实现任务删除逻辑

        return {"message": "构建任务已删除", "task_id": task_id}

    except Exception as e:
        logger.error(f"删除构建任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除构建任务失败: {str(e)}")


@router.get("/stats")
async def get_build_stats(
    service: BuildService = Depends(get_build_service)
) -> Dict[str, Any]:
    """
    获取构建统计信息。

    Args:
        service: 构建服务

    Returns:
        构建统计信息

    Raises:
        HTTPException: 获取失败
    """
    try:
        active_tasks = await service.get_active_tasks()

        # 统计各状态任务数量
        stats = {
            "total_tasks": len(active_tasks),
            "running_tasks": len([t for t in active_tasks if t.status == TaskStatus.RUNNING.value]),
            "completed_tasks": len([t for t in active_tasks if t.status == TaskStatus.COMPLETED.value]),
            "failed_tasks": len([t for t in active_tasks if t.status == TaskStatus.FAILED.value]),
            "cancelled_tasks": len([t for t in active_tasks if t.status == TaskStatus.CANCELLED.value]),
            "pending_tasks": len([t for t in active_tasks if t.status == TaskStatus.PENDING.value]),
            "by_task_type": {},
            "by_project": {}
        }

        # 按任务类型统计
        for task in active_tasks:
            task_type = task.task_type
            stats["by_task_type"][task_type] = stats["by_task_type"].get(task_type, 0) + 1

        # 按项目统计
        for task in active_tasks:
            project_id = str(task.project_id)
            stats["by_project"][project_id] = stats["by_project"].get(project_id, 0) + 1

        return stats

    except Exception as e:
        logger.error(f"获取构建统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取构建统计失败: {str(e)}")


@router.post("/cleanup")
async def cleanup_old_tasks(
    days: int = Query(7, ge=1, le=30, description="清理多少天前的任务"),
    service: BuildService = Depends(get_build_service)
) -> Dict[str, Any]:
    """
    清理旧的构建任务。

    Args:
        days: 清理多少天前的任务
        service: 构建服务

    Returns:
        清理结果

    Raises:
        HTTPException: 清理失败
    """
    try:
        count = await service.cleanup_completed_tasks(days)
        return {"message": f"已清理 {count} 个旧任务", "cleaned_count": count}

    except Exception as e:
        logger.error(f"清理旧任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"清理旧任务失败: {str(e)}")