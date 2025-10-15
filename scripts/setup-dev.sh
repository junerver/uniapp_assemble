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
if [ ! -d ".venv" ]; then
    uv venv
fi

# 同步依赖
echo "📚 Installing dependencies..."
uv sync --dev

# 安装pre-commit钩子（如果需要）
if [ -f ".pre-commit-config.yaml" ]; then
    echo "🔍 Setting up pre-commit hooks..."
    uv run pre-commit install
fi

echo "✅ Setup complete!"
echo "🎯 Activate environment: source .venv/bin/activate"
echo "🧪 Run tests: uv run pytest"
echo "🔍 Run linting: uv run ruff check src/"