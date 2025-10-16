"""
Android项目操作服务。

提供Android项目的创建、管理、配置等业务逻辑。
"""

import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from ..models.android_project import AndroidProject
from ..models.project_config import ProjectConfig, ConfigType
from ..database.repositories import BaseAsyncRepository
from ..utils.exceptions import ProjectNotFoundError, ProjectAlreadyExistsError, InvalidProjectPathError, ValidationError

logger = logging.getLogger(__name__)


class AndroidProjectRepository(BaseAsyncRepository[AndroidProject, dict, dict]):
    """Android项目仓储类。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        super().__init__(AndroidProject)

    async def get_by_name(self, name: str) -> Optional[AndroidProject]:
        """根据名称获取项目。"""
        result = await self.get_multi(self.session, name=name, limit=1)
        return result[0] if result else None

    async def list_active(self) -> List[AndroidProject]:
        """获取所有激活的项目。"""
        return await self.get_multi(self.session, is_active=True)

    async def list_all(self) -> List[AndroidProject]:
        """获取所有项目。"""
        return await self.get_multi(self.session)

    async def set_active(self, id: str, is_active: bool) -> bool:
        """设置项目激活状态。"""
        db_obj = await self.get(self.session, id=id)
        if db_obj:
            db_obj.is_active = is_active
            await self.session.commit()
            await self.session.refresh(db_obj)
            return True
        return False


class AndroidProjectService:
    """Android项目服务类。

    提供Android项目的完整业务逻辑，包括创建、验证、配置管理等。
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = AndroidProjectRepository(session)

    async def create_project(
        self,
        name: str,
        path: str,
        alias: Optional[str] = None,
        description: Optional[str] = None,
        git_url: Optional[str] = None,
        main_branch: str = "main"
    ) -> AndroidProject:
        """创建新的Android项目。

        Args:
            name: 项目名称
            path: 项目路径
            alias: 项目别名
            description: 项目描述
            git_url: Git仓库URL
            main_branch: 主分支名称

        Returns:
            创建的AndroidProject对象

        Raises:
            ProjectAlreadyExistsError: 项目名称已存在
            InvalidProjectPathError: 项目路径无效
        """
        logger.info(f"创建Android项目: {name}")

        # 检查项目名称是否已存在
        existing_project = await self.repository.get_by_name(name)
        if existing_project:
            raise ProjectAlreadyExistsError(f"项目名称 '{name}' 已存在")

        # 验证项目路径
        project_path = Path(path)
        if not project_path.exists():
            raise InvalidProjectPathError(f"项目路径不存在: {path}")

        if not project_path.is_dir():
            raise InvalidProjectPathError(f"项目路径不是目录: {path}")

        # 检查是否为Android项目（包含gradle文件）
        gradle_files = list(project_path.glob("**/build.gradle*"))
        if not gradle_files:
            logger.warning(f"路径中未找到Gradle文件，可能不是Android项目: {path}")

        # 创建项目数据
        project_data = {
            "name": name,
            "path": str(project_path.resolve()),
            "alias": alias,
            "description": description,
            "is_active": True
        }

        project = await self.repository.create(
            db=self.session,
            obj_in=project_data
        )

        # 如果提供了Git信息，创建Git配置
        if git_url:
            await self._create_git_config(project.id, git_url, main_branch)

        logger.info(f"Android项目创建成功: {name} (ID: {project.id})")
        return project

    async def get_project(self, project_id: str) -> AndroidProject:
        """获取项目详情。

        Args:
            project_id: 项目ID

        Returns:
            AndroidProject对象

        Raises:
            ProjectNotFoundError: 项目不存在
        """
        project = await self.repository.get(self.session, id=project_id)
        if not project:
            raise ProjectNotFoundError(f"项目不存在: {project_id}")
        return project

    async def list_projects(self, active_only: bool = True) -> List[AndroidProject]:
        """获取项目列表。

        Args:
            active_only: 是否只返回激活的项目

        Returns:
            项目列表
        """
        if active_only:
            return await self.repository.list_active()
        return await self.repository.list_all()

    async def update_project(
        self,
        project_id: str,
        name: Optional[str] = None,
        alias: Optional[str] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> AndroidProject:
        """更新项目信息。

        Args:
            project_id: 项目ID
            name: 新的项目名称
            alias: 新的项目别名
            description: 新的项目描述
            is_active: 新的激活状态

        Returns:
            更新后的AndroidProject对象

        Raises:
            ProjectNotFoundError: 项目不存在
            ProjectAlreadyExistsError: 项目名称已存在
        """
        logger.info(f"更新Android项目: {project_id}")

        project = await self.get_project(project_id)

        # 检查新名称是否冲突
        if name and name != project.name:
            existing_project = await self.repository.get_by_name(name)
            if existing_project:
                raise ProjectAlreadyExistsError(f"项目名称 '{name}' 已存在")

        # 准备更新数据
        update_data = {}
        if name is not None:
            update_data["name"] = name
        if alias is not None:
            update_data["alias"] = alias
        if description is not None:
            update_data["description"] = description
        if is_active is not None:
            update_data["is_active"] = is_active

        if update_data:
            updated_project = await self.repository.update(
                db=self.session,
                db_obj=project,
                obj_in=update_data
            )
            if updated_project:
                logger.info(f"Android项目更新成功: {project_id}")
                return updated_project

        return project

    async def delete_project(self, project_id: str) -> bool:
        """删除项目。

        Args:
            project_id: 项目ID

        Returns:
            是否删除成功

        Raises:
            ProjectNotFoundError: 项目不存在
        """
        logger.info(f"删除Android项目: {project_id}")

        project = await self.get_project(project_id)
        success = await self.repository.delete(db=self.session, id=project_id)

        if success:
            logger.info(f"Android项目删除成功: {project_id}")
        else:
            logger.error(f"Android项目删除失败: {project_id}")

        return success

    async def validate_project_path(self, path: str) -> Dict[str, Any]:
        """验证项目路径。

        Args:
            path: 项目路径

        Returns:
            验证结果字典
        """
        project_path = Path(path)
        result = {
            "valid": False,
            "exists": False,
            "is_directory": False,
            "is_android_project": False,
            "gradle_files": [],
            "error": None
        }

        try:
            # 检查路径是否存在
            if not project_path.exists():
                result["error"] = "路径不存在"
                return result
            result["exists"] = True

            # 检查是否为目录
            if not project_path.is_dir():
                result["error"] = "路径不是目录"
                return result
            result["is_directory"] = True

            # 检查是否为Android项目
            gradle_files = list(project_path.glob("**/build.gradle*"))
            result["gradle_files"] = [str(f.relative_to(project_path)) for f in gradle_files]
            result["is_android_project"] = len(gradle_files) > 0

            if not result["is_android_project"]:
                result["error"] = "未找到Gradle文件，可能不是Android项目"
                return result

            result["valid"] = True

        except Exception as e:
            result["error"] = f"路径验证错误: {str(e)}"
            logger.error(f"项目路径验证失败: {path}, 错误: {e}")

        return result

    async def get_project_configs(self, project_id: str) -> List[ProjectConfig]:
        """获取项目配置。

        Args:
            project_id: 项目ID

        Returns:
            项目配置列表
        """
        result = await self.session.execute(
            select(ProjectConfig).where(ProjectConfig.project_id == project_id)
        )
        return result.scalars().all()

    async def _create_git_config(self, project_id: UUID, git_url: str, main_branch: str) -> None:
        """创建Git配置。"""
        git_config = ProjectConfig.create_git_config(
            project_id=project_id,
            git_url=git_url,
            main_branch=main_branch
        )
        self.session.add(git_config)
        await self.session.commit()
        logger.info(f"Git配置创建成功: {project_id}")

    async def get_project_build_info(self, project_id: str) -> Dict[str, Any]:
        """获取项目构建信息。

        Args:
            project_id: 项目ID

        Returns:
            构建信息字典
        """
        project = await self.get_project(project_id)
        project_path = Path(project.path)

        # 获取Git信息
        from ..utils.git_utils import GitUtils
        git_info = {}
        try:
            if GitUtils.is_git_repository(project_path):
                git_info = GitUtils.get_repository_info(project_path)
        except Exception as e:
            logger.warning(f"获取Git信息失败: {e}")

        # 获取Gradle信息
        from ..utils.gradle_utils import GradleUtils
        gradle_info = {}
        try:
            gradle_utils = GradleUtils(project_path)
            if gradle_utils.is_gradle_project():
                gradle_info = {
                    "is_gradle_project": True,
                    "gradle_version": gradle_utils.get_gradle_version(),
                    "available_tasks": gradle_utils.get_available_tasks(),
                    "build_variants": gradle_utils.get_build_variants(),
                    "build_flavors": gradle_utils.get_build_flavors(),
                    "project_info": gradle_utils.get_project_info()
                }
        except Exception as e:
            logger.warning(f"获取Gradle信息失败: {e}")

        return {
            "project": project.to_dict(),
            "git_info": git_info,
            "gradle_info": gradle_info,
            "build_environment_valid": bool(git_info and gradle_info.get("is_gradle_project", False))
        }

    async def validate_build_environment(self, project_id: str) -> Dict[str, Any]:
        """验证项目构建环境。

        Args:
            project_id: 项目ID

        Returns:
            验证结果字典
        """
        project = await self.get_project(project_id)
        project_path = Path(project.path)

        validation_result = {
            "valid": True,
            "issues": [],
            "warnings": [],
            "recommendations": [],
            "checks": {}
        }

        # 检查项目路径
        if not project_path.exists():
            validation_result["valid"] = False
            validation_result["issues"].append("项目路径不存在")
            return validation_result

        validation_result["checks"]["project_exists"] = True

        # 检查Gradle环境
        from ..utils.gradle_utils import GradleUtils
        try:
            gradle_utils = GradleUtils(project_path)
            gradle_validation = gradle_utils.validate_build_environment()
            validation_result["checks"]["gradle_environment"] = gradle_validation

            if not gradle_validation["valid"]:
                validation_result["valid"] = False
                validation_result["issues"].extend(gradle_validation["issues"])

            validation_result["warnings"].extend(gradle_validation["warnings"])

        except Exception as e:
            validation_result["valid"] = False
            validation_result["issues"].append(f"Gradle环境检查失败: {e}")

        # 检查Git环境
        from ..utils.git_utils import GitUtils
        try:
            if GitUtils.is_git_repository(project_path):
                validation_result["checks"]["git_environment"] = {"valid": True}
            else:
                validation_result["warnings"].append("项目不是Git仓库")
                validation_result["recommendations"].append("初始化Git仓库以便版本控制")
        except Exception as e:
            validation_result["warnings"].append(f"Git环境检查失败: {e}")

        # 检查关键文件
        critical_files = [
            "app/build.gradle",
            "gradle.properties",
            "settings.gradle"
        ]

        missing_files = []
        for file_path in critical_files:
            full_path = project_path / file_path
            if not full_path.exists():
                missing_files.append(file_path)

        if missing_files:
            validation_result["checks"]["critical_files"] = {
                "present": len(critical_files) - len(missing_files),
                "missing": missing_files
            }
            validation_result["warnings"].append(f"缺少关键文件: {', '.join(missing_files)}")
        else:
            validation_result["checks"]["critical_files"] = {"present": len(critical_files), "missing": []}

        return validation_result

    async def get_project_branches(self, project_id: str) -> Dict[str, Any]:
        """获取项目的Git分支信息。

        Args:
            project_id: 项目ID

        Returns:
            分支信息字典
        """
        project = await self.get_project(project_id)
        project_path = Path(project.path)

        from ..utils.git_utils import GitUtils
        try:
            if not GitUtils.is_git_repository(project_path):
                return {
                    "is_git_repository": False,
                    "error": "项目不是Git仓库"
                }

            branches = GitUtils.get_all_branches(project_path)
            current_branch = GitUtils.get_current_branch(project_path)

            return {
                "is_git_repository": True,
                "current_branch": current_branch,
                "all_branches": branches,
                "local_branches": [b for b in branches if not b.startswith("origin/")],
                "remote_branches": [b for b in branches if b.startswith("origin/")]
            }

        except Exception as e:
            logger.error(f"获取分支信息失败: {e}")
            return {
                "is_git_repository": False,
                "error": f"获取分支信息失败: {str(e)}"
            }

    async def create_build_task_for_project(
        self,
        project_id: str,
        task_type: str,
        git_branch: str,
        resource_package_path: Optional[str] = None,
        config_options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """为项目创建构建任务。

        Args:
            project_id: 项目ID
            task_type: 任务类型
            git_branch: Git分支
            resource_package_path: 资源包路径
            config_options: 配置选项

        Returns:
            创建结果
        """
        try:
            # 验证项目
            await self.get_project(project_id)

            # 验证构建环境
            validation = await self.validate_build_environment(project_id)
            if not validation["valid"]:
                raise ValidationError(f"构建环境验证失败: {'; '.join(validation['issues'])}")

            # 这里会调用BuildService来创建任务
            # 实际的任务创建会在API层处理
            return {
                "project_id": project_id,
                "task_type": task_type,
                "git_branch": git_branch,
                "validation": validation,
                "ready_for_build": True
            }

        except Exception as e:
            logger.error(f"为项目创建构建任务失败: {e}")
            raise