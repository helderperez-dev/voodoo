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
    """Close lazily-opened async DB resources before the test loop is torn down.

    aiosqlite owns a worker thread whose futures are bound to the event loop
    that opened the connection. Closing it later with ``asyncio.run`` creates a
    second loop and can leave the worker trying to report into an already-closed
    one. Keeping cleanup in an async fixture guarantees teardown happens while
    pytest's owning loop is still alive. Starlette lifespan shutdown normally
    clears the same globals first, making this a no-op for TestClient tests.
    """
    yield
    from voodoo.data import base

    if base._db_connection is not None:
        await voodoo.data.close_db()


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
    """Initialize an in-memory database for data tests without starting the app."""
    await voodoo.data.init_db(":memory:")
    db = await voodoo.data.get_db()
    yield db
    await voodoo.data.close_db()
