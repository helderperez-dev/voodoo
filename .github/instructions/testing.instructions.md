# Testing & Contract Instructions

> **Read this before:** writing or modifying any test, adding contract tests, or touching `tests/conftest.py`.

---

## Test Infrastructure

### Runners & config

- **`pytest`** with `asyncio_mode = "auto"` — async tests don't need `@pytest.mark.asyncio`.
- **`pytest-asyncio`** — async test support.
- **Config** in `pyproject.toml`: `testpaths = ["tests"]`, `asyncio_mode = "auto"`.
- **Root `conftest.py`** — Adds `src/` to `sys.path` for bare `pytest` runs.

### Running tests

```bash
# Full suite
just test
# or
uv run pytest

# Verbose with short tracebacks (matches CI)
uv run pytest --tb=short

# Specific test file
uv run pytest tests/unit/runtime/test_runtime.py

# Public API contract
uv run pytest tests/integration/test_contract_api.py

# Architecture invariants
uv run pytest tests/architecture/test_repository_layout.py

# With markers
uv run pytest -m "not slow"

# With coverage
uv run pytest --cov=voodoo --cov-report=term-missing
```

### Service containers

Some contract tests require external services. Start them locally:

```bash
# MinIO (S3-compatible object store)
just minio-up

# Redis (queue + cache)
just redis-up

# Tear down
just minio-down
just redis-down
```

For PostgreSQL, use Docker directly:
```bash
docker run --name voodoo-pg -p 5432:5432 \
    -e POSTGRES_DB=voodoo_test \
    -e POSTGRES_USER=voodoo \
    -e POSTGRES_PASSWORD=voodoo \
    -d postgres:16
```

---

## Autouse Fixtures (`tests/conftest.py`)

These run before every test automatically:

| Fixture | Purpose |
|---|---|
| `_clean_page_registry` | Clears the `@page` registry between tests |
| `_reset_queue_state` | Resets `voodoo.runtime.scheduling` queue provider and running worker tasks |
| `_close_db_after_test` | Closes optional SQLite resources and resets Runtime Store/model state |
| `model_store` | Binds a fresh `application.vstore` for Store-native Model tests |
| `app` / `client` | Creates an isolated application/TestClient lifecycle |
| `test_db` | Explicit SQLite fixture for adapter-compatibility tests only |

### Important: `_reset_queue_state` does NOT reset the handler registry

Handlers register at import time. The fixture resets the provider and running task set under `voodoo.runtime.scheduling`, but not the handler registry. If a test registers a new handler, clean it explicitly or use a fresh registry where the test contract supports one.

---

## Test Patterns

### Structure

```python
from __future__ import annotations

import pytest


class TestMyFeature:
    """Tests for MyFeature."""

    async def test_basic_case(self):
        # Arrange
        obj = MyFeature()

        # Act
        result = await obj.do_thing()

        # Assert
        assert result == expected

    async def test_error_case(self):
        with pytest.raises(MyError):
            await obj.do_bad_thing()
```

### Fresh instances per test

Never share mutable state across tests. Use fixtures for isolation:

```python
@pytest.fixture
def engine():
    """Fresh ExecutionEngine per test — never use the singleton."""
    return ExecutionEngine()


async def test_execute(engine):
    result = await engine.execute(...)
```

### Async tests

With `asyncio_mode = "auto"`, async test functions work without decorators:

```python
async def test_async_thing():
    result = await some_async_function()
    assert result is not None
```

---

## Contract Tests (`tests/contracts/`)

The contract test suite is the **portability guarantee**. Mixin classes define the behavior every adapter must satisfy. Provider-specific test files subclass the mixin and run the same tests against a real server.

### Mixin pattern

```python
# tests/contracts/test_database.py
from __future__ import annotations

import pytest

class DatabaseContractTests:
    """Contract tests for VoodooDatabase implementations.

    Every database adapter must pass these tests unchanged.
    """

    @pytest.fixture
    def db(self):
        """Subclasses must override this fixture."""
        raise NotImplementedError("Subclass must provide db fixture")

    async def test_write_read_roundtrip(self, db):
        await db.execute("CREATE TABLE t (id INTEGER, name TEXT)")
        await db.execute("INSERT INTO t (id, name) VALUES (?, ?)", [1, "hello"])
        row = await db.fetchone("SELECT * FROM t WHERE id = ?", [1])
        assert row is not None
        assert row["name"] == "hello"

    async def test_migration_ledger(self, db):
        # ... migration tests

    async def test_transaction_commit_rollback(self, db):
        # ... transaction tests
```

### Provider-specific test file

```python
# tests/contracts/test_database_postgres.py
from __future__ import annotations

import os
import pytest

psycopg = pytest.importorskip("psycopg")

from .test_database import DatabaseContractTests


@pytest.mark.skipif(
    not os.environ.get("VOODOO_TEST_DATABASE_URL"),
    reason="VOODOO_TEST_DATABASE_URL not set",
)
class TestPostgresDatabase(DatabaseContractTests):
    @pytest.fixture
    def db(self):
        from voodoo.storage.database.postgres import PostgresDatabase

        cfg = {"url": os.environ.get("VOODOO_TEST_DATABASE_URL")}
        db = PostgresDatabase(cfg)
        # setup...
        yield db
        # teardown...
```

### Critical rules for contract tests

1. **Never modify the mixin** — The shared mixin classes are immutable. New adapters add tests on top, never change the shared suite.
2. **Gate with `importorskip`** — `pytest.importorskip("psycopg")` skips if the SDK isn't installed.
3. **Gate with env vars** — Use `os.environ.get(...)` at module level (NOT `os.environ[...]`), because module-level code runs before skip markers.
4. **Subclass the mixin** — `class TestMyProvider(XxxContractTests):`
5. **Override the fixture** — The subclass must provide the `db`/`queue`/`cache` fixture.

### Available contract suites

| Mixin | File | Tests |
|---|---|---|
| `DatabaseContractTests` | `test_database.py` | write/read, migrations, transactions, reconnect |
| `QueueContractTests` | `test_queue.py` | enqueue, claim, complete, retry, release, idempotency |
| `CacheContractTests` | `test_cache.py` | get/set, delete, exists, expire, TTL |
| `EventBusContractTests` | `test_eventbus.py` | publish, subscribe, replay, ordering |
| `ObjectStoreContractTests` | `test_objectstore.py` | upload, download, delete, presign, metadata |

### Provider-specific test files

| File | Provider | Env var gate |
|---|---|---|
| `test_database_postgres.py` | PostgreSQL | `VOODOO_TEST_DATABASE_URL` |
| `test_queue_postgres.py` | PostgreSQL queue | `VOODOO_TEST_DATABASE_URL` |
| `test_queue_redis.py` | Redis queue | `VOODOO_TEST_REDIS_URL` |
| `test_cache_redis.py` | Redis cache | `VOODOO_TEST_REDIS_URL` |
| `test_eventbus_postgres.py` | PostgreSQL events | `VOODOO_TEST_DATABASE_URL` |
| `test_execution_postgres.py` | PostgreSQL execution store | `VOODOO_TEST_DATABASE_URL` |
| `test_objectstore_s3.py` | S3/MinIO objects | `VOODOO_TEST_S3_ENDPOINT` |
| `test_sql_to_postgres.py` | SQL translation | `VOODOO_TEST_DATABASE_URL` |

---

## Mock Provider

`MockProvider` is deterministic and requires no network. Use it for all agent/AI tests:

```python
from voodoo.ai.providers.mock import MockProvider

provider = MockProvider(
    responses=["Hello!", "How can I help?"],
    model="mock:default",
)
```

`ToolThenTextProvider` simulates tool-call sequences:

```python
from voodoo.ai.providers.mock import ToolThenTextProvider

provider = ToolThenTextProvider(
    tool_call={"name": "search", "args": {"q": "python"}},
    final_text="Found Python!",
)
```

---

## Test File Organization

The 3.x suite mirrors semantic ownership instead of placing feature tests at
`tests/` root:

```text
tests/
├── conftest.py
├── architecture/   # repository/dependency invariants
├── contracts/      # portable adapter/protocol contracts
├── e2e/            # user/runtime acceptance journeys
├── integration/    # cross-domain behavior and durable Runtime flows
└── unit/
    ├── ai/
    ├── auth/
    ├── cli/
    ├── core/
    ├── data/
    ├── edge/
    ├── integrations/
    ├── primitives/
    ├── protocol/
    ├── runtime/
    ├── storage/
    ├── ui/
    └── world/
```

Do not add new `test_*.py` files directly under `tests/`; the architecture
suite enforces this rule.

---

## Public API Contract (`tests/integration/test_contract_api.py`)

This test verifies that all public exports in `voodoo.__all__` are importable and have the expected types. If you change the public API (add/remove/rename exports), update this test.

```python
def test_public_api_exports():
    import voodoo

    for name in voodoo.__all__:
        assert hasattr(voodoo, name), f"{name} in __all__ but not importable"
```

---

## When Writing Tests

1. **Use `from __future__ import annotations`** at the top of every test file.
2. **Group with test classes** — `class TestMyFeature:`.
3. **Fresh instances** — Never share mutable state. Use fixtures.
4. **Mock provider** — Use `MockProvider` for all AI tests. Never make real API calls.
5. **Autouse fixtures** — Don't disable them. They ensure isolation.
6. **Test names** — `test_<scenario>_<expected>` (e.g., `test_execute_with_valid_intent_returns_result`).
7. **Arrange-Act-Assert** — Structure tests clearly.
8. **Failure-path tests** — Every durability claim needs a failure-path test.
9. **Contract tests** — New adapters must pass the mixin suite unchanged.
10. **Env vars** — Use `os.environ.get(...)` at module level, never `os.environ[...]`.

---

## Quality Gate

```bash
just format && just lint && just test
```

This is the **mandatory** quality gate before any commit. All three must pass:

1. **`just format`** — `ruff format . && ruff check --fix .`
2. **`just lint`** — `ruff check .` (mypy is NOT part of lint — run separately with `uv run mypy src/voodoo`)
3. **`just test`** — `uv run pytest`

CI runs the same gate on Python 3.12 and 3.13 with service containers (PostgreSQL, MinIO, Redis).
