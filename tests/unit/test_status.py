from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import voodoo.status as status_module


@pytest.mark.asyncio
async def test_status_distinguishes_degraded_services(monkeypatch):
    async def operational_database():
        return {"status": "Operational"}

    async def degraded_queue():
        return {"status": "Degraded", "workers": 0}

    async def operational_storage():
        return {"status": "Operational"}

    async def operational_agent():
        return {"status": "Operational"}

    monkeypatch.setattr(status_module, "check_database", operational_database)
    monkeypatch.setattr(status_module, "check_queue", degraded_queue)
    monkeypatch.setattr(status_module, "check_storage", operational_storage)
    monkeypatch.setattr(status_module, "check_agent", operational_agent)

    response = await status_module.get_status()

    assert response.status_code == 200
    payload = json.loads(response.body)
    assert payload["overall"] == "Degraded"
    assert payload["degraded"] == ["queue"]
    assert payload["attention"]["queue"].startswith("start or reconnect workers")
    assert payload["policy"] == {
        "http_status": 200,
        "traffic": "serve_with_attention",
    }


@pytest.mark.asyncio
async def test_agent_health_reports_resolved_model_without_network_call(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(status_module, "get_active_runtime_store", lambda: None)

    def fake_default_model() -> str:
        calls.append("default")
        return "mock:test"

    def fake_resolve_model(model: str) -> tuple[str, str]:
        calls.append(model)
        return ("mock", "test")

    monkeypatch.setattr(
        "voodoo.ai.providers.default_model", fake_default_model
    )
    monkeypatch.setattr("voodoo.ai.providers.resolve_model", fake_resolve_model)

    result = await status_module.check_agent()

    assert result == {
        "status": "Operational",
        "provider": "mock",
        "model": "test",
        "verified": False,
        "probe": "configuration",
    }
    assert calls == ["default", "mock:test"]


@pytest.mark.asyncio
async def test_agent_health_rejects_invalid_model_configuration(monkeypatch):
    monkeypatch.setattr(
        "voodoo.ai.providers.default_model", lambda: "missing-provider:model"
    )

    result = await status_module.check_agent()

    assert result["status"] == "Down"
    assert "Unknown provider" in result["error"]


@pytest.mark.asyncio
async def test_agent_health_does_not_hide_provider_implementation_failures(monkeypatch):
    def broken_default_model() -> str:
        raise RuntimeError("provider implementation failed")

    monkeypatch.setattr(
        "voodoo.ai.providers.default_model", broken_default_model
    )
    with pytest.raises(RuntimeError, match="implementation failed"):
        await status_module.check_agent()


@pytest.mark.asyncio
async def test_status_returns_service_unavailable_for_down_service(monkeypatch):
    async def down_database():
        return {"status": "Down", "error": "[REDACTED]"}

    async def operational():
        return {"status": "Operational"}

    monkeypatch.setattr(status_module, "check_database", down_database)
    monkeypatch.setattr(status_module, "check_queue", operational)
    monkeypatch.setattr(status_module, "check_storage", operational)
    monkeypatch.setattr(status_module, "check_agent", operational)

    response = await status_module.get_status()

    assert response.status_code == 503
    payload = json.loads(response.body)
    assert payload["overall"] == "Down"
    assert "database" in payload["attention"]
    assert payload["policy"] == {"http_status": 503, "traffic": "fail_closed"}


@pytest.mark.asyncio
async def test_database_health_failure_emits_redacted_structured_diagnostic(
    monkeypatch, caplog
):
    async def failing_database():
        raise RuntimeError("token=super-secret database unavailable")

    monkeypatch.setattr(status_module, "get_db", failing_database)

    with caplog.at_level("WARNING", logger=status_module.logger.name):
        result = await status_module.check_database()

    assert result == {"status": "Down", "error": "token=[REDACTED] database unavailable"}
    record = next(record for record in caplog.records if record.message == "health check failed")
    assert record.health_check == "database"
    assert record.error == result["error"]
    assert "super-secret" not in caplog.text


@pytest.mark.asyncio
async def test_database_health_does_not_hide_unexpected_implementation_failures(
    monkeypatch,
):
    async def broken_database():
        raise AssertionError("database invariant failed")

    monkeypatch.setattr(status_module, "get_db", broken_database)

    with pytest.raises(AssertionError, match="invariant failed"):
        await status_module.check_database()


@pytest.mark.asyncio
async def test_store_health_projects_capacity_and_redacts_details(monkeypatch):
    fake_runtime = SimpleNamespace(
        health=lambda: SimpleNamespace(
            provider="voodoo",
            path=Path("/private/store.vstore"),
            opened=True,
            verified=True,
            details={
                "within_limit": False,
                "error": "token=secret store pressure",
            },
        )
    )
    monkeypatch.setattr(status_module, "get_active_runtime_store", lambda: fake_runtime)

    result = await status_module.check_store()

    assert result["status"] == "Degraded"
    assert result["details"]["error"] == "token=[REDACTED] store pressure"
    assert "secret" not in json.dumps(result)


@pytest.mark.asyncio
async def test_store_health_does_not_hide_unexpected_implementation_failures(
    monkeypatch,
):
    fake_runtime = SimpleNamespace(
        health=lambda: (_ for _ in ()).throw(AssertionError("store invariant failed"))
    )
    monkeypatch.setattr(status_module, "get_active_runtime_store", lambda: fake_runtime)

    with pytest.raises(AssertionError, match="store invariant failed"):
        await status_module.check_store()


@pytest.mark.asyncio
async def test_store_health_details_are_bounded_json_safe_and_identifier_free(monkeypatch):
    fake_runtime = SimpleNamespace(
        health=lambda: SimpleNamespace(
            provider="voodoo",
            opened=True,
            verified=True,
            details={
                "store_id": b"opaque-id",
                "path": Path("/private/store.vstore"),
                "nested": {"count": 3, "bytes": b"payload"},
                "message": "healthy",
            },
        )
    )
    monkeypatch.setattr(status_module, "get_active_runtime_store", lambda: fake_runtime)

    result = await status_module.check_store()

    assert result["details"] == {
        "nested": {"count": 3},
        "message": "healthy",
    }
    assert json.dumps(result)
