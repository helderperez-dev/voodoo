from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from voodoo.observability.api import get_metrics, get_metrics_prometheus
from voodoo.observability.store import telemetry_store


@pytest.mark.asyncio
async def test_prometheus_metrics_endpoint_is_bounded_and_scrapeable(monkeypatch):
    monkeypatch.setitem(telemetry_store.metrics, "requests_total", 7)
    monkeypatch.setitem(telemetry_store.metrics, "errors_total", 2)
    response = await get_metrics_prometheus()

    assert response.media_type.startswith("text/plain")
    assert response.charset == "utf-8"
    body = response.body.decode()
    assert 'voodoo_metrics_info{version="1"} 1' in body
    assert "# TYPE voodoo_requests_total counter" in body
    assert "voodoo_requests_total 7" in body
    assert "recent_traces" not in body


@pytest.mark.asyncio
async def test_prometheus_metrics_skip_non_finite_samples(monkeypatch):
    monkeypatch.setitem(telemetry_store.metrics, "bad_nan", math.nan)
    monkeypatch.setitem(telemetry_store.metrics, "bad_inf", math.inf)
    response = await get_metrics_prometheus()
    body = response.body.decode()
    assert "voodoo_bad_nan" not in body
    assert "voodoo_bad_inf" not in body


@pytest.mark.asyncio
async def test_metrics_projects_sanitized_active_store_health(monkeypatch):
    fake_health = SimpleNamespace(
        provider="voodoo",
        opened=True,
        verified=True,
        details={
            "native_health": {
                "store_id": b"must-not-be-exported",
                "queue_ready": 3,
                "metrics": {"commits": 7},
            }
        },
    )
    fake_runtime = SimpleNamespace(health=lambda: fake_health)
    monkeypatch.setattr(
        "voodoo.runtime.store.get_active_runtime_store", lambda: fake_runtime
    )

    summary = await get_metrics()
    assert summary["store_health"]["details"]["native_health"]["queue_ready"] == 3
    assert "store_id" not in summary["store_health"]["details"]["native_health"]

    response = await get_metrics_prometheus()
    body = response.body.decode()
    assert "voodoo_store_health_details_native_health_queue_ready 3" in body
    assert "voodoo_store_health_details_native_health_metrics_commits 7" in body
    assert "must-not-be-exported" not in body


@pytest.mark.asyncio
async def test_metrics_json_drops_paths_and_non_numeric_health_payloads(monkeypatch):
    fake_health = SimpleNamespace(
        provider="voodoo",
        opened=True,
        verified=True,
        details={
            "path": "/private/store.vstore",
            "secret_token": "password=do-not-export",
            "within_limit": True,
            "queue_ready": 4,
            "nested": {"latency_ms": 2.5, "message": "not a metric"},
        },
    )
    monkeypatch.setattr(
        "voodoo.runtime.store.get_active_runtime_store",
        lambda: SimpleNamespace(health=lambda: fake_health),
    )

    summary = await get_metrics()
    details = summary["store_health"]["details"]
    assert details == {
        "within_limit": True,
        "queue_ready": 4,
        "nested": {"latency_ms": 2.5},
    }
