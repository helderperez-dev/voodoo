# Default recipe to list all available commands
default:
    @just --list

# Install dependencies (including dev)
install:
    pip install -e .[dev]

# Format the code using ruff
format:
    ruff format .
    ruff check --fix .

# Run linters (ruff and mypy)
lint:
    ruff check .
    mypy .

# Run tests using pytest
test:
    pytest

# Clean up build artifacts and cache directories
clean:
    rm -rf build/
    rm -rf dist/
    rm -rf *.egg-info/
    find . -type d -name __pycache__ -exec rm -rf {} +
    find . -type f -name "*.pyc" -delete
