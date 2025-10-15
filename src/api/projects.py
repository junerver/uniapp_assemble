"""
项目管理API端点。

提供Android项目的CRUD操作和项目配置管理API。
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..config.database import get_async_session
from ..services.android_service import AndroidProjectService
from ..models.android_project import AndroidProject
from ..models.project_config import ProjectConfig
from ..utils.exceptions import (
    ProjectNotFoundError,
    ProjectAlreadyExistsError,
    InvalidProjectPathError,
    create_not_found_exception,
    create_conflict_exception,
    create_validation_exception
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["Projects"])


# Pydantic models for request/response
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any


class ProjectCreateRequest(BaseModel):
    """创建项目请求模型。"""
    name: str = Field(..., min_length=1, max_length=255, description="项目名称")
    path: str = Field(..., min_length=1, description="项目路径")
    alias: Optional[str] = Field(None, max_length=255, description="项目别名")
    description: Optional[str] = Field(None, description="项目描述")
    git_url: Optional[str] = Field(None, description="Git仓库URL")
    main_branch: str = Field("main", description="主分支名称")

    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('项目名称不能为空')
        return v.strip()

    @validator('path')
    def validate_path(cls, v):
        if not v.strip():
            raise ValueError('项目路径不能为空')
        return v.strip()


class ProjectUpdateRequest(BaseModel):
    """更新项目请求模型。"""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="项目名称")
    alias: Optional[str] = Field(None, max_length=255, description="项目别名")
    description: Optional[str] = Field(None, description="项目描述")
    is_active: Optional[bool] = Field(None, description="是否激活")

    @validator('name')
    def validate_name(cls, v):
        if v is not None and not v.strip():
            raise ValueError('项目名称不能为空')
        return v.strip() if v else v


class ProjectResponse(BaseModel):
    """项目响应模型。"""
    id: str
    name: str
    alias: Optional[str]
    path: str
    description: Optional[str]
    is_active: bool
    display_name: str
    created_at: Optional[str]
    updated_at: Optional[str]

    class Config:
        from_attributes = True


class ProjectValidationResponse(BaseModel):
    """项目路径验证响应模型。"""
    valid: bool
    exists: bool
    is_directory: bool
    is_android_project: bool
    gradle_files: List[str]
    error: Optional[str]


# Dependency injection
async def get_project_service(session: AsyncSession = Depends(get_async_session)) -> AndroidProjectService:
    """获取Android项目服务实例。"""
    return AndroidProjectService(session)


# API endpoints
@router.post("/", response_model=ProjectResponse, status_code=201)
async def create_project(
    request: ProjectCreateRequest,
    service: AndroidProjectService = Depends(get_project_service)
) -> AndroidProject:
    """
    创建新的Android项目。

    Args:
        request: 项目创建请求
        service: Android项目服务

    Returns:
        创建的项目信息

    Raises:
        HTTPException: 项目创建失败
    """
    try:
        project = await service.create_project(
            name=request.name,
            path=request.path,
            alias=request.alias,
            description=request.description,
            git_url=request.git_url,
            main_branch=request.main_branch
        )
        logger.info(f"项目创建成功: {project.name} (ID: {project.id})")
        return project

    except ProjectAlreadyExistsError as e:
        raise create_conflict_exception(str(e))
    except InvalidProjectPathError as e:
        raise create_validation_exception(str(e))
    except Exception as e:
        logger.error(f"创建项目失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建项目失败: {str(e)}")


@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    active_only: bool = Query(True, description="是否只返回激活的项目"),
    service: AndroidProjectService = Depends(get_project_service)
) -> List[AndroidProject]:
    """
    获取项目列表。

    Args:
        active_only: 是否只返回激活的项目
        service: Android项目服务

    Returns:
        项目列表
    """
    try:
        projects = await service.list_projects(active_only=active_only)
        logger.info(f"获取项目列表: {len(projects)} 个项目")
        return projects

    except Exception as e:
        logger.error(f"获取项目列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取项目列表失败: {str(e)}")


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    service: AndroidProjectService = Depends(get_project_service)
) -> AndroidProject:
    """
    获取项目详情。

    Args:
        project_id: 项目ID
        service: Android项目服务

    Returns:
        项目详情

    Raises:
        HTTPException: 项目不存在
    """
    try:
        project = await service.get_project(project_id)
        logger.info(f"获取项目详情: {project.name} (ID: {project.id})")
        return project

    except ProjectNotFoundError as e:
        raise create_not_found_exception("Project", project_id)
    except Exception as e:
        logger.error(f"获取项目详情失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取项目详情失败: {str(e)}")


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    request: ProjectUpdateRequest,
    service: AndroidProjectService = Depends(get_project_service)
) -> AndroidProject:
    """
    更新项目信息。

    Args:
        project_id: 项目ID
        request: 项目更新请求
        service: Android项目服务

    Returns:
        更新后的项目信息

    Raises:
        HTTPException: 项目不存在或更新失败
    """
    try:
        project = await service.update_project(
            project_id=project_id,
            name=request.name,
            alias=request.alias,
            description=request.description,
            is_active=request.is_active
        )
        logger.info(f"项目更新成功: {project.name} (ID: {project.id})")
        return project

    except ProjectNotFoundError as e:
        raise create_not_found_exception("Project", project_id)
    except ProjectAlreadyExistsError as e:
        raise create_conflict_exception(str(e))
    except Exception as e:
        logger.error(f"更新项目失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新项目失败: {str(e)}")


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    service: AndroidProjectService = Depends(get_project_service)
) -> dict:
    """
    删除项目。

    Args:
        project_id: 项目ID
        service: Android项目服务

    Returns:
        删除结果

    Raises:
        HTTPException: 项目不存在或删除失败
    """
    try:
        success = await service.delete_project(project_id)
        if success:
            logger.info(f"项目删除成功: {project_id}")
            return {"message": "项目删除成功", "project_id": project_id}
        else:
            raise HTTPException(status_code=500, detail="项目删除失败")

    except ProjectNotFoundError as e:
        raise create_not_found_exception("Project", project_id)
    except Exception as e:
        logger.error(f"删除项目失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除项目失败: {str(e)}")


@router.post("/{project_id}/validate")
async def validate_project_path(
    project_id: str,
    service: AndroidProjectService = Depends(get_project_service)
) -> ProjectValidationResponse:
    """
    验证项目路径。

    Args:
        project_id: 项目ID
        service: Android项目服务

    Returns:
        验证结果

    Raises:
        HTTPException: 项目不存在
    """
    try:
        project = await service.get_project(project_id)
        validation_result = await service.validate_project_path(project.path)

        logger.info(f"项目路径验证完成: {project_id}, 结果: {validation_result['valid']}")
        return ProjectValidationResponse(**validation_result)

    except ProjectNotFoundError as e:
        raise create_not_found_exception("Project", project_id)
    except Exception as e:
        logger.error(f"验证项目路径失败: {e}")
        raise HTTPException(status_code=500, detail=f"验证项目路径失败: {str(e)}")


@router.post("/validate-path")
async def validate_path(
    path: str = Query(..., description="要验证的项目路径"),
    service: AndroidProjectService = Depends(get_project_service)
) -> ProjectValidationResponse:
    """
    验证任意路径（用于项目创建前的验证）。

    Args:
        path: 要验证的路径
        service: Android项目服务

    Returns:
        验证结果
    """
    try:
        validation_result = await service.validate_project_path(path)

        logger.info(f"路径验证完成: {path}, 结果: {validation_result['valid']}")
        return ProjectValidationResponse(**validation_result)

    except Exception as e:
        logger.error(f"验证路径失败: {e}")
        raise HTTPException(status_code=500, detail=f"验证路径失败: {str(e)}")


@router.get("/{project_id}/configs", response_model=List[Dict[str, Any]])
async def get_project_configs(
    project_id: str,
    service: AndroidProjectService = Depends(get_project_service)
) -> List[ProjectConfig]:
    """
    获取项目配置列表。

    Args:
        project_id: 项目ID
        service: Android项目服务

    Returns:
        项目配置列表

    Raises:
        HTTPException: 项目不存在
    """
    try:
        # 验证项目存在
        await service.get_project(project_id)

        configs = await service.get_project_configs(project_id)
        logger.info(f"获取项目配置: {project_id}, {len(configs)} 个配置")
        return [config.to_dict() for config in configs]

    except ProjectNotFoundError as e:
        raise create_not_found_exception("Project", project_id)
    except Exception as e:
        logger.error(f"获取项目配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取项目配置失败: {str(e)}")


@router.post("/{project_id}/activate")
async def activate_project(
    project_id: str,
    service: AndroidProjectService = Depends(get_project_service)
) -> dict:
    """
    激活项目。

    Args:
        project_id: 项目ID
        service: Android项目服务

    Returns:
        激活结果

    Raises:
        HTTPException: 项目不存在
    """
    try:
        project = await service.update_project(project_id, is_active=True)
        logger.info(f"项目激活成功: {project.name} (ID: {project.id})")
        return {"message": "项目激活成功", "project_id": project_id}

    except ProjectNotFoundError as e:
        raise create_not_found_exception("Project", project_id)
    except Exception as e:
        logger.error(f"激活项目失败: {e}")
        raise HTTPException(status_code=500, detail=f"激活项目失败: {str(e)}")


@router.post("/{project_id}/deactivate")
async def deactivate_project(
    project_id: str,
    service: AndroidProjectService = Depends(get_project_service)
) -> dict:
    """
    停用项目。

    Args:
        project_id: 项目ID
        service: Android项目服务

    Returns:
        停用结果

    Raises:
        HTTPException: 项目不存在
    """
    try:
        project = await service.update_project(project_id, is_active=False)
        logger.info(f"项目停用成功: {project.name} (ID: {project.id})")
        return {"message": "项目停用成功", "project_id": project_id}

    except ProjectNotFoundError as e:
        raise create_not_found_exception("Project", project_id)
    except Exception as e:
        logger.error(f"停用项目失败: {e}")
        raise HTTPException(status_code=500, detail=f"停用项目失败: {str(e)}")