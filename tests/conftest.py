import os

import pytest
import pytest_asyncio
from starlette.testclient import TestClient

import voodoo.data
import voodoo.queue
from voodoo.core import create_app

# Tests default to the in-memory queue provider for speed; durable-queue
# tests override this per-test.
os.environ.setdefault("VOODOO_QUEUE_PROVIDER", "memory")


@pytest.fixture(autouse=True)
def _clean_page_registry():
    """Isolate the global @page registry between tests."""
    from voodoo.core.routing import page_registry

    page_registry.clear()
    yield
    page_registry.clear()


@pytest.fixture(autouse=True)
def _reset_queue_state():
    """Reset queue provider and running worker tasks between tests.

    The ``_workers`` handler registry is *not* cleared — handlers register
    at import time via ``@queue``/``@task`` and must persist. Only the
    provider (``_queue``) and asyncio tasks (``_worker_tasks``) are stateful.
    """
    from voodoo.workers import queue as worker_mod

    worker_mod._queue = None
    for task in worker_mod._worker_tasks:
        task.cancel()
    worker_mod._worker_tasks.clear()
    yield
    for task in worker_mod._worker_tasks:
        task.cancel()
    worker_mod._worker_tasks.clear()
    worker_mod._queue = None


@pytest_asyncio.fixture(autouse=True)
async def _close_db_after_test():
    """Close optional SQLite resources before the test loop is torn down."""
    yield
    import voodoo.data.base as _db_base
    from voodoo.data import store_backend
    from voodoo.runtime import store as _runtime_store_mod
    from voodoo.storage.database.sqlite import _close_open_sqlite_databases

    await _close_open_sqlite_databases()
    # Reset the global connection references so the next test's get_db()
    # doesn't return a stale/closed connection and fall back to the
    # default file-based database.
    _db_base._db_connection = None
    _db_base._database = None
    # Reset the Voodoo Store runtime so the Store-backed Model doesn't
    # accumulate records across tests.
    if _runtime_store_mod._shared_runtime_store is not None:
        _runtime_store_mod._shared_runtime_store.stop()
        _runtime_store_mod._shared_runtime_store = None
    _runtime_store_mod._active_runtime_store = None
    store_backend._runtime_store = None
    # Remove the Store's on-disk file so the next test starts fresh.
    import shutil
    from pathlib import Path
    voodoo_dir = Path.cwd() / ".voodoo"
    if voodoo_dir.exists():
        shutil.rmtree(voodoo_dir, ignore_errors=True)


@pytest.fixture
def model_store(tmp_path):
    """Bind a fresh application.vstore for one Store-native Model test."""
    from voodoo.data.store_backend import bind_runtime_store
    from voodoo.runtime.store import RuntimeStore, StoreConfig

    runtime = RuntimeStore(
        StoreConfig(path=tmp_path / "application.vstore", enabled=True)
    )
    runtime.start()
    bind_runtime_store(runtime)
    try:
        yield runtime
    finally:
        bind_runtime_store(None)
        runtime.stop()


@pytest.fixture
def app(monkeypatch):
    """Fixture to provide the Starlette app with mocked database initialization."""
    original_init_db = voodoo.data.init_db

    async def mock_init_db(db_path=":memory:"):
        await original_init_db(db_path)

    monkeypatch.setattr(voodoo.data, "init_db", mock_init_db)

    return create_app()


@pytest.fixture
def client(app):
    """Provide a TestClient whose context manager runs startup and shutdown."""
    with TestClient(app) as test_client:
        yield test_client


@pytest_asyncio.fixture
async def test_db():
    """Initialize explicit SQLite for adapter-compatibility tests only."""
    await voodoo.data.init_db(":memory:")
    db = await voodoo.data.get_db()
    yield db
    await voodoo.data.close_db()
