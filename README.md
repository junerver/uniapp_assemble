# Android项目资源包替换构建工具

一个基于 FastAPI 的Web工具，帮助Android开发工程师**快速完成资源包替换、自动化构建和APK产物提取**的全流程。项目使用规范驱动开发工作流程，具有章程治理。

## ✨ 核心功能

### 1. 项目配置和资源包上传 (User Story 1) ✅
- 📁 Android项目管理和配置
- 🌳 Git分支自动检测
- ⬆️ 拖拽式资源包上传（支持ZIP格式）
- ✔️ 资源包格式验证

### 2. 自动化资源替换和构建 (User Story 2) ✅
- 🔄 自动资源文件替换
- 🏗️ Gradle自动化构建
- 📡 实时构建日志WebSocket推送
- ⚡ 构建进度实时tracking
- 🛡️ Git安全检查（防止误操作）

### 3. 构建产物提取和管理 (User Story 3) ✅
- 📦 APK文件自动扫描和提取
- 🔍 APK元数据分析（包名、版本、权限等）
- ⬇️ APK文件下载功能
- 📊 构建结果历史记录
- 🔐 Base64编码路径方案（解决Windows路径问题）

### 4. Git提交和回滚管理 (User Story 4) ✅
- 💾 Git安全提交（自动备份）
- ⏪ Git回滚到指定commit
- 📜 Git操作历史跟踪
- 🗃️ 仓库备份和恢复
- 🔄 自动过期备份清理

## 🚀 快速开始

### 系统要求

- **Python**: 3.13+
- **操作系统**: Windows 10/11, macOS 10.15+, Linux
- **包管理器**: UV (推荐) 或 pip
- **解压工具**: 支持多种压缩格式需要安装:
  - **7-Zip**: 用于解压 .7z 和 .rar 文件 (推荐)
  - **WinRAR**: 或使用 WinRAR 解压 .rar 文件

#### 安装解压工具 (可选 - 用于 RAR/7Z 格式支持)

**Windows**:
```bash
# 使用 Chocolatey 安装 7-Zip
choco install 7zip

# 或从官网下载安装: https://www.7-zip.org/
```

**macOS**:
```bash
# 使用 Homebrew 安装 7-Zip
brew install p7zip
```

**Linux**:
```bash
# Ubuntu/Debian
sudo apt-get install p7zip-full unrar

# CentOS/RHEL
sudo yum install p7zip p7zip-plugins unrar
```

> **注意**: 如果不安装这些工具,系统仍然支持 ZIP 格式的资源包,但无法处理 RAR 和 7Z 格式。

### 使用UV包管理器（推荐）

#### 1. 安装UV

```bash
# 方法1: 官方安装脚本（推荐）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 方法2: 使用pip安装
pip install uv

# 方法3: 使用包管理器
# macOS: brew install uv
# Windows: winget install uv
# Linux: cargo install uv
```

#### 2. 克隆项目并设置环境

```bash
# 克隆项目
git clone <repository-url>
cd uniapp_assemble

# 创建虚拟环境并安装依赖
uv venv
uv sync --dev

# 激活虚拟环境
source .venv/bin/activate  # Linux/macOS
# 或 .venv\Scripts\activate  # Windows
```

#### 3. 运行应用

```bash
# 启动FastAPI服务器
uv run python -m src.main

# 或使用uvicorn直接运行
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

## 📋 开发工作流程

本项目遵循结构化的**规范驱动开发**流程。

### 开发命令

```bash
# 运行测试
uv run pytest

# 代码格式化
uv run black src/
uv run ruff format src/

# 代码检查
uv run ruff check src/
uv run mypy src/
```

## 🏗️ 项目结构

```
├── .specify/                    # 规范驱动开发框架
├── specs/                       # 功能规范
├── src/                        # 源代码目录
├── tests/                      # 测试文件
├── pyproject.toml             # Python 项目配置和依赖管理
├── uv.lock                    # UV依赖锁定文件
└── README.md                  # 本文件
```

## 🛠️ 技术栈

- **后端框架**: FastAPI 0.115+
- **异步ORM**: SQLAlchemy 2.0 async
- **数据库**: SQLite (开发/生产)
- **实时通信**: WebSocket
- **代码质量**: Ruff, Black, MyPy
- **测试**: Pytest, Pytest-asyncio
- **包管理**: UV (极速Python包管理器)
- **前端**: HTML5 + Tailwind CSS + Vanilla JavaScript

## 📡 API端点

### 项目管理
- `POST /api/projects` - 创建Android项目
- `GET /api/projects/{project_id}` - 获取项目信息
- `PUT /api/projects/{project_id}` - 更新项目配置
- `GET /api/projects/{project_id}/branches` - 获取Git分支列表

### 文件管理
- `POST /api/files/upload` - 上传资源包
- `GET /api/files/download-base64?encoded_path={path}` - 下载文件（Base64编码路径）
- `POST /api/files/validate` - 验证资源包格式

### 构建管理
- `POST /api/builds` - 创建构建任务
- `GET /api/builds/{build_id}` - 获取构建状态
- `GET /api/builds/{build_id}/logs` - 获取构建日志
- `WS /api/ws/{build_id}` - WebSocket实时构建日志

### APK管理
- `GET /api/apks/projects/{project_id}/apks` - 扫描项目APK文件
- `GET /api/apks/files/{path}/info` - 获取APK详细信息
- `POST /api/apks/compare` - 比较两个APK文件

### Git操作
- `POST /api/git/commit` - Git安全提交（带备份）
- `POST /api/git/rollback` - Git回滚到指定commit
- `GET /api/git/history/{project_id}` - 查看commit历史
- `GET /api/git/backups/{project_id}` - 查看备份列表
- `POST /api/git/restore/{backup_id}` - 从备份恢复

### 健康检查
- `GET /api/health/` - 基础健康检查
- `GET /api/health/detailed` - 详细健康检查（含数据库和目录状态）
- `GET /api/health/liveness` - Kubernetes liveness probe
- `GET /api/health/readiness` - Kubernetes readiness probe

### API文档
- `GET /docs` - Swagger UI交互式文档
- `GET /redoc` - ReDoc文档

## 📊 性能指标

使用UV包管理器带来的性能提升：

| 操作 | pip | UV | 性能提升 |
|------|-----|----|---------|
| 依赖安装 | 5-10分钟 | 30-60秒 | 10-20x |
| 虚拟环境创建 | 1-2分钟 | 10-30秒 | 4-8x |
| 依赖解析 | 30-60秒 | 5-10秒 | 6-12x |

---

## ⚙️ 配置说明

### 环境变量

创建 `.env` 文件（参考 `.env.example`）：

```bash
# 应用配置
APP_NAME="Android项目构建工具"
APP_VERSION="1.0.0"
DEBUG=true

# 服务器配置
HOST=0.0.0.0
PORT=8000

# 数据库配置
DATABASE_URL=sqlite+aiosqlite:///./data/app.db

# 目录配置
UPLOAD_DIR=./uploads
TEMP_DIR=./temp

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=./logs/app.log

# CORS配置
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
```

### 目录结构说明

应用启动时会自动创建以下目录：

```
.
├── data/                  # SQLite数据库文件
├── uploads/               # 用户上传的资源包
├── temp/                  # 临时文件（解压缩等）
├── logs/                  # 应用日志
└── backups/               # Git仓库备份
    └── {project_id}/      # 按项目ID组织的备份
```

## 🔒 安全特性

- ✅ 文件路径安全验证（防止路径遍历攻击）
- ✅ Base64编码文件路径（防止路径注入）
- ✅ Git操作前自动备份
- ✅ 资源包格式验证
- ✅ CORS跨域请求控制
- ✅ 安全HTTP headers（X-Frame-Options, X-XSS-Protection等）
- ✅ 输入数据验证（Pydantic models）

## 🚧 故障排除

### 问题：数据库锁定错误
**解决方案**: SQLite在高并发时可能出现锁定，建议生产环境使用PostgreSQL

### 问题：APK下载路径错误
**解决方案**: 已使用Base64编码方案解决Windows路径反斜杠问题

### 问题：Gradle构建失败
**解决方案**:
1. 确保Android SDK已正确安装
2. 检查gradlew文件是否有执行权限
3. 查看WebSocket实时日志定位具体错误

### 问题：Git操作失败
**解决方案**:
1. 确保工作目录干净（无未提交更改）
2. 检查分支是否正确
3. 查看Git操作日志

## 📝 开发规范

本项目遵循**规范驱动开发（Specification-Driven Development）**流程：

1. **规范编写** (`/speckit.specify`) - 定义功能需求和验收标准
2. **实施计划** (`/speckit.plan`) - 设计技术方案和架构
3. **任务分解** (`/speckit.tasks`) - 生成可执行的任务列表
4. **实施开发** (`/speckit.implement`) - 按任务顺序实施

详见 `.specify/memory/constitution.md`

## 🤝 贡献指南

1. Fork 本仓库
2. 创建feature分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 详见 LICENSE 文件

---

**注意**: 本项目已迁移到UV包管理工具。旧的requirements.txt文件已备份为requirements.txt.backup，建议使用UV进行依赖管理以获得最佳性能。
