# 快速启动指南 - UV包管理工具迁移

**项目**: Android项目资源包替换构建工具 UV迁移
**版本**: 1.0.0
**创建**: 2025-10-15
**目标**: 从pip + requirements.txt迁移到uv + pyproject.toml

## 🚀 快速开始

### 系统要求

- **Python**: 3.13+ (现有项目版本)
- **操作系统**: Windows 10/11, macOS 10.15+, Linux
- **内存**: 最少 4GB RAM
- **网络**: 稳定的互联网连接
- **权限**: 虚拟环境创建权限

### 5分钟快速迁移

#### 步骤 1: 安装UV

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

#### 步骤 2: 验证安装

```bash
uv --version
uv python install 3.13
```

#### 步骤 3: 迁移项目

```bash
# 进入项目目录
cd /path/to/your/project

# 创建UV虚拟环境
uv venv

# 导入现有requirements.txt到pyproject.toml
uv add --dev ruff black mypy pytest pytest-asyncio

# 同步依赖
uv sync --dev
```

#### 步骤 4: 验证迁移

```bash
# 激活虚拟环境
source .venv/bin/activate  # Linux/macOS
# 或 .venv\Scripts\activate  # Windows

# 运行测试
uv run pytest

# 运行代码检查
uv run ruff check
uv run mypy src/
```

## 📋 详细迁移步骤

### Phase 1: 准备工作

#### 1.1 备份现有配置
```bash
# 备份requirements.txt
cp requirements.txt requirements.txt.backup

# 备份现有虚拟环境（如果有）
python -m venv venv_backup
source venv_backup/bin/activate
pip freeze > requirements_backup.txt
```

#### 1.2 分析现有依赖
```bash
# 查看当前依赖
pip list

# 分析依赖关系
pipdeptree
```

### Phase 2: UV配置

#### 2.1 初始化项目
```bash
# 创建pyproject.toml
uv init --name android-builder

# 设置Python版本
uv python pin 3.13
```

#### 2.2 配置项目文件
编辑 `pyproject.toml`:
```toml
[project]
name = "govcar-upgrade-uniapp-assemble"
version = "0.1.0"
description = "Android项目资源包替换构建工具"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "sqlalchemy[asyncio]>=2.0.0",
    "aiosqlite>=0.19.0",
    "pydantic>=2.4.0",
    "aiofiles>=23.2.1",
    "GitPython>=3.1.40",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "httpx>=0.25.0",
    "black>=23.7.0",
    "ruff>=0.0.287",
    "mypy>=1.5.0",
]

[tool.uv]
dev-dependencies = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "black>=23.7.0",
    "ruff>=0.0.287",
    "mypy>=1.5.0",
]
```

### Phase 3: 依赖迁移

#### 3.1 导入现有依赖
```bash
# 从requirements.txt导入
uv add -r requirements.txt

# 添加开发依赖
uv add --dev pytest ruff black mypy

# 生成锁定文件
uv lock
```

#### 3.2 验证依赖
```bash
# 检查依赖兼容性
uv tree

# 验证锁定文件
uv lock --check

# 同步到虚拟环境
uv sync
```

### Phase 4: 工具链更新

#### 4.1 更新开发脚本
创建 `scripts/setup.sh`:
```bash
#!/bin/bash
set -e

echo "🚀 Setting up development environment with UV..."

# 检查UV安装
if ! command -v uv &> /dev/null; then
    echo "📦 Installing UV..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# 创建虚拟环境
echo "🔧 Creating virtual environment..."
uv venv

# 同步依赖
echo "📚 Installing dependencies..."
uv sync --dev

# 安装pre-commit钩子
echo "🔍 Setting up pre-commit hooks..."
uv run pre-commit install

echo "✅ Setup complete!"
echo "🎯 Activate environment: source .venv/bin/activate"
```

#### 4.2 更新Makefile
```makefile
.PHONY: help install dev test lint format clean

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	uv sync --dev

dev:  ## Set up development environment
	chmod +x scripts/setup.sh
	./scripts/setup.sh

test:  ## Run tests
	uv run pytest

test-cov:  ## Run tests with coverage
	uv run pytest --cov=src --cov-report=html

lint:  ## Run linting
	uv run ruff check src/
	uv run mypy src/

format:  ## Format code
	uv run black src/
	uv run ruff format src/

clean:  ## Clean up
	rm -rf .venv/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
```

## 🔧 开发环境配置

### IDE配置

#### VS Code
创建 `.vscode/settings.json`:
```json
{
    "python.defaultInterpreterPath": "./.venv/bin/python",
    "python.terminal.activateEnvironment": true,
    "python.linting.enabled": true,
    "python.linting.ruffEnabled": true,
    "python.formatting.provider": "black",
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["tests/"],
    "files.exclude": {
        "**/__pycache__": true,
        "**/*.pyc": true
    }
}
```

#### PyCharm
1. 打开项目设置
2. 选择 "Python Interpreter"
3. 点击 "Add Interpreter"
4. 选择 "Existing Environment"
5. 浏览到 `./.venv/bin/python`

### Git配置

#### .gitignore更新
```gitignore
# UV
.uv/
.uv-cache/

# Virtual environment
.venv/
venv/

# Python
__pycache__/
*.pyc
*.pyo
*.pyd

# Coverage
.coverage
htmlcov/
.pytest_cache/

# IDE
.vscode/
.idea/
*.swp
*.swo
```

#### Pre-commit配置
创建 `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.0.287
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/psf/black
    rev: 23.7.0
    hooks:
      - id: black

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.5.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
```

## 🚢 CI/CD集成

### GitHub Actions

创建 `.github/workflows/ci.yml`:
```yaml
name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.13]

    steps:
    - uses: actions/checkout@v4

    - name: Set up UV
      uses: astral-sh/setup-uv@v3
      with:
        version: "latest"

    - name: Set up Python ${{ matrix.python-version }}
      run: uv python install ${{ matrix.python-version }}

    - name: Install dependencies
      run: uv sync --dev

    - name: Run tests
      run: uv run pytest

    - name: Run linting
      run: uv run ruff check src/

    - name: Run type checking
      run: uv run mypy src/

    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

### Docker优化

创建 `Dockerfile`:
```dockerfile
# 多阶段构建
FROM python:3.13-slim as base

# 安装UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 设置工作目录
WORKDIR /app

# 复制配置文件
COPY pyproject.toml uv.lock ./

# 安装依赖
RUN uv sync --frozen

# 生产镜像
FROM base as production
COPY src/ ./src/

# 非root用户
RUN useradd --create-home --shell /bin/bash app
USER app

# 运行应用
CMD ["uv", "run", "python", "-m", "src.main"]
```

## 🔍 故障排除

### 常见问题

#### 1. UV安装失败
```bash
# 问题: UV安装脚本无法执行
# 解决方案: 使用pip安装
pip install uv
```

#### 2. 依赖安装错误
```bash
# 问题: 某个依赖无法安装
# 解决方案: 检查Python版本兼容性
uv add package_name --index-url https://pypi.org/simple
```

#### 3. 虚拟环境激活失败
```bash
# Linux/macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate

# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

#### 4. 锁定文件冲突
```bash
# 问题: uv.lock与依赖不匹配
# 解决方案: 重新生成锁定文件
rm uv.lock
uv lock
```

### 性能优化

#### 1. 缓存配置
```bash
# 设置缓存目录
export UV_CACHE_DIR=/path/to/cache

# 限制缓存大小
uv sync --cache-dir /path/to/cache
```

#### 2. 并行安装
```bash
# UV默认并行安装，无需额外配置
# 如需限制并行数
export UV_CONCURRENT_DOWNLOADS=4
```

### 网络问题

#### 1. 镜像源配置
```bash
# 使用国内镜像
uv add package_name --index-url https://pypi.tuna.tsinghua.edu.cn/simple/
```

#### 2. 离线安装
```bash
# 下载依赖包
uv pip compile pyproject.toml -o requirements.txt

# 离线安装
uv pip install -r requirements.txt --no-index --find-links /path/to/packages
```

## 📊 性能对比

| 操作 | pip | UV | 性能提升 |
|------|-----|----|---------|
| 依赖安装 | 5-10分钟 | 30-60秒 | 10-20x |
| 虚拟环境创建 | 1-2分钟 | 10-30秒 | 4-8x |
| 依赖解析 | 30-60秒 | 5-10秒 | 6-12x |
| 缓存利用 | 基础 | 智能缓存 | 2-5x |

## 🎯 成功指标

- ✅ 依赖安装时间 < 1分钟
- ✅ 环境设置时间 < 30秒
- ✅ CI/CD构建时间减少50%
- ✅ 团队环境一致性 > 99%
- ✅ 开发者满意度 > 4.5/5

## 📚 更多资源

- [UV官方文档](https://docs.astral.sh/uv/)
- [pyproject.toml规范](https://packaging.python.org/specifications/pyproject-toml/)
- [Python打包指南](https://packaging.python.org/)
- [项目GitHub](https://github.com/astral-sh/uv)

---

**🎉 现在您已经成功迁移到UV包管理工具！**

如有问题，请查看故障排除部分或联系开发团队。