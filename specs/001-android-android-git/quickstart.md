# 快速启动指南 - Android项目资源包替换构建工具

**项目**: Android项目资源包替换构建工具
**版本**: 1.0.0
**创建**: 2025-10-15
**架构**: FastAPI + SQLite + Tailwind CSS

## 🚀 快速开始

### 系统要求

- **Python**: 3.13+
- **操作系统**: Windows 10/11, macOS 10.15+, Linux
- **内存**: 最少 4GB RAM
- **存储**: 最少 2GB 可用空间
- **Git**: 2.0+ (可选，用于版本控制)

### 5分钟快速部署

#### 步骤 1: 克隆和安装

```bash
# 克隆项目
git clone <repository-url>
cd uniapp_assemble

# 安装依赖
pip install -e .

# 验证安装
python -c "import fastapi, sqlalchemy, pydantic; print('✅ 所有依赖已安装')"
```

#### 步骤 2: 初始化数据库

```bash
# 初始化SQLite数据库
python -c "
from src.database.init_db import init_database
import asyncio
asyncio.run(init_database())
print('✅ 数据库初始化完成')
"
```

#### 步骤 3: 启动服务

```bash
# 启动开发服务器
python main.py

# 或者使用uvicorn (推荐)
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

#### 步骤 4: 访问应用

打开浏览器访问: **http://localhost:8000**

## 📋 功能概览

### 核心功能

1. **📁 项目管理**
   - 添加/删除Android项目
   - 项目配置管理
   - Git分支选择

2. **📦 资源包上传**
   - 拖拽上传 (最大500MB)
   - 实时上传进度
   - 文件安全验证

3. **🔧 资源替换**
   - 自动资源替换
   - 智能路径匹配
   - 备份和恢复

4. **🏗️ Gradle构建**
   - 异步构建执行
   - 实时日志监控
   - 构建状态跟踪

5. **📱 APK提取**
   - 自动APK检测
   - 文件下载管理
   - 元数据提取

6. **🔄 Git操作**
   - 安全提交操作
   - 智能回滚机制
   - 操作历史记录

### 界面预览

```
┌─────────────────────────────────────────────────────┐
│  Android项目资源包替换构建工具                        │
├─────────────────────────────────────────────────────┤
│  [项目管理] [构建历史] [Git操作] [设置]              │
├─────────────────────────────────────────────────────┤
│  ┌─ 项目配置 ──┐  ┌─ 资源包上传 ──┐                │
│  │ 项目选择:    │  │ 拖拽文件到此处 │                │
│  │ [下拉菜单]   │  │ 或点击选择     │                │
│  │ Git分支:     │  │               │                │
│  │ [分支列表]   │  │ 上传进度: 85% │                │
│  │             │  │ [选择文件]    │                │
│  └─────────────┘  └─────────────────┘                │
│                                                     │
│  ┌─ 构建控制 ──┐  ┌─ 实时日志 ──┐                   │
│  │ [开始构建]  │  │ > Task :processDebugResources   │
│  │ [停止构建]  │  │ > Resource replacement done     │
│  │ [下载APK]   │  │ > Gradle build completed       │
│  │ [Git提交]   │  │ > APK extracted successfully    │
│  │ [Git回滚]   │  │                               │
│  └─────────────┘  └─────────────────┘               │
└─────────────────────────────────────────────────────┘
```

## 🛠️ 开发指南

### 项目结构

```
src/
├── main.py                 # FastAPI应用入口
├── api/                    # API路由
│   ├── __init__.py
│   ├── projects.py         # 项目管理API
│   ├── builds.py          # 构建任务API
│   ├── git.py             # Git操作API
│   └── websocket.py       # WebSocket连接
├── models/                 # Pydantic数据模型
│   ├── __init__.py
│   ├── project.py         # 项目模型
│   ├── build.py           # 构建模型
│   └── git.py             # Git操作模型
├── database/               # 数据库相关
│   ├── __init__.py
│   ├── models.py          # SQLAlchemy ORM模型
│   ├── database.py        # 数据库连接
│   └── repositories.py    # 数据访问层
├── services/               # 业务逻辑服务
│   ├── __init__.py
│   ├── project_service.py  # 项目管理服务
│   ├── build_service.py    # 构建服务
│   ├── git_service.py      # Git操作服务
│   └── file_service.py     # 文件处理服务
├── utils/                  # 工具函数
│   ├── __init__.py
│   ├── git_utils.py        # Git操作工具
│   ├── gradle_utils.py     # Gradle构建工具
│   └── file_utils.py       # 文件处理工具
└── templates/              # 前端模板
    ├── index.html          # 主页面
    ├── css/                # 样式文件
    │   └── main.css        # Tailwind CSS
    └── js/                 # JavaScript文件
        └── main.js         # 前端逻辑
```

### 开发环境设置

```bash
# 开发模式安装
pip install -e ".[dev]"

# 代码格式化
black src/
ruff check src/

# 类型检查
mypy src/

# 运行测试
pytest tests/ -v --cov=src
```

### 环境变量配置

创建 `.env` 文件：

```bash
# 应用配置
APP_NAME="Android项目构建工具"
APP_VERSION="1.0.0"
DEBUG=true

# 数据库配置
DATABASE_URL="sqlite+aiosqlite:///./android_builder.db"

# 文件存储配置
UPLOAD_DIR="./uploads"
MAX_FILE_SIZE=524288000  # 500MB

# Git配置
GIT_AUTO_BACKUP=true
GIT_COMMIT_AUTHOR="Android Builder <builder@example.com>"

# 构建配置
GRADLE_TIMEOUT=1800  # 30分钟
MAX_CONCURRENT_BUILDS=3
```

## 📊 API 使用示例

### 1. 创建项目

```bash
curl -X POST "http://localhost:8000/api/projects" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "MyAndroidApp",
    "path": "/path/to/android/project",
    "description": "我的Android应用项目"
  }'
```

### 2. 上传资源包

```bash
curl -X POST "http://localhost:8000/api/projects/{project_id}/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@resources.zip"
```

### 3. 开始构建

```bash
curl -X POST "http://localhost:8000/api/builds" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "project-uuid",
    "resource_package_path": "/path/to/resources.zip",
    "git_branch": "main"
  }'
```

### 4. 监控构建进度

```javascript
// WebSocket连接
const ws = new WebSocket('ws://localhost:8000/ws/builds/{build_id}');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('构建状态:', data.status);
    console.log('进度:', data.progress);
    console.log('日志:', data.log_message);
};
```

### 5. Git操作

```bash
# 提交构建结果
curl -X POST "http://localhost:8000/api/git/{project_id}/commit" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "更新资源包 - 2025-10-15",
    "author": "开发者 <dev@example.com>"
  }'

# 回滚到之前状态
curl -X POST "http://localhost:8000/api/git/{project_id}/rollback" \
  -H "Content-Type: application/json" \
  -d '{
    "target_commit": "commit-hash"
  }'
```

## 🔧 配置说明

### Android项目要求

1. **Gradle配置**: 项目必须包含 `build.gradle` 或 `build.gradle.kts`
2. **资源结构**: 标准Android资源目录结构 (`res/`, `assets/`)
3. **Git仓库**: 可选，但推荐使用以获得版本控制功能

### 资源包要求

- **格式**: ZIP压缩包
- **大小**: 最大500MB
- **结构**: 必须符合Android资源目录结构
- **安全**: 通过文件类型验证和病毒扫描

### 构建配置

```json
{
  "build_config": {
    "gradle_tasks": ["assembleDebug"],
    "build_type": "debug",
    "output_dir": "build/outputs/apk/debug",
    "timeout": 1800,
    "environment": {
      "ANDROID_HOME": "/path/to/android/sdk",
      "JAVA_HOME": "/path/to/java"
    }
  }
}
```

## 🐛 故障排除

### 常见问题

#### 1. 构建失败
```bash
# 检查Gradle环境
./gradlew --version

# 清理构建缓存
./gradlew clean

# 检查Android SDK路径
echo $ANDROID_HOME
```

#### 2. Git操作失败
```bash
# 检查Git状态
git status

# 检查远程仓库
git remote -v

# 重置到干净状态
git reset --hard HEAD
```

#### 3. 文件上传问题
```bash
# 检查文件权限
ls -la uploads/

# 检查磁盘空间
df -h

# 检查文件大小
du -h your-resource.zip
```

### 日志查看

```bash
# 应用日志
tail -f logs/app.log

# 构建日志
tail -f logs/build.log

# Git操作日志
tail -f logs/git.log
```

### 性能优化

1. **数据库优化**
   ```bash
   # 启用WAL模式
   sqlite3 android_builder.db "PRAGMA journal_mode=WAL;"

   # 添加索引
   sqlite3 android_builder.db ".schema"
   ```

2. **内存优化**
   ```python
   # 限制并发构建数量
   MAX_CONCURRENT_BUILDS = 3

   # 启用文件压缩
   ENABLE_FILE_COMPRESSION = True
   ```

## 📚 更多资源

### 文档
- [完整API文档](http://localhost:8000/docs)
- [数据模型设计](data-model.md)
- [架构设计文档](plan.md)

### 开发工具
- [FastAPI文档](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/)
- [Pydantic](https://docs.pydantic.dev/)
- [Tailwind CSS](https://tailwindcss.com/)

### 社区支持
- 项目Issues: [GitHub Issues](link-to-issues)
- 讨论区: [GitHub Discussions](link-to-discussions)
- 文档Wiki: [Project Wiki](link-to-wiki)

---

**🎉 现在您已经准备好开始使用Android项目资源包替换构建工具了！**

如有问题，请查看故障排除部分或联系开发团队。