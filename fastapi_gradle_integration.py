"""
FastAPI与Gradle构建系统的异步集成
提供REST API、WebSocket实时通信、文件上传下载等功能
"""

import asyncio
import os
import json
from typing import Dict, Any, List, Optional, Set
from pathlib import Path
import tempfile
import shutil
import zipfile
from datetime import datetime

from fastapi import (
    FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File,
    HTTPException, BackgroundTasks, Query, Depends
)
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from gradle_monitor import (
    GradleBuildManager, BuildStatus, BuildResult, GradleAsyncExecutor
)


# Pydantic模型定义
class BuildRequest(BaseModel):
    project_path: str
    tasks: List[str] = ["assembleDebug"]
    timeout: int = 600
    build_flavor: Optional[str] = None
    build_type: Optional[str] = None


class BuildResponse(BaseModel):
    build_id: str
    status: str
    message: str
    submitted_at: datetime


class BuildStatusResponse(BaseModel):
    build_id: str
    status: str
    progress: float
    current_step: str
    start_time: datetime
    duration: Optional[float]
    apk_path: Optional[str]
    error_message: Optional[str]


class WebSocketMessage(BaseModel):
    type: str  # 'log', 'progress', 'status', 'error'
    build_id: str
    data: Dict[str, Any]
    timestamp: datetime


class ProjectUploadResponse(BaseModel):
    project_id: str
    project_path: str
    extracted_path: str
    message: str


class ConnectionManager:
    """WebSocket连接管理器"""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.build_subscriptions: Dict[str, Set[str]] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        """建立WebSocket连接"""
        await websocket.accept()

        if client_id not in self.active_connections:
            self.active_connections[client_id] = set()

        self.active_connections[client_id].add(websocket)
        print(f"客户端已连接: {client_id}")

    def disconnect(self, websocket: WebSocket, client_id: str):
        """断开WebSocket连接"""
        if client_id in self.active_connections:
            self.active_connections[client_id].discard(websocket)

            # 清理空连接集合
            if not self.active_connections[client_id]:
                del self.active_connections[client_id]

        # 清理订阅
        for build_id, subscribers in self.build_subscriptions.items():
            if client_id in subscribers:
                subscribers.remove(client_id)

        print(f"客户端已断开: {client_id}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """发送个人消息"""
        await websocket.send_text(message)

    async def broadcast_to_build(self, build_id: str, message: Dict[str, Any]):
        """向特定构建的订阅者广播消息"""
        subscribers = self.build_subscriptions.get(build_id, set())

        for client_id in subscribers:
            if client_id in self.active_connections:
                websockets = self.active_connections[client_id]
                for websocket in websockets:
                    try:
                        await websocket.send_text(json.dumps(message, default=str))
                    except Exception as e:
                        print(f"发送消息失败: {e}")

    def subscribe_to_build(self, client_id: str, build_id: str):
        """订阅构建更新"""
        if build_id not in self.build_subscriptions:
            self.build_subscriptions[build_id] = set()

        self.build_subscriptions[build_id].add(client_id)

    def unsubscribe_from_build(self, client_id: str, build_id: str):
        """取消订阅构建更新"""
        if build_id in self.build_subscriptions:
            self.build_subscriptions[build_id].discard(client_id)


class ProjectManager:
    """项目管理器 - 处理项目上传和解压"""

    def __init__(self, projects_dir: str = "projects"):
        self.projects_dir = Path(projects_dir)
        self.projects_dir.mkdir(exist_ok=True)
        self.projects: Dict[str, Dict[str, Any]] = {}

    async def upload_project(self, file: UploadFile) -> ProjectUploadResponse:
        """上传并解压项目文件"""
        project_id = f"project_{int(datetime.now().timestamp())}"
        project_path = self.projects_dir / project_id

        try:
            # 创建项目目录
            project_path.mkdir(exist_ok=True)

            # 保存上传的文件
            zip_path = project_path / file.filename
            with open(zip_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)

            # 解压项目
            extracted_path = project_path / "extracted"
            extracted_path.mkdir(exist_ok=True)

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extracted_path)

            # 查找Android项目根目录
            android_root = self._find_android_root(extracted_path)

            if not android_root:
                raise HTTPException(
                    status_code=400,
                    detail="上传的文件不是有效的Android项目"
                )

            # 保存项目信息
            self.projects[project_id] = {
                "project_id": project_id,
                "project_path": str(android_root),
                "extracted_path": str(extracted_path),
                "uploaded_at": datetime.now(),
                "filename": file.filename
            }

            return ProjectUploadResponse(
                project_id=project_id,
                project_path=str(android_root),
                extracted_path=str(extracted_path),
                message="项目上传并解压成功"
            )

        except Exception as e:
            # 清理失败的文件
            if project_path.exists():
                shutil.rmtree(project_path)
            raise HTTPException(status_code=500, detail=f"项目处理失败: {str(e)}")

    def _find_android_root(self, extracted_path: Path) -> Optional[Path]:
        """查找Android项目根目录"""
        # 查找build.gradle或settings.gradle文件
        for root, dirs, files in os.walk(extracted_path):
            if "build.gradle" in files or "settings.gradle" in files:
                return Path(root)
        return None

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """获取项目信息"""
        return self.projects.get(project_id)

    def delete_project(self, project_id: str) -> bool:
        """删除项目"""
        if project_id not in self.projects:
            return False

        project_info = self.projects[project_id]
        project_path = Path(project_info["extracted_path"])

        try:
            if project_path.exists():
                shutil.rmtree(project_path)

            del self.projects[project_id]
            return True

        except Exception as e:
            print(f"删除项目失败: {e}")
            return False


# 创建FastAPI应用
app = FastAPI(
    title="Gradle构建API",
    description="基于FastAPI的Gradle构建管理系统",
    version="1.0.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局实例
build_manager = GradleBuildManager(max_concurrent_builds=3)
connection_manager = ConnectionManager()
project_manager = ProjectManager()


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    await build_manager.start()
    print("FastAPI应用已启动，构建管理器已初始化")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    await build_manager.stop()
    print("FastAPI应用已关闭")


# REST API端点
@app.post("/api/projects/upload", response_model=ProjectUploadResponse)
async def upload_project(file: UploadFile = File(...)):
    """上传Android项目文件"""
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="只支持ZIP文件格式")

    return await project_manager.upload_project(file)


@app.get("/api/projects")
async def list_projects():
    """列出所有项目"""
    return {"projects": list(project_manager.projects.values())}


@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    """获取项目信息"""
    project = project_manager.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    """删除项目"""
    success = project_manager.delete_project(project_id)
    if not success:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"message": "项目删除成功"}


@app.post("/api/builds", response_model=BuildResponse)
async def submit_build(
    request: BuildRequest,
    background_tasks: BackgroundTasks
):
    """提交构建任务"""

    # 验证项目路径
    project_path = Path(request.project_path)
    if not project_path.exists():
        raise HTTPException(status_code=404, detail="项目路径不存在")

    # 创建日志回调
    def log_callback(log_entry):
        asyncio.create_task(
            connection_manager.broadcast_to_build(
                build_id,
                {
                    "type": "log",
                    "build_id": build_id,
                    "data": log_entry,
                    "timestamp": datetime.now()
                }
            )
        )

    # 创建进度回调
    def progress_callback(progress):
        asyncio.create_task(
            connection_manager.broadcast_to_build(
                build_id,
                {
                    "type": "progress",
                    "build_id": build_id,
                    "data": {
                        "percentage": progress.percentage,
                        "current_step": progress.current_step,
                        "current_file": progress.current_file
                    },
                    "timestamp": datetime.now()
                }
            )
        )

    # 提交构建任务
    build_id = await build_manager.submit_build(
        request.project_path,
        request.tasks,
        request.timeout,
        log_callback,
        progress_callback
    )

    return BuildResponse(
        build_id=build_id,
        status=BuildStatus.QUEUED.value,
        message="构建任务已提交",
        submitted_at=datetime.now()
    )


@app.get("/api/builds/{build_id}", response_model=BuildStatusResponse)
async def get_build_status(build_id: str):
    """获取构建状态"""
    result = await build_manager.get_build_status(build_id)

    if not result:
        raise HTTPException(status_code=404, detail="构建任务不存在")

    return BuildStatusResponse(
        build_id=result.build_id,
        status=result.status.value,
        progress=result.progress.percentage,
        current_step=result.progress.current_step,
        start_time=result.start_time,
        duration=result.duration,
        apk_path=result.apk_path,
        error_message=result.error_message
    )


@app.post("/api/builds/{build_id}/cancel")
async def cancel_build(build_id: str):
    """取消构建"""
    success = await build_manager.cancel_build(build_id)

    if not success:
        raise HTTPException(status_code=404, detail="构建任务不存在或无法取消")

    # 广播取消消息
    await connection_manager.broadcast_to_build(
        build_id,
        {
            "type": "status",
            "build_id": build_id,
            "data": {"status": "cancelled"},
            "timestamp": datetime.now()
        }
    )

    return {"message": "构建已取消"}


@app.get("/api/builds/{build_id}/download")
async def download_apk(build_id: str):
    """下载构建生成的APK文件"""
    result = await build_manager.get_build_status(build_id)

    if not result:
        raise HTTPException(status_code=404, detail="构建任务不存在")

    if result.status != BuildStatus.SUCCESS:
        raise HTTPException(status_code=400, detail="构建未成功完成")

    if not result.apk_path or not Path(result.apk_path).exists():
        raise HTTPException(status_code=404, detail="APK文件不存在")

    return FileResponse(
        result.apk_path,
        media_type="application/vnd.android.package-archive",
        filename=Path(result.apk_path).name
    )


@app.get("/api/builds")
async def list_builds():
    """列出所有构建任务"""
    builds = []

    for build_id, result in build_manager.active_builds.items():
        builds.append({
            "build_id": build_id,
            "status": result.status.value,
            "start_time": result.start_time,
            "duration": result.duration,
            "progress": result.progress.percentage
        })

    return {"builds": builds}


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket端点 - 实时通信"""
    await connection_manager.connect(websocket, client_id)

    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            message = json.loads(data)

            message_type = message.get("type")

            if message_type == "subscribe":
                # 订阅构建更新
                build_id = message.get("build_id")
                if build_id:
                    connection_manager.subscribe_to_build(client_id, build_id)

                    # 发送当前状态
                    result = await build_manager.get_build_status(build_id)
                    if result:
                        await connection_manager.send_personal_message(
                            json.dumps({
                                "type": "status",
                                "build_id": build_id,
                                "data": {
                                    "status": result.status.value,
                                    "progress": result.progress.percentage,
                                    "start_time": result.start_time,
                                    "duration": result.duration
                                },
                                "timestamp": datetime.now()
                            }, default=str),
                            websocket
                        )

            elif message_type == "unsubscribe":
                # 取消订阅
                build_id = message.get("build_id")
                if build_id:
                    connection_manager.unsubscribe_from_build(client_id, build_id)

            elif message_type == "ping":
                # 心跳检测
                await connection_manager.send_personal_message(
                    json.dumps({"type": "pong"}),
                    websocket
                )

    except WebSocketDisconnect:
        connection_manager.disconnect(websocket, client_id)
    except Exception as e:
        print(f"WebSocket错误: {e}")
        connection_manager.disconnect(websocket, client_id)


# 健康检查端点
@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "active_builds": len(build_manager.active_builds),
        "connected_clients": len(connection_manager.active_connections)
    }


# 性能监控端点
@app.get("/api/stats")
async def get_stats():
    """获取系统统计信息"""
    stats = {
        "active_builds": len(build_manager.active_builds),
        "connected_clients": len(connection_manager.active_connections),
        "build_subscriptions": len(connection_manager.build_subscriptions),
        "total_projects": len(project_manager.projects),
        "build_statuses": {}
    }

    # 统计构建状态
    for result in build_manager.active_builds.values():
        status = result.status.value
        stats["build_statuses"][status] = stats["build_statuses"].get(status, 0) + 1

    return stats


def create_app():
    """创建FastAPI应用实例"""
    return app


if __name__ == "__main__":
    # 运行应用
    uvicorn.run(
        "fastapi_gradle_integration:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )