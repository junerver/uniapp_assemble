#!/bin/bash
set -e

echo "🔍 UV迁移验证脚本"
echo "=================="

# 检查UV是否安装
if ! command -v uv &> /dev/null; then
    echo "❌ UV未安装"
    exit 1
else
    echo "✅ UV已安装: $(uv --version)"
fi

# 检查虚拟环境
if [ -d ".venv" ]; then
    echo "✅ 虚拟环境存在"
else
    echo "❌ 虚拟环境不存在"
    exit 1
fi

# 检查pyproject.toml
if [ -f "pyproject.toml" ]; then
    echo "✅ pyproject.toml存在"
else
    echo "❌ pyproject.toml不存在"
    exit 1
fi

# 检查uv.lock
if [ -f "uv.lock" ]; then
    echo "✅ uv.lock存在"
else
    echo "❌ uv.lock不存在"
    exit 1
fi

# 检查关键依赖
echo "📦 检查关键依赖..."
if uv run python -c "import fastapi, uvicorn, sqlalchemy, pydantic" 2>/dev/null; then
    echo "✅ 关键依赖正常"
else
    echo "❌ 关键依赖缺失"
    exit 1
fi

# 检查开发工具
echo "🔧 检查开发工具..."
tools=("pytest" "ruff" "black" "mypy")
for tool in "${tools[@]}"; do
    if uv run "$tool" --version >/dev/null 2>&1; then
        echo "✅ $tool 正常"
    else
        echo "❌ $tool 异常"
    fi
done

# 性能测试
echo "⚡ 性能测试..."
start_time=$(date +%s.%N)
uv sync --check >/dev/null 2>&1
end_time=$(date +%s.%N)
duration=$(echo "$end_time - $start_time" | bc)
echo "📊 同步时间: ${duration}秒"

echo ""
echo "🎉 UV迁移验证完成！"