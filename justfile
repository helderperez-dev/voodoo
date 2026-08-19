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

# Start a local MinIO container for S3 object store contract tests
minio-up:
    docker rm -f voodoo-minio 2>/dev/null || true
    docker run --name voodoo-minio -p 9000:9000 -p 9001:9001 \
        -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin \
        -d minio/minio server /data --console-address ":9001"
    @echo "MinIO ready at http://localhost:9000 (console: http://localhost:9001)"

# Stop and remove the local MinIO container
minio-down:
    docker rm -f voodoo-minio 2>/dev/null || true
    @echo "MinIO container removed"

# Start a local Redis container for queue + cache contract tests
redis-up:
    docker rm -f voodoo-redis 2>/dev/null || true
    docker run --name voodoo-redis -p 6379:6379 -d redis:7
    @echo "Redis ready at redis://localhost:6379/0"

# Stop and remove the local Redis container
redis-down:
    docker rm -f voodoo-redis 2>/dev/null || true
    @echo "Redis container removed"

# Clean up build artifacts and cache directories
clean:
    rm -rf build/ dist/ *.egg-info/ .voodoo/ storage/ .mypy_cache/ .ruff_cache/
    find . -type d -name __pycache__ -exec rm -rf {} +
    find . -type f -name "*.pyc" -delete

# Build wheel and sdist packages
build: clean
    uv build

# Release a new version (fully automated in GitHub Actions: test, bump, PyPI, Homebrew, GitHub Release)
release version:
    @gh workflow run release.yml --ref main -f version={{version}}
    @echo "Release {{version}} triggered — watch it: gh run watch --workflow=release.yml"
