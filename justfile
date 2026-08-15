# Default recipe to list all available commands
default:
    @just --list

# Install dependencies (including dev)
install:
    uv pip install -e ".[dev]"

# Format the code using ruff
format:
    uv run ruff format .
    uv run ruff check --fix .

# Run linters (ruff)
lint:
    uv run ruff check .

# Run test suite using pytest
test:
    uv run pytest

# Clean up build artifacts and cache directories
clean:
    rm -rf build/ dist/ *.egg-info/ .data/ storage/ .mypy_cache/ .ruff_cache/
    find . -type d -name __pycache__ -exec rm -rf {} +
    find . -type f -name "*.pyc" -delete

# Build wheel and sdist packages
build: clean
    uv build

# Release a new version (fully automated in GitHub Actions: test, bump, PyPI, Homebrew, GitHub Release)
release version:
    @gh workflow run release.yml --ref main -f version={{version}}
    @echo "Release {{version}} triggered — watch it: gh run watch --workflow=release.yml"
