# Android项目资源包替换构建工具

一个基于 FastAPI 的工具，用于**拖拽压缩包处理以快速构建 Android 项目**。项目使用规范驱动开发工作流程，具有章程治理。

## 🚀 快速开始

### 系统要求

- **Python**: 3.13+
- **操作系统**: Windows 10/11, macOS 10.15+, Linux
- **包管理器**: UV (推荐) 或 pip

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
cd govcar_upgrade_uniapp_assemble

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

- **后端框架**: FastAPI
- **异步ORM**: SQLAlchemy 2.0
- **数据库**: SQLite (开发), PostgreSQL (生产)
- **代码质量**: Ruff, Black, MyPy
- **测试**: Pytest, Pytest-asyncio
- **包管理**: UV

## 📊 性能指标

使用UV包管理器带来的性能提升：

| 操作 | pip | UV | 性能提升 |
|------|-----|----|---------|
| 依赖安装 | 5-10分钟 | 30-60秒 | 10-20x |
| 虚拟环境创建 | 1-2分钟 | 10-30秒 | 4-8x |
| 依赖解析 | 30-60秒 | 5-10秒 | 6-12x |

---

**注意**: 本项目已迁移到UV包管理工具。旧的requirements.txt文件已备份为requirements.txt.backup，建议使用UV进行依赖管理以获得最佳性能。
