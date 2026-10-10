"""Tests for HTTP × Runtime integration.

Every API handler runs through the Voodoo runtime engine, producing an
Execution record (intent ``http:GET /path``) with actor, effects and cost.
"""

from __future__ import annotations

import asyncio
import importlib

import pytest
from starlette.testclient import TestClient

import voodoo.data
from voodoo.core import create_app
from voodoo.observability import telemetry_store
from voodoo.routing.api import api
from voodoo.runtime.execution import ExecutionStatus
from voodoo.runtime.execution.engine import engine as runtime_engine
from voodoo.runtime.store import get_active_runtime_store

app_module = importlib.import_module("voodoo.core.app")


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
    def test_liveness_and_readiness_probes_are_explicit(self, make_client):
        telemetry_store.metrics.setdefault("requests", []).clear()
        with make_client() as client:
            health = client.get(
                "/healthz",
                headers={
                    "x-trace-id": "trace-from-gateway",
                    "x-correlation-id": "request-42",
                },
            )
            ready = client.get("/readyz")

        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        assert health.headers["x-trace-id"] == "trace-from-gateway"
        assert health.headers["x-correlation-id"] == "request-42"
        request_metric = telemetry_store.metrics["requests"][-2]
        assert request_metric["trace_id"] == "trace-from-gateway"
        assert request_metric["correlation_id"] == "request-42"
        assert request_metric["status_code"] == 200
        assert ready.status_code == 200
        assert ready.json()["status"] == "ready"
        assert ready.json()["mode"] == "ready"
        assert ready.json()["capacity_pressure"] is False
        assert ready.json()["recovery_mode"] is False
        assert ready.json()["store"]["within_limit"] is True

        assert client.app.state.lifecycle_phase == "stopped"

    def test_lifecycle_marks_app_ready_only_during_active_lifespan(self, make_client):
        with make_client() as client:
            assert client.app.state.lifecycle_phase == "ready"
            response = client.get("/readyz")
            assert response.status_code == 200
            assert response.json()["status"] == "ready"

    @pytest.mark.parametrize("phase, mode", [("starting", "starting"), ("stopping", "shutting_down")])
    def test_readiness_fails_closed_during_lifecycle_transitions(
        self, make_client, phase, mode
    ):
        with make_client() as client:
            client.app.state.lifecycle_phase = phase
            response = client.get("/readyz")

        assert response.status_code == 503
        assert response.json() == {
            "status": "not_ready",
            "mode": mode,
            "lifecycle_phase": phase,
        }

    def test_readiness_reports_migration_required_mode(self, make_client, monkeypatch):
        monkeypatch.setattr(
            "voodoo.data.base.migration_health",
            lambda: {
                "status": "migration_required",
                "current_version": 4,
                "error": "schema upgrade required",
            },
        )

        with make_client() as client:
            ready = client.get("/readyz")

        assert ready.status_code == 503
        assert ready.json()["status"] == "not_ready"
        assert ready.json()["mode"] == "migration_required"
        assert ready.json()["migration"]["current_version"] == 4

    def test_readiness_fails_closed_when_store_health_probe_raises(
        self, make_client, caplog
    ):
        class BrokenStore:
            def health(self):
                raise RuntimeError("token=readiness-secret store unavailable")

        with make_client() as client:
            client.app.state.runtime_store = BrokenStore()
            with caplog.at_level("WARNING", logger=app_module.logger.name):
                ready = client.get("/readyz")

        assert ready.status_code == 503
        assert ready.json() == {
            "status": "not_ready",
            "mode": "store_unavailable",
            "store": {"opened": False, "verified": False},
        }
        assert "readiness-secret" not in caplog.text

    def test_readiness_does_not_hide_store_invariant_failures(self, make_client):
        class BrokenStore:
            def health(self):
                raise AssertionError("readiness invariant failed")

        with make_client() as client:
            client.app.state.runtime_store = BrokenStore()
            with pytest.raises(AssertionError, match="invariant failed"):
                client.get("/readyz")

    def test_readiness_redacts_and_bounds_store_details(self, make_client):
        class StoreWithSensitiveHealth:
            def health(self):
                return type(
                    "Health",
                    (),
                    {
                        "opened": True,
                        "verified": True,
                        "details": {
                            "within_limit": True,
                            "path": "/private/store.vstore",
                            "payload": "secret-payload",
                            "nested": {"count": 3, "opaque": object()},
                        },
                    },
                )()

        with make_client() as client:
            client.app.state.runtime_store = StoreWithSensitiveHealth()
            ready = client.get("/readyz")

        assert ready.status_code == 200
        assert ready.json()["store"] == {
            "within_limit": True,
            "nested": {"count": 3},
        }

    def test_startup_failure_unwinds_partial_runtime_store(
        self, make_client, monkeypatch
    ):
        async def fail_mqtt(*_args, **_kwargs):
            raise RuntimeError("synthetic startup failure")

        monkeypatch.setattr(app_module, "_start_mqtt", fail_mqtt)
        app = create_app()

        with pytest.raises(RuntimeError, match="synthetic startup failure"):
            with TestClient(app):
                pass

        assert get_active_runtime_store() is None
        assert app.state.lifecycle_phase == "stopped"

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
