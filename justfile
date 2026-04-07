# Development task runner
# Usage: just <target>

# Cross-platform shell configuration
set windows-shell := ["powershell", "-NoLogo", "-Command"]
set shell := ["sh", "-cu"]

# ---------------------------------------------------------------------------
# Fast dev loop (~30s)
# ---------------------------------------------------------------------------

# Run fast quality checks + unit tests (parallel)
check:
    uv run ruff check src tests
    uv run ruff format --check src tests
    uv run mypy src
    uv run pytest -m unit -n auto

# ---------------------------------------------------------------------------
# Full pre-merge gate (~3 min)
# ---------------------------------------------------------------------------

# Run all quality checks + all tests with coverage
gate:
    uv run ruff check src tests
    uv run ruff format --check src tests
    uv run mypy src
    uv run xenon --max-absolute B --max-modules A --max-average A src
    uv run pip-audit --ignore-vuln CVE-2025-69872  # diskcache via pyqmd, no fix available
    uv run pytest -m "unit or integration" --cov --cov-report=term-missing --cov-report=html --cov-fail-under=50

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

# Run all tests
test:
    uv run pytest -m unit -n auto
    uv run pytest -m integration

# Run unit tests only (parallel)
test-unit:
    uv run pytest -m unit -n auto

# Run integration tests only (serial — shared ports)
test-integration:
    uv run pytest -m integration

# Run e2e tests only
test-e2e:
    uv run pytest -m e2e

# Run slow tests (requires Claude Code, API tokens)
test-slow:
    uv run pytest -m slow

# Run tests with coverage report
test-cov:
    uv run pytest -m unit -n auto --cov --cov-report=term-missing --cov-report=html
    uv run pytest -m integration --cov --cov-append --cov-report=term-missing --cov-report=html

# ---------------------------------------------------------------------------
# Code quality (individual tools)
# ---------------------------------------------------------------------------

# Format code (auto-fix)
format:
    uv run ruff format src tests
    uv run ruff check --fix src tests

# Check linting (no auto-fix)
lint:
    uv run ruff check src tests

# Run type checker
types:
    uv run mypy src

# Check code complexity
complexity:
    uv run xenon --max-absolute B --max-modules A --max-average A src

# Scan dependencies for vulnerabilities
audit:
    uv run pip-audit --ignore-vuln CVE-2025-69872  # diskcache via pyqmd, no fix available

# ---------------------------------------------------------------------------
# Documentation
# ---------------------------------------------------------------------------

# Build docs (strict mode, warnings are errors)
docs:
    uv run mkdocs build --strict

# Serve docs locally with live reload
docs-serve:
    uv run mkdocs serve

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

# Install all dependencies
install:
    uv sync --all-groups

# Install pre-commit hooks
hooks:
    uv run pre-commit install

# Clean build artifacts and caches
[unix]
clean:
    rm -rf build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage site

[windows]
clean:
    if (Test-Path build) { Remove-Item -Recurse -Force build }
    if (Test-Path dist) { Remove-Item -Recurse -Force dist }
    if (Test-Path .pytest_cache) { Remove-Item -Recurse -Force .pytest_cache }
    if (Test-Path .mypy_cache) { Remove-Item -Recurse -Force .mypy_cache }
    if (Test-Path .ruff_cache) { Remove-Item -Recurse -Force .ruff_cache }
    if (Test-Path htmlcov) { Remove-Item -Recurse -Force htmlcov }
    if (Test-Path .coverage) { Remove-Item -Force .coverage }
    if (Test-Path site) { Remove-Item -Recurse -Force site }
    Get-ChildItem -Filter *.egg-info -Recurse | Remove-Item -Recurse -Force
