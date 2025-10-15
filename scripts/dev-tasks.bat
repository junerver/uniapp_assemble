@echo off
rem 开发任务脚本

if "%1"=="help" (
    echo Available commands:
    echo   install    - Install dependencies
    echo   test       - Run tests
    echo   test-cov   - Run tests with coverage
    echo   lint       - Run linting
    echo   format     - Format code
    echo   check      - Run all checks
    echo   clean      - Clean up
    echo   lock       - Update lock file
    echo   tree       - Show dependency tree
    goto :eof
)

if "%1"=="install" (
    uv sync --dev
    goto :eof
)

if "%1"=="test" (
    uv run pytest
    goto :eof
)

if "%1"=="test-cov" (
    uv run pytest --cov=src --cov-report=html
    goto :eof
)

if "%1"=="lint" (
    uv run ruff check src/
    uv run mypy src/
    goto :eof
)

if "%1"=="format" (
    uv run black src/
    uv run ruff format src/
    goto :eof
)

if "%1"=="check" (
    call :lint
    call :test
    goto :eof
)

if "%1"=="clean" (
    if exist .venv rmdir /s /q .venv
    if exist .pytest_cache rmdir /s /q .pytest_cache
    if exist .coverage del .coverage
    if exist htmlcov rmdir /s /q htmlcov
    if exist dist rmdir /s /q dist
    if exist build rmdir /s /q build
    goto :eof
)

if "%1"=="lock" (
    uv lock
    goto :eof
)

if "%1"=="tree" (
    uv tree
    goto :eof
)

echo Unknown command: %1
echo Use 'scripts\dev-tasks.bat help' for available commands