import asyncio

import pytest
import pytest_asyncio
from starlette.testclient import TestClient

import voodoo.data
import voodoo.queue
from voodoo.core import create_app


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def _clean_page_registry():
    """Isolate the global @page registry between tests."""
    from voodoo.core.routing import page_registry

    page_registry.clear()
    yield
    page_registry.clear()


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
    if voodoo.data._db_connection:
        await voodoo.data._db_connection.close()
        voodoo.data._db_connection = None
