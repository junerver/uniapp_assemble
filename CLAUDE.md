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
# 安装依赖（需要 Python 3.13+）
pip install -e .

# 运行主应用程序
python main.py
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
