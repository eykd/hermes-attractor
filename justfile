# Just configuration
set shell := ["bash", "-uc"]

# Default recipe (list all recipes)
default:
    @just --list

# Run linters + type checker
lint:
    uv run ruff check src tests
    uv run ruff format --check src tests
    uv run pyright

# Format code
format:
    uv run ruff format src tests
    uv run ruff check --fix src tests

# Run tests with coverage (100% required)
test:
    uv run pytest -v --cov

# Run quick tests (no coverage)
test-quick:
    uv run pytest -v --no-cov

# Run tests with HTML coverage report
test-cov:
    uv run pytest -v --cov --cov-report=html
    @echo "Coverage report generated at htmlcov/index.html"

# Run CI suite (lint + type check + test)
ci:
    just lint
    just test

# Install dependencies (all groups)
install:
    uv sync --all-groups

# Install pre-commit hooks
hooks:
    uv run pre-commit install

# Run pre-commit on all files
pre-commit:
    uv run pre-commit run --all-files

# Clean build artifacts
clean:
    rm -rf build/
    rm -rf dist/
    rm -rf *.egg-info
    rm -rf .pytest_cache
    rm -rf .ruff_cache
    rm -rf htmlcov
    rm -rf .coverage .coverage.*
    find . -type d -name __pycache__ -exec rm -rf {} +
    find . -type f -name '*.pyc' -delete

# Run the Hermes CLI with the plugin (requires `hermes` installed; see Open Items)
run *ARGS:
    uv run hermes {{ARGS}}

# Run Python shell with package loaded
shell:
    uv run python
