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

    @classmethod
    def from_android_project(cls, project: AndroidProject) -> "ProjectResponse":
        """从AndroidProject模型创建响应对象。"""
        from datetime import datetime
        return cls(
            id=project.id,
            name=project.name,
            alias=project.alias,
            path=project.path,
            description=project.description,
            is_active=project.is_active,
            display_name=project.alias if project.alias else project.name,
            created_at=project.created_at.isoformat() if isinstance(project.created_at, datetime) else str(project.created_at) if project.created_at else None,
            updated_at=project.updated_at.isoformat() if isinstance(project.updated_at, datetime) else str(project.updated_at) if project.updated_at else None
        )


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
        return ProjectResponse.from_android_project(project)

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
        return [ProjectResponse.from_android_project(project) for project in projects]

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
        return ProjectResponse.from_android_project(project)

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
        return ProjectResponse.from_android_project(project)

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


@router.get("/{project_id}/branches")
async def get_project_branches(
    project_id: str,
    include_remote: bool = Query(True, description="是否包含远程分支"),
    service: AndroidProjectService = Depends(get_project_service)
) -> Dict[str, Any]:
    """
    获取项目的Git分支列表。

    Args:
        project_id: 项目ID
        include_remote: 是否包含远程分支
        service: Android项目服务

    Returns:
        分支信息，包括当前分支和分支列表

    Raises:
        HTTPException: 项目不存在或不是Git仓库
    """
    try:
        # 获取项目信息
        project = await service.get_project(project_id)

        # 导入Git工具
        from ..utils.git_utils import GitUtils

        # 检查是否为Git仓库
        if not GitUtils.is_git_repository(project.path):
            raise HTTPException(
                status_code=400,
                detail=f"项目路径不是有效的Git仓库: {project.path}"
            )

        # 获取分支信息
        branches = GitUtils.get_all_branches(project.path, include_remote=include_remote)
        current_branch = GitUtils.get_current_branch(project.path)

        logger.info(f"获取项目分支: {project.name} (ID: {project.id}), {len(branches)} 个分支")

        return {
            "project_id": project_id,
            "current_branch": current_branch,
            "branches": branches,
            "total_count": len(branches)
        }

    except ProjectNotFoundError as e:
        raise create_not_found_exception("Project", project_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取项目分支失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取项目分支失败: {str(e)}")


@router.get("/{project_id}/resource-packages")
async def get_resource_packages(
    project_id: str,
    branch: str = Query(..., description="分支名称"),
    service: AndroidProjectService = Depends(get_project_service)
) -> Dict[str, Any]:
    """
    获取项目指定分支的资源包ID列表(通过Git查询,不切换分支)。

    Args:
        project_id: 项目ID
        branch: 分支名称
        service: Android项目服务

    Returns:
        资源包信息,包括资源包ID列表

    Raises:
        HTTPException: 项目不存在或不是Git仓库
    """
    try:
        # 获取项目信息
        project = await service.get_project(project_id)

        # 导入Git工具
        from ..utils.git_utils import GitUtils, BranchNotFoundError

        # 检查是否为Git仓库
        if not GitUtils.is_git_repository(project.path):
            raise HTTPException(
                status_code=400,
                detail=f"项目路径不是有效的Git仓库: {project.path}"
            )

        # 获取资源包目录列表(app/src/main/assets/apps)
        try:
            resource_packages = GitUtils.list_directories_in_branch(
                path=project.path,
                branch_name=branch,
                directory_path="app/src/main/assets/apps"
            )

            # 获取指定分支的commit信息
            branch_info = GitUtils.get_branch_info(project.path, branch)

            logger.info(f"获取资源包列表: {project.name} (ID: {project.id}), 分支: {branch}, {len(resource_packages)} 个资源包")

            return {
                "project_id": project_id,
                "branch": branch,
                "resource_packages": resource_packages,
                "total_count": len(resource_packages),
                "directory_path": "app/src/main/assets/apps",
                "latest_commit": {
                    "sha": branch_info.get("commit_sha"),
                    "short_sha": branch_info.get("short_sha"),
                    "message": branch_info.get("commit_message"),
                    "author": branch_info.get("author"),
                    "committed_date": branch_info.get("committed_date")
                }
            }

        except BranchNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))

    except ProjectNotFoundError as e:
        raise create_not_found_exception("Project", project_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取资源包列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取资源包列表失败: {str(e)}")


@router.get("/{project_id}/workspace-status")
async def get_workspace_status(
    project_id: str,
    service: AndroidProjectService = Depends(get_project_service)
) -> Dict[str, Any]:
    """
    获取项目工作区状态。

    Args:
        project_id: 项目ID
        service: Android项目服务

    Returns:
        工作区状态信息，包括：
        - is_clean: 工作区是否干净
        - is_dirty: 是否有未提交的更改
        - untracked_files: 未跟踪文件数量
        - modified_files: 已修改文件数量
        - staged_files: 暂存区文件数量
        - can_clean_reset: 是否可以安全地回滚

    Raises:
        HTTPException: 项目不存在或不是Git仓库
    """
    try:
        # 获取项目信息
        project = await service.get_project(project_id)

        # 导入Git工具
        from ..utils.git_utils import GitUtils

        # 检查是否为Git仓库
        if not GitUtils.is_git_repository(project.path):
            raise HTTPException(
                status_code=400,
                detail=f"项目路径不是有效的Git仓库: {project.path}"
            )

        # 获取仓库信息
        repo_info = GitUtils.get_repository_info(project.path)

        # 获取暂存区文件数量
        staged_files = 0
        try:
            git_repo = GitUtils.get_repository(project.path)
            staged_files = len([item.a_path for item in git_repo.index.diff("HEAD")])
        except Exception as e:
            logger.warning(f"获取暂存区文件数量失败: {e}")

        # 判断是否可以安全地回滚
        can_clean_reset = True
        status_description = "工作区干净"
        status_type = "clean"

        if repo_info["is_dirty"]:
            can_clean_reset = False
            status_type = "dirty"
            if repo_info["untracked_files"] > 0 and repo_info["modified_files"] > 0:
                status_description = f"有未提交的更改 ({repo_info['untracked_files']} 个未跟踪文件, {repo_info['modified_files']} 个修改文件)"
            elif repo_info["untracked_files"] > 0:
                status_description = f"有未跟踪文件 ({repo_info['untracked_files']} 个)"
            elif repo_info["modified_files"] > 0:
                status_description = f"有修改的文件 ({repo_info['modified_files']} 个)"
        elif staged_files > 0:
            can_clean_reset = False
            status_type = "staged"
            status_description = f"暂存区有文件 ({staged_files} 个)"
        else:
            status_description = "工作区干净"

        logger.info(f"获取工作区状态: {project.name} (ID: {project.id}), 状态: {status_type}")

        return {
            "project_id": project_id,
            "is_clean": not repo_info["is_dirty"] and staged_files == 0,
            "is_dirty": repo_info["is_dirty"],
            "untracked_files": repo_info["untracked_files"],
            "modified_files": repo_info["modified_files"],
            "staged_files": staged_files,
            "can_clean_reset": can_clean_reset,
            "status_description": status_description,
            "status_type": status_type
        }

    except ProjectNotFoundError as e:
        raise create_not_found_exception("Project", project_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取工作区状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取工作区状态失败: {str(e)}")


@router.post("/{project_id}/reset-workspace")
async def reset_workspace(
    project_id: str,
    service: AndroidProjectService = Depends(get_project_service)
) -> Dict[str, Any]:
    """
    回滚工作区到当前分支的最新提交。

    此操作将：
    - 丢弃所有未提交的更改
    - 删除所有未跟踪的文件
    - 清空暂存区

    Args:
        project_id: 项目ID
        service: Android项目服务

    Returns:
        回滚结果

    Raises:
        HTTPException: 项目不存在或不是Git仓库
    """
    try:
        # 获取项目信息
        project = await service.get_project(project_id)

        # 导入Git工具
        from ..utils.git_utils import GitUtils

        # 检查是否为Git仓库
        if not GitUtils.is_git_repository(project.path):
            raise HTTPException(
                status_code=400,
                detail=f"项目路径不是有效的Git仓库: {project.path}"
            )

        # 获取仓库对象
        repo = GitUtils.get_repository(project.path)

        # 记录回滚前的状态
        status_before = GitUtils.get_repository_info(project.path)

        # 执行重置操作
        reset_results = {
            "discarded_changes": 0,
            "removed_untracked": 0,
            "cleared_staged": 0,
            "errors": []
        }

        try:
            # 1. 清空暂存区
            if len([item.a_path for item in repo.index.diff("HEAD")]) > 0:
                repo.git.reset("--mixed", "HEAD")
                reset_results["cleared_staged"] = len([item.a_path for item in repo.index.diff("HEAD")])
                logger.info(f"清空暂存区: {reset_results['cleared_staged']} 个文件")

            # 2. 丢弃工作区的更改
            if status_before["modified_files"] > 0:
                repo.git.checkout("--", ".")
                reset_results["discarded_changes"] = status_before["modified_files"]
                logger.info(f"丢弃更改: {reset_results['discarded_changes']} 个文件")

            # 3. 删除未跟踪的文件
            if status_before["untracked_files"] > 0:
                repo.git.clean("-fd")
                reset_results["removed_untracked"] = status_before["untracked_files"]
                logger.info(f"删除未跟踪文件: {reset_results['removed_untracked']} 个文件")

        except Exception as e:
            error_msg = f"执行重置操作时出错: {str(e)}"
            logger.error(error_msg)
            reset_results["errors"].append(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

        # 获取回滚后的状态
        status_after = GitUtils.get_repository_info(project.path)

        logger.info(f"工作区回滚完成: {project.name} (ID: {project.id})")

        return {
            "project_id": project_id,
            "success": len(reset_results["errors"]) == 0,
            "message": "工作区已成功回滚到最新提交" if len(reset_results["errors"]) == 0 else "回滚过程中出现错误",
            "reset_results": reset_results,
            "status_before": {
                "is_dirty": status_before["is_dirty"],
                "untracked_files": status_before["untracked_files"],
                "modified_files": status_before["modified_files"]
            },
            "status_after": {
                "is_dirty": status_after["is_dirty"],
                "untracked_files": status_after["untracked_files"],
                "modified_files": status_after["modified_files"]
            }
        }

    except ProjectNotFoundError as e:
        raise create_not_found_exception("Project", project_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重置工作区失败: {e}")
        raise HTTPException(status_code=500, detail=f"重置工作区失败: {str(e)}")


# 构建相关的新端点
@router.get("/{project_id}/build-info")
async def get_project_build_info(
    project_id: str,
    service: AndroidProjectService = Depends(get_project_service)
) -> Dict[str, Any]:
    """
    获取项目的构建信息。

    Args:
        project_id: 项目ID
        service: Android项目服务

    Returns:
        构建信息，包括Git信息、Gradle信息等

    Raises:
        HTTPException: 项目不存在
    """
    try:
        build_info = await service.get_project_build_info(project_id)
        logger.info(f"获取项目构建信息: {project_id}")
        return build_info

    except ProjectNotFoundError as e:
        raise create_not_found_exception("Project", project_id)
    except Exception as e:
        logger.error(f"获取项目构建信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取项目构建信息失败: {str(e)}")


@router.get("/{project_id}/build-validation")
async def validate_build_environment(
    project_id: str,
    service: AndroidProjectService = Depends(get_project_service)
) -> Dict[str, Any]:
    """
    验证项目的构建环境。

    Args:
        project_id: 项目ID
        service: Android项目服务

    Returns:
        构建环境验证结果

    Raises:
        HTTPException: 项目不存在
    """
    try:
        validation_result = await service.validate_build_environment(project_id)
        logger.info(f"构建环境验证完成: {project_id}, 有效: {validation_result['valid']}")
        return validation_result

    except ProjectNotFoundError as e:
        raise create_not_found_exception("Project", project_id)
    except Exception as e:
        logger.error(f"构建环境验证失败: {e}")
        raise HTTPException(status_code=500, detail=f"构建环境验证失败: {str(e)}")


@router.post("/{project_id}/prepare-build")
async def prepare_build(
    project_id: str,
    task_type: str = Query(..., description="任务类型"),
    git_branch: str = Query(..., description="Git分支"),
    resource_package_path: Optional[str] = Query(None, description="资源包路径"),
    config_options: Optional[Dict[str, Any]] = None,
    service: AndroidProjectService = Depends(get_project_service)
) -> Dict[str, Any]:
    """
    为项目准备构建任务。

    Args:
        project_id: 项目ID
        task_type: 任务类型
        git_branch: Git分支
        resource_package_path: 资源包路径
        config_options: 构建配置选项
        service: Android项目服务

    Returns:
        构建准备结果

    Raises:
        HTTPException: 项目不存在或验证失败
    """
    try:
        build_prep = await service.create_build_task_for_project(
            project_id=project_id,
            task_type=task_type,
            git_branch=git_branch,
            resource_package_path=resource_package_path,
            config_options=config_options or {}
        )
        logger.info(f"构建任务准备完成: {project_id}, 类型: {task_type}")
        return build_prep

    except ProjectNotFoundError as e:
        raise create_not_found_exception("Project", project_id)
    except Exception as e:
        logger.error(f"准备构建任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"准备构建任务失败: {str(e)}")


@router.get("/{project_id}/branch-info")
async def get_project_branch_info(
    project_id: str,
    service: AndroidProjectService = Depends(get_project_service)
) -> Dict[str, Any]:
    """
    获取项目的Git分支信息（使用AndroidProjectService的新方法）。

    Args:
        project_id: 项目ID
        service: Android项目服务

    Returns:
        分支信息

    Raises:
        HTTPException: 项目不存在
    """
    try:
        branch_info = await service.get_project_branches(project_id)
        logger.info(f"获取项目分支信息: {project_id}")
        return branch_info

    except ProjectNotFoundError as e:
        raise create_not_found_exception("Project", project_id)
    except Exception as e:
        logger.error(f"获取项目分支信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取项目分支信息失败: {str(e)}")