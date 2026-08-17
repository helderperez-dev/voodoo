import asyncio

import pytest
import pytest_asyncio
from starlette.testclient import TestClient

import voodoo.data
import voodoo.queue
from voodoo.core import create_app


@pytest.fixture(autouse=True)
def _clean_page_registry():
    """Isolate the global @page registry between tests."""
    from voodoo.core.routing import page_registry

    page_registry.clear()
    yield
    page_registry.clear()


@pytest.fixture(autouse=True)
def _close_db_after_test():
    """Close any lazily-opened database connection after each test.

    aiosqlite runs each connection on a dedicated non-daemon thread; a
    connection left open would keep the pytest process alive at
    interpreter shutdown. Reads of ``voodoo.data._db_connection`` forward
    to ``voodoo.data.base`` via PEP 562 — never *assign* through the
    package, that would create a stale shadow global (there is no module
    ``__setattr__`` in Python).
    """
    yield
    from voodoo.data import base

    if base._db_connection is not None:
        try:
            asyncio.run(voodoo.data.close_db())
        except Exception:
            # Best-effort cleanup; never fail a test here
            base._db_connection = None


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
    """Fixture to provide a Starlette TestClient with context manager (triggers startup/shutdown)."""
    with TestClient(app) as c:
        yield c


@pytest_asyncio.fixture
async def test_db():
    """Fixture to initialize an in-memory database for data tests without starting the app."""
    await voodoo.data.init_db(":memory:")
    db = await voodoo.data.get_db()
    yield db
    await voodoo.data.close_db()
