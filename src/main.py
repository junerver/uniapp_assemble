"""
FastAPI application entry point for Android项目资源包替换构建工具.

This module sets up the FastAPI application with middleware, routes,
and configuration for the Android build tool web service.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .config.database import create_database_directory
from .config.settings import get_settings

settings = get_settings()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(settings.log_file) if settings.log_file else logging.StreamHandler(),
        logging.StreamHandler(),
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown events for the FastAPI application.
    """
    # Startup
    logger.info("Starting Android项目构建工具 application...")

    # Create necessary directories
    await create_database_directory()

    # Create uploads and temp directories
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path("temp").mkdir(exist_ok=True)

    logger.info("Application startup completed")

    yield

    # Shutdown
    logger.info("Shutting down Android项目构建工具 application...")
    logger.info("Application shutdown completed")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Android项目资源包替换构建工具 - 帮助Android开发工程师快速完成资源包替换、构建产物和最终提取的全流程",
    lifespan=lifespan,
    debug=settings.debug,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Add trusted host middleware for security
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"] if settings.debug else ["localhost", "127.0.0.1"]
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """
    Add security headers to all responses.
    """
    response = await call_next(request)

    # Add security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    return response


# Include API routers
from .api import projects, files, builds, apks, results, git, health
app.include_router(projects.router)
app.include_router(files.router)
app.include_router(builds.router)
app.include_router(apks.router)
app.include_router(results.router)
app.include_router(git.router)
app.include_router(health.router)

# Mount static files
app.mount("/static", StaticFiles(directory="src/static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def root():
    """
    Serve the main application interface.
    """
    try:
        # Try to serve the main template
        template_path = Path("src/templates/index.html")
        if template_path.exists():
            with open(template_path, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        else:
            # Fallback simple HTML if template doesn't exist yet
            return HTMLResponse(content="""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Android项目构建工具</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .container { max-width: 800px; margin: 0 auto; }
        .status { color: #666; background: #f5f5f5; padding: 20px; border-radius: 8px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔧 Android项目构建工具</h1>
        <div class="status">
            <h3>🚧 系统正在建设中</h3>
            <p>核心功能正在开发中，敬请期待...</p>
            <br>
            <p><strong>API文档</strong>: <a href="/docs">Swagger UI</a></p>
            <p><strong>ReDoc文档</strong>: <a href="/redoc">ReDoc</a></p>
        </div>
    </div>
</body>
</html>
            """)
    except Exception as e:
        logger.error(f"Error serving root page: {e}")
        return HTMLResponse(content="<h1>Service Unavailable</h1>", status_code=503)


@app.get("/health")
async def health_check():
    """
    Simple health check endpoint.
    """
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "debug": settings.debug,
    }


@app.get("/api/info")
async def app_info():
    """
    Get application information.
    """
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": app.description,
        "debug": settings.debug,
        "features": {
            "project_management": "✅ 已实现",
            "file_upload": "✅ 已实现",
            "gradle_build": "✅ 已实现",
            "apk_extraction": "✅ 已实现",
            "git_operations": "✅ 已实现",
        }
    }


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Server will be available at: http://{settings.host}:{settings.port}")

    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        access_log=True,
    )