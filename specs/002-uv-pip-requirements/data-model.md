# Data Model Design - UV包管理工具迁移

**Created**: 2025-10-15
**Phase**: Phase 1 - Design & Contracts
**Research**: Based on Phase 0 research findings

## Overview

本文档定义了UV包管理工具迁移的数据模型设计。由于这是一个基础设施迁移项目，主要涉及配置文件和工具设置，不需要传统的数据库模型。重点在于项目配置文件结构和工具集成配置。

## Configuration Models

### 1. Project Configuration (pyproject.toml)

**Purpose**: 项目的主要配置文件，替代requirements.txt并统一管理所有项目设置

**Structure**:
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
    # ... 其他生产依赖
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "black>=23.7.0",
    "ruff>=0.0.287",
    "mypy>=1.5.0",
]

[project.scripts]
android-builder = "src.main:main"

[tool.uv]
dev-dependencies = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "black>=23.7.0",
    "ruff>=0.0.287",
    "mypy>=1.5.0",
]

[tool.ruff]
line-length = 88
target-version = "py313"

[tool.black]
line-length = 88
target-version = ["py313"]

[tool.mypy]
python_version = "3.13"
strict = true

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

**Key Features**:
- 统一的依赖管理
- 开发依赖分离
- 工具配置集中管理
- 脚本入口点定义

### 2. UV Configuration (.uvrc)

**Purpose**: UV工具的全局和项目级配置

**Structure**:
```toml
# Global UV configuration
[pip]
# Python包索引配置
index-url = "https://pypi.org/simple"
extra-index-url = []
trusted-host = []

# 缓存配置
[cache]
dir = ".uv-cache"
max-size = "2GB"

# 虚拟环境配置
[venv]
# 自动创建虚拟环境
auto-create = true
# 虚拟环境目录
prefer-uv-python = true

# 开发模式配置
[dev]
# 自动安装开发依赖
auto-install-dev = true
```

### 3. CI/CD Configuration Models

#### GitHub Actions Workflow
```yaml
name: CI
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up UV
        uses: astral-sh/setup-uv@v3
        with:
          version: "latest"
      - name: Install dependencies
        run: uv sync --dev
      - name: Run tests
        run: uv run pytest
      - name: Run type checking
        run: uv run mypy src/
      - name: Run linting
        run: uv run ruff check src/
```

#### Docker Configuration
```dockerfile
FROM python:3.13-slim

# 安装UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 设置工作目录
WORKDIR /app

# 复制配置文件
COPY pyproject.toml uv.lock ./

# 安装依赖
RUN uv sync --frozen

# 复制应用代码
COPY src/ ./src/

# 运行应用
CMD ["uv", "run", "python", "-m", "src.main"]
```

### 4. Development Environment Scripts

#### Environment Setup Script
```bash
#!/bin/bash
# setup-env.sh

echo "Setting up development environment with UV..."

# 检查UV是否安装
if ! command -v uv &> /dev/null; then
    echo "Installing UV..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# 创建虚拟环境
echo "Creating virtual environment..."
uv venv

# 激活虚拟环境
echo "Activating virtual environment..."
source .venv/bin/activate

# 安装依赖
echo "Installing dependencies..."
uv sync --dev

# 安装pre-commit钩子
echo "Setting up pre-commit hooks..."
uv run pre-commit install

echo "Development environment setup complete!"
echo "To activate the environment, run: source .venv/bin/activate"
```

## Migration Data Flow

### Phase 1: 依赖迁移流程
```
requirements.txt → pyproject.toml [dependencies]
                    → pyproject.toml [project.optional-dependencies.dev]
                    → uv.lock (generated)
```

### Phase 2: 环境设置流程
```
pyproject.toml + uv.lock → uv sync → .venv/
                                      ├── bin/python
                                      ├── lib/python3.13/site-packages/
                                      └── pyvenv.cfg
```

### Phase 3: 工具集成流程
```
pyproject.toml [tool.*] → uv run <tool> → tool execution
                                      ├── ruff check src/
                                      ├── black src/
                                      ├── mypy src/
                                      └── pytest tests/
```

## Configuration Validation

### Dependency Validation Rules
1. **Version Compatibility**: 所有依赖必须与Python 3.13+兼容
2. **Security Scanning**: 依赖必须通过安全扫描
3. **License Compliance**: 所有依赖必须使用兼容的许可证
4. **Size Optimization**: 依赖包大小应该在合理范围内

### Tool Configuration Validation
1. **Consistency**: 所有工具配置必须保持一致性
2. **Performance**: 配置应该优化工具性能
3. **Compatibility**: 工具版本必须相互兼容
4. **Standards Compliance**: 配置必须符合团队标准

## Integration Points

### 1. IDE Integration
- **VS Code**: 使用UV解释器配置
- **PyCharm**: 配置UV管理的虚拟环境
- **Vim/Neovim**: 使用UV运行LSP服务器

### 2. Build System Integration
- **Makefile**: 使用UV命令替换pip命令
- **CMake**: 集成UV进行Python环境管理
- **Bazel**: 配置UV作为包管理工具

### 3. Container Integration
- **Docker**: 多阶段构建优化镜像大小
- **Kubernetes**: 使用UV进行容器内依赖管理
- **Podman**: 与Docker相同的集成策略

## Monitoring and Metrics

### Performance Metrics
- **安装时间**: 依赖安装耗时
- **缓存命中率**: UV缓存使用效率
- **并行度**: 并行安装的有效性
- **错误率**: 安装失败的比例

### Quality Metrics
- **依赖一致性**: 团队环境的一致性
- **安全扫描**: 依赖漏洞检测结果
- **兼容性测试**: 跨平台兼容性验证
- **开发者满意度**: 工具使用体验反馈

## Migration Checklist

### Pre-Migration
- [ ] 备份现有requirements.txt文件
- [ ] 分析现有依赖关系
- [ ] 验证UV版本兼容性
- [ ] 准备回滚计划

### Migration Execution
- [ ] 创建pyproject.toml配置文件
- [ ] 导入现有依赖到pyproject.toml
- [ ] 生成uv.lock锁定文件
- [ ] 验证依赖安装正确性

### Post-Migration Validation
- [ ] 运行完整测试套件
- [ ] 验证所有开发工具正常工作
- [ ] 测试CI/CD流水线
- [ ] 收集性能基准数据

### Team Adoption
- [ ] 更新项目文档
- [ ] 提供迁移指南
- [ ] 进行团队培训
- [ ] 收集使用反馈

## Rollback Strategy

### Immediate Rollback
- 保留原始requirements.txt文件
- 恢复pip安装脚本
- 回滚CI/CD配置

### Full Rollback
- 移除pyproject.toml和uv.lock
- 恢复所有开发环境配置
- 重新配置所有工具链

## Success Criteria

- ✅ 所有依赖通过UV成功安装
- ✅ 开发环境设置时间<30秒
- ✅ CI/CD构建时间减少50%
- ✅ 团队成员满意度>4.5/5
- ✅ 零生产环境故障