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
    """Close every async SQLite resource before the test loop is torn down.

    ``data.base`` owns the normal application DB, while contract/provider tests
    may instantiate independent SQLite adapters. All of them use aiosqlite
    worker threads bound to the loop that opened them, so teardown must happen
    here rather than after pytest closes that loop.
    """
    yield
    from voodoo.data import base
    from voodoo.storage.database.sqlite import _close_open_sqlite_databases

    if base._db_connection is not None:
        await voodoo.data.close_db()
    await _close_open_sqlite_databases()


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
