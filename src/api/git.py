"""
Git操作API端点。

提供Git提交、回滚、备份和恢复操作的REST API接口。
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, Path
from pydantic import BaseModel, Field

from ..services.git_service import GitService
from ..models.git_operation import OperationType
from ..config.database import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession


router = APIRouter(prefix="/api/git", tags=["git"])


class CommitRequest(BaseModel):
    """Git提交请求模型。"""
    commit_message: str = Field(..., min_length=1, max_length=1000, description="提交消息")
    files_to_commit: Optional[List[str]] = Field(None, description="要提交的文件列表，为空则提交所有变更")
    create_backup: bool = Field(True, description="是否在提交前创建备份")
    backup_expiry_days: int = Field(30, ge=1, le=365, description="备份保留天数")


class RollbackRequest(BaseModel):
    """Git回滚请求模型。"""
    target_commit_hash: str = Field(..., min_length=7, max_length=40, description="目标提交哈希")
    create_backup: bool = Field(True, description="是否在回滚前创建备份")
    backup_expiry_days: int = Field(30, ge=1, le=365, description="备份保留天数")


class BranchOperationRequest(BaseModel):
    """分支操作请求模型。"""
    branch_name: str = Field(..., min_length=1, max_length=255, description="分支名称")
    source_branch: Optional[str] = Field(None, description="源分支（仅创建分支时需要）")
    create_backup: bool = Field(True, description="是否在操作前创建备份")
    backup_expiry_days: int = Field(30, ge=1, le=365, description="备份保留天数")


class BackupRestoreRequest(BaseModel):
    """备份恢复请求模型。"""
    confirm_restore: bool = Field(False, description="确认恢复操作")


@router.post("/projects/{project_id}/commit", summary="安全提交Git变更")
async def commit_changes(
    project_id: str = Path(..., description="项目ID"),
    request: CommitRequest = ...,
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, Any]:
    """
    安全地提交Git变更，可选择在提交前创建备份。

    - **project_id**: 项目唯一标识符
    - **commit_message**: 提交消息，描述本次变更的内容
    - **files_to_commit**: 可选，指定要提交的文件列表。如果为空，则提交所有变更文件
    - **create_backup**: 是否在提交前创建仓库备份
    - **backup_expiry_days**: 备份文件保留天数

    返回操作结果，包括提交哈希、创建的备份信息等。
    """
    try:
        git_service = GitService(db)

        result = await git_service.create_safe_commit(
            project_id=project_id,
            commit_message=request.commit_message,
            files_to_commit=request.files_to_commit,
            create_backup=request.create_backup,
            backup_expiry_days=request.backup_expiry_days
        )

        return {
            "success": True,
            "message": "Git提交成功",
            "data": result
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Git提交失败: {str(e)}")


@router.post("/projects/{project_id}/rollback", summary="安全回滚到指定提交")
async def rollback_changes(
    project_id: str = Path(..., description="项目ID"),
    request: RollbackRequest = ...,
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, Any]:
    """
    安全地回滚到指定的提交哈希，可选择在回滚前创建备份。

    - **project_id**: 项目唯一标识符
    - **target_commit_hash**: 目标提交哈希，支持完整哈希或短哈希（至少7位）
    - **create_backup**: 是否在回滚前创建仓库备份
    - **backup_expiry_days**: 备份文件保留天数

    返回操作结果，包括回滚前后的状态信息、创建的备份信息等。
    """
    try:
        git_service = GitService(db)

        result = await git_service.create_safe_rollback(
            project_id=project_id,
            target_commit_hash=request.target_commit_hash,
            create_backup=request.create_backup,
            backup_expiry_days=request.backup_expiry_days
        )

        return {
            "success": True,
            "message": "Git回滚成功",
            "data": result
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Git回滚失败: {str(e)}")


@router.post("/projects/{project_id}/branches/{branch_name}/create", summary="创建新分支")
async def create_branch(
    project_id: str = Path(..., description="项目ID"),
    branch_name: str = Path(..., description="分支名称"),
    request: BranchOperationRequest = ...,
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, Any]:
    """
    从指定源分支创建新分支。

    - **project_id**: 项目唯一标识符
    - **branch_name**: 新分支的名称
    - **source_branch**: 源分支名称，如果不指定则从当前分支创建
    - **create_backup**: 是否在操作前创建备份
    - **backup_expiry_days**: 备份文件保留天数
    """
    try:
        git_service = GitService(db)

        result = await git_service.create_branch(
            project_id=project_id,
            branch_name=branch_name,
            source_branch=request.source_branch,
            create_backup=request.create_backup,
            backup_expiry_days=request.backup_expiry_days
        )

        return {
            "success": True,
            "message": f"分支 '{branch_name}' 创建成功",
            "data": result
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建分支失败: {str(e)}")


@router.post("/projects/{project_id}/branches/{branch_name}/switch", summary="切换分支")
async def switch_branch(
    project_id: str = Path(..., description="项目ID"),
    branch_name: str = Path(..., description="分支名称"),
    create_backup: bool = Query(True, description="是否在切换前创建备份"),
    backup_expiry_days: int = Query(30, ge=1, le=365, description="备份保留天数"),
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, Any]:
    """
    切换到指定分支。

    - **project_id**: 项目唯一标识符
    - **branch_name**: 目标分支名称
    - **create_backup**: 是否在切换前创建备份
    - **backup_expiry_days**: 备份文件保留天数
    """
    try:
        git_service = GitService(db)

        result = await git_service.switch_branch(
            project_id=project_id,
            branch_name=branch_name,
            create_backup=create_backup,
            backup_expiry_days=backup_expiry_days
        )

        return {
            "success": True,
            "message": f"已切换到分支 '{branch_name}'",
            "data": result
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"切换分支失败: {str(e)}")


@router.get("/projects/{project_id}/operations", summary="获取Git操作历史")
async def get_operation_history(
    project_id: str = Path(..., description="项目ID"),
    operation_type: Optional[str] = Query(None, description="操作类型过滤"),
    limit: int = Query(50, ge=1, le=200, description="返回记录数量限制"),
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, Any]:
    """
    获取指定项目的Git操作历史记录。

    - **project_id**: 项目唯一标识符
    - **operation_type**: 可选，操作类型过滤（commit, rollback, branch_switch等）
    - **limit**: 返回记录的最大数量
    """
    try:
        git_service = GitService(db)

        operations = await git_service.get_operation_history(
            project_id=project_id,
            operation_type=operation_type,
            limit=limit
        )

        return {
            "success": True,
            "data": {
                "operations": operations,
                "total_count": len(operations),
                "project_id": project_id,
                "filters": {
                    "operation_type": operation_type,
                    "limit": limit
                }
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取操作历史失败: {str(e)}")


@router.get("/operations/{operation_id}", summary="获取Git操作详情")
async def get_operation_details(
    operation_id: str = Path(..., description="操作ID"),
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, Any]:
    """
    获取指定Git操作的详细信息，包括相关的备份信息。

    - **operation_id**: Git操作记录的唯一标识符
    """
    try:
        git_service = GitService(db)

        operation = await git_service.get_operation_details(operation_id)

        if not operation:
            raise HTTPException(status_code=404, detail="Git操作记录不存在")

        return {
            "success": True,
            "data": operation
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取操作详情失败: {str(e)}")


@router.get("/projects/{project_id}/backups", summary="获取项目备份列表")
async def get_backup_list(
    project_id: str = Path(..., description="项目ID"),
    include_expired: bool = Query(False, description="是否包含已过期的备份"),
    limit: int = Query(50, ge=1, le=200, description="返回记录数量限制"),
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, Any]:
    """
    获取指定项目的仓库备份列表。

    - **project_id**: 项目唯一标识符
    - **include_expired**: 是否包含已过期的备份
    - **limit**: 返回记录的最大数量
    """
    try:
        git_service = GitService(db)

        backups = await git_service.get_backup_list(
            project_id=project_id,
            include_expired=include_expired,
            limit=limit
        )

        return {
            "success": True,
            "data": {
                "backups": backups,
                "total_count": len(backups),
                "project_id": project_id,
                "filters": {
                    "include_expired": include_expired,
                    "limit": limit
                }
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取备份列表失败: {str(e)}")


@router.post("/backups/{backup_id}/restore", summary="从备份恢复仓库")
async def restore_from_backup(
    backup_id: str = Path(..., description="备份ID"),
    request: BackupRestoreRequest = ...,
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, Any]:
    """
    从指定备份恢复仓库状态。

    **警告**: 此操作将覆盖当前仓库状态，请确保已创建当前状态的备份。

    - **backup_id**: 备份记录的唯一标识符
    - **confirm_restore**: 必须设置为true才能执行恢复操作
    """
    if not request.confirm_restore:
        raise HTTPException(
            status_code=400,
            detail="请确认恢复操作（设置confirm_restore为true）"
        )

    try:
        git_service = GitService(db)

        result = await git_service.restore_from_backup(backup_id)

        return {
            "success": True,
            "message": "仓库恢复成功",
            "data": result
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"恢复备份失败: {str(e)}")


@router.delete("/backups/{backup_id}", summary="删除备份")
async def delete_backup(
    backup_id: str = Path(..., description="备份ID"),
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, Any]:
    """
    删除指定的仓库备份。

    - **backup_id**: 备份记录的唯一标识符
    """
    try:
        git_service = GitService(db)

        success = await git_service.delete_backup(backup_id)

        if not success:
            raise HTTPException(status_code=404, detail="备份记录不存在")

        return {
            "success": True,
            "message": "备份删除成功"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除备份失败: {str(e)}")


@router.post("/projects/{project_id}/backups/cleanup", summary="清理过期备份")
async def cleanup_expired_backups(
    project_id: str = Path(..., description="项目ID"),
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, Any]:
    """
    清理指定项目的所有过期备份。

    - **project_id**: 项目唯一标识符
    """
    try:
        git_service = GitService(db)

        deleted_count = await git_service.delete_expired_backups(project_id)

        return {
            "success": True,
            "message": f"已清理 {deleted_count} 个过期备份",
            "data": {
                "deleted_count": deleted_count,
                "project_id": project_id
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清理过期备份失败: {str(e)}")


@router.get("/projects/{project_id}/status", summary="获取Git仓库状态")
async def get_repository_status(
    project_id: str = Path(..., description="项目ID"),
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, Any]:
    """
    获取指定项目的Git仓库当前状态信息。

    - **project_id**: 项目唯一标识符
    """
    try:
        git_service = GitService(db)

        status = await git_service.get_repository_status(project_id)

        return {
            "success": True,
            "data": status
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取仓库状态失败: {str(e)}")


@router.get("/projects/{project_id}/branches", summary="获取Git分支列表")
async def get_branch_list(
    project_id: str = Path(..., description="项目ID"),
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, Any]:
    """
    获取指定项目的Git分支列表。

    - **project_id**: 项目唯一标识符
    """
    try:
        git_service = GitService(db)

        branches = await git_service.get_branch_list(project_id)

        return {
            "success": True,
            "data": {
                "branches": branches,
                "total_count": len(branches),
                "project_id": project_id
            }
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取分支列表失败: {str(e)}")


@router.get("/projects/{project_id}/commits", summary="获取提交历史")
async def get_commit_history(
    project_id: str = Path(..., description="项目ID"),
    limit: int = Query(50, ge=1, le=200, description="返回记录数量限制"),
    branch: Optional[str] = Query(None, description="分支名称（缺省为当前分支）"),
    db: AsyncSession = Depends(get_async_session)
) -> Dict[str, Any]:
    """
    获取指定项目的Git提交历史记录。

    - **project_id**: 项目唯一标识符
    - **limit**: 返回记录的最大数量
    """
    try:
        git_service = GitService(db)

        commits = await git_service.get_commit_history(project_id, limit, branch)

        return {
            "success": True,
            "data": {
                "commits": commits,
                "total_count": len(commits),
                "project_id": project_id,
                "limit": limit,
                "branch": branch
            }
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取提交历史失败: {str(e)}")