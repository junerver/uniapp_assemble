#!/usr/bin/env pwsh
# 设置开发环境脚本

Write-Host "🚀 Setting up development environment with UV..." -ForegroundColor Green

# 检查UV安装
if (!(Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "📦 Installing UV..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri "https://astral.sh/uv/install.ps1" -OutFile "install.ps1"
    .\install.ps1
    Remove-Item "install.ps1"
}

# 创建虚拟环境
Write-Host "🔧 Creating virtual environment..." -ForegroundColor Yellow
if (!(Test-Path ".venv")) {
    uv venv
}

# 同步依赖
Write-Host "📚 Installing dependencies..." -ForegroundColor Yellow
uv sync --dev

# 安装pre-commit钩子（如果需要）
if (Test-Path ".pre-commit-config.yaml") {
    Write-Host "🔍 Setting up pre-commit hooks..." -ForegroundColor Yellow
    uv run pre-commit install
}

Write-Host "✅ Setup complete!" -ForegroundColor Green
Write-Host "🎯 Activate environment: .venv\Scripts\Activate.ps1" -ForegroundColor Cyan
Write-Host "🧪 Run tests: uv run pytest" -ForegroundColor Cyan
Write-Host "🔍 Run linting: uv run ruff check src/" -ForegroundColor Cyan