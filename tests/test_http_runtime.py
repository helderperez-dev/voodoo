"""Tests for HTTP × Runtime integration.

Every API handler runs through the Voodoo runtime engine, producing an
Execution record (intent ``http:GET /path``) with actor, effects and cost.
"""

from __future__ import annotations

import asyncio

import pytest
from starlette.testclient import TestClient

import voodoo.data
from voodoo.core import create_app
from voodoo.routing.api import api
from voodoo.runtime.engine import engine as runtime_engine
from voodoo.runtime.execution import ExecutionStatus


@pytest.fixture
def make_client(monkeypatch):
    """Build a TestClient whose database init is pointed at an in-memory DB.

    Routes must be registered (via @api decorators) BEFORE calling this
    factory — the Starlette app snapshots ``api.routes`` at creation time.
    """

    real_init_db = voodoo.data.init_db

    async def memory_db(db_path=":memory:"):
        await real_init_db(":memory:")

    monkeypatch.setattr(voodoo.data, "init_db", memory_db)

    def _make(raise_server_exceptions: bool = True) -> TestClient:
        return TestClient(create_app(), raise_server_exceptions=raise_server_exceptions)

    return _make


def _execution_for(intent_name: str):
    for ex in reversed(runtime_engine.executions.values()):
        if ex.intent and ex.intent.name == intent_name:
            return ex
    return None


class TestHTTPRuntimeIntegration:
    def test_route_executes_through_engine(self, make_client):
        @api.get("/runtime-ping")
        def ping():
            return {"ok": True}

        with make_client() as client:
            response = client.get("/runtime-ping")

        assert response.status_code == 200
        assert response.json() == {"ok": True}

        ex = _execution_for("http:GET /runtime-ping")
        assert ex is not None
        assert ex.status is ExecutionStatus.COMPLETED
        assert ex.actor == "anonymous"
        assert ex.result == {"ok": True}

    def test_route_with_query_param(self, make_client):
        @api.get("/runtime-echo")
        def echo(name: str):
            return {"hello": name}

        with make_client() as client:
            response = client.get("/runtime-echo", params={"name": "voodoo"})

        assert response.status_code == 200
        assert response.json() == {"hello": "voodoo"}

        ex = _execution_for("http:GET /runtime-echo")
        assert ex is not None
        assert ex.intent.params.get("name") == "voodoo"

    def test_async_route(self, make_client):
        @api.get("/runtime-async")
        async def slow():
            await asyncio.sleep(0)
            return {"async": True}

        with make_client() as client:
            response = client.get("/runtime-async")

        assert response.status_code == 200
        assert response.json() == {"async": True}

        ex = _execution_for("http:GET /runtime-async")
        assert ex is not None
        assert ex.status is ExecutionStatus.COMPLETED

    def test_route_failure_records_failed_execution(self, make_client):
        @api.get("/runtime-boom")
        def boom():
            raise ValueError("kaboom")

        # Build the client directly so the raised ExecutionError is
        # converted into a 500 response instead of re-raised.
        with make_client(raise_server_exceptions=False) as client:
            response = client.get("/runtime-boom")

        assert response.status_code == 500

        ex = _execution_for("http:GET /runtime-boom")
        assert ex is not None
        assert ex.status is ExecutionStatus.FAILED
        assert ex.error is not None

    def test_route_without_runtime_skips_engine(self, make_client):
        @api.get("/runtime-direct")
        def direct():
            return {"direct": True}

        api.run_through_runtime = False
        try:
            with make_client() as client:
                response = client.get("/runtime-direct")
        finally:
            api.run_through_runtime = True

        assert response.status_code == 200
        assert response.json() == {"direct": True}
        assert _execution_for("http:GET /runtime-direct") is None
