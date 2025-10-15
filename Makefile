.PHONY: help install dev test lint format clean

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	uv sync --dev

dev:  ## Set up development environment
	chmod +x scripts/setup-dev.sh
	./scripts/setup-dev.sh

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

check: lint test  ## Run all checks

clean:  ## Clean up
	rm -rf .venv/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf dist/
	rm -rf build/

lock:  ## Update lock file
	uv lock

tree:  ## Show dependency tree
	uv tree

outdated:  ## Show outdated dependencies
	uv tree --outdated