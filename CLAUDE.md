# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Communication Language

**请使用中文进行对话** - Please communicate in Chinese when working with this repository. All explanations, comments, and interactions should be in Chinese to maintain consistency with the project's primary language context.

## 项目概述

这是一个基于 Python 的工具，用于**拖拽压缩包处理以快速构建 Android 项目**。项目使用规范驱动开发工作流程，具有章程治理。

## 开发工作流程

本项目遵循结构化的**规范驱动开发**流程，使用自定义斜杠命令。所有开发必须遵循项目章程（`.specify/memory/constitution.md`）中定义的工作流程。

### 必需的工作流程步骤

1. **功能规范**：使用 `/speckit.specify` 创建包含用户故事和需求的功能规范
2. **实施计划**：使用 `/speckit.plan` 创建详细的实施计划
3. **任务生成**：使用 `/speckit.tasks` 创建可操作的任务列表
4. **实施**：按优先级顺序执行任务（P1 → P2 → P3）

### 分支命名约定

所有功能分支必须遵循模式：`[###-feature-name]`，其中 `###` 是一个 3 位数字（例如，`001-drag-drop-interface`、`002-zip-processing`）。

## 常用命令

### 开发环境设置
```bash
# ⚠️ 重要：本项目强制使用UV包管理工具（章程第VII条原则）
# 禁止使用裸pip和python命令

# 安装UV（如果尚未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 创建虚拟环境并安装依赖
uv venv
uv sync --dev

# 运行主应用程序
uv run python -m src.main

# 或使用uvicorn
uv run uvicorn src.main:app --reload
```

### 规范驱动开发命令
```bash
# 检查开发先决条件
./.specify/scripts/powershell/check-prerequisites.ps1

# 创建具有正确分支命名的新功能
./.specify/scripts/powershell/create-new-feature.ps1 "功能描述"

# 检查当前功能的可用文档
./.specify/scripts/powershell/check-prerequisites.ps1 -Json
```

### 功能开发
按顺序使用这些斜杠命令：
- `/speckit.specify` - 创建功能规范
- `/speckit.plan` - 创建实施计划
- `/speckit.tasks` - 生成任务列表
- `/speckit.implement` - 执行实施

## 项目结构

```
├── .specify/                    # 规范驱动开发框架
│   ├── memory/constitution.md   # 项目章程和治理
│   ├── templates/               # 规范、计划、任务的文档模板
│   └── scripts/powershell/      # 开发自动化脚本
├── specs/                       # 功能规范（自动创建）
│   └── [###-feature-name]/
│       ├── spec.md             # 功能规范
│       ├── plan.md             # 实施计划
│       ├── tasks.md            # 任务分解
│       └── contracts/          # API 合约和模式
├── main.py                     # 应用程序入口点
├── pyproject.toml             # Python 项目配置
└── CLAUDE.md                  # 本文件
```

## 架构原则

根据项目章程，本项目必须遵循：

1. **模块化架构**：每个组件必须是独立的、可单独测试的，具有清晰的接口
2. **跨平台兼容性**：代码必须在 Web、iOS 和 Android 平台上都能工作
3. **测试驱动开发**：TDD 是强制性的 - 测试必须在实现之前编写并失败
4. **组件可重用性**：UI 组件和业务逻辑必须设计为可重用的
5. **性能优化**：应用加载 < 3 秒，转换 < 500 毫秒，内存优化
6. **用户体验一致性**：所有界面必须保持一致的交互模式和视觉设计
7. **UV包管理（强制）**：所有Python操作必须使用UV，禁止裸python/pip命令
8. **代码卫生和清理（强制）**：临时验证脚本/调试代码必须在验证完成后立即删除

## 关键文件及其用途

- **`.specify/memory/constitution.md`**：项目治理原则，覆盖所有其他实践
- **`pyproject.toml`**：Python 项目元数据和依赖（目前最小化）
- **`main.py`**：简单的入口点，将扩展拖放功能
- **PowerShell 脚本**：提供跨平台开发自动化和先决条件检查

## 测试要求

- 单元测试必须覆盖所有业务逻辑
- 集成测试必须覆盖组件交互
- 端到端测试必须覆盖关键用户旅程
- 测试覆盖率必须保持在 80% 以上
- 测试必须在实现之前编写（TDD 方法）

## Git 集成

项目支持 git 和非 git 仓库。当 git 可用时：
- 功能分支会自动创建，使用正确的命名
- 分支验证强制执行 `###-feature-name` 约定
- 所有开发都在功能分支上进行，而不是主分支

## 环境变量

- `SPECIFY_FEATURE`：由功能创建脚本自动设置，以跟踪当前功能上下文

## 临时文件管理（重要）

⚠️ **强制要求**：所有临时验证脚本、调试代码必须在完成验证后立即删除（章程第VIII条原则）

### 禁止的文件模式
- ❌ `debug_*.py`, `debug_*.js`, `debug_*.html` - 调试文件
- ❌ `test_*.html` - 临时HTML测试文件（仅允许在tests/目录）
- ❌ `fix_*.py`, `temp_*.py` - 临时修复/测试脚本
- ❌ `foo.py`, `bar.py`, `asdf.py` - 随意命名的临时文件
- ❌ 大块注释代码 - 使用版本控制历史而非注释

### 允许的临时位置
- ✅ `/temp/` - gitignored，应用启动时自动清理
- ✅ `/sandbox/` - gitignored，手动实验区域
- ✅ `tests/test_*.py` - 正式测试文件（仅限tests/目录）

### 最佳实践
1. 如果需要临时验证代码，使用 `/sandbox/` 目录
2. 验证完成后立即删除临时文件
3. 正式测试应放在 `tests/` 目录并遵循命名约定
4. 提交前运行 `git status` 确保没有遗留临时文件
