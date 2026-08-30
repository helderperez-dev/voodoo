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

# Start a local PostgreSQL container for database/queue/event/execution contract tests
postgres-up:
    docker rm -f voodoo-pg 2>/dev/null || true
    docker run --name voodoo-pg -p 5432:5432 \
        -e POSTGRES_DB=voodoo_test \
        -e POSTGRES_USER=voodoo \
        -e POSTGRES_PASSWORD=voodoo \
        -d postgres:16
    @echo "Waiting for PostgreSQL to accept connections..."
    @for i in $(seq 1 30); do docker exec voodoo-pg pg_isready -U voodoo >/dev/null 2>&1 && break; sleep 1; done
    @echo "PostgreSQL ready at postgresql://voodoo:voodoo@localhost:5432/voodoo_test"

# Start a local Mosquitto MQTT broker for edge integration tests
mqtt-up:
    docker rm -f voodoo-mqtt 2>/dev/null || true
    docker run --name voodoo-mqtt -p 1883:1883 -d eclipse-mosquitto:2 \
        mosquitto -c /mosquitto-no-auth.conf
    @echo "Mosquitto MQTT ready at mqtt://localhost:1883 (no auth, local dev only)"

# Stop and remove the local Mosquitto MQTT broker
mqtt-down:
    docker rm -f voodoo-mqtt 2>/dev/null || true
    @echo "Mosquitto MQTT container removed"

# Stop and remove the local PostgreSQL container
postgres-down:
    docker rm -f voodoo-pg 2>/dev/null || true
    @echo "PostgreSQL container removed"

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

# Start all local test infrastructure (PostgreSQL, MinIO, Redis) and run the full suite
# against it. This runs every contract suite (database, queue, event, execution, object
# store, cache) instead of skipping the provider-gated ones.
test-all: postgres-up minio-up redis-up
    @echo "Waiting for MinIO and Redis to be ready..."
    @for i in $(seq 1 30); do curl -sf http://localhost:9000/minio/health/live >/dev/null 2>&1 && break; sleep 1; done
    @for i in $(seq 1 30); do docker exec voodoo-redis redis-cli ping >/dev/null 2>&1 && break; sleep 1; done
    @echo "Running the full test suite against all local infrastructure..."
    VOODOO_TEST_DATABASE_URL=postgresql://voodoo:voodoo@localhost:5432/voodoo_test \
    VOODOO_TEST_S3_ENDPOINT=http://localhost:9000 \
    VOODOO_TEST_S3_BUCKET=voodoo-test \
    VOODOO_TEST_S3_KEY=minioadmin \
    VOODOO_TEST_S3_SECRET=minioadmin \
    VOODOO_TEST_REDIS_URL=redis://localhost:6379/0 \
    uv run pytest
