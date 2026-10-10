"""Acceptance coverage for the Runtime-native agent registry."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from voodoo.agents.models import AgentEntity, AgentRunRecord
from voodoo.agents.registry import VoodooStoreAgentRegistry
from voodoo.runtime.store import RuntimeStore, StoreConfig, bind_active_runtime_store


def _runtime(path: Path) -> RuntimeStore:
    runtime = RuntimeStore(StoreConfig(path=path))
    runtime.start()
    bind_active_runtime_store(runtime)
    return runtime


@pytest.mark.asyncio
async def test_agent_registry_uses_native_collections_and_survives_restart(
    tmp_path: Path,
) -> None:
    path = tmp_path / "agents.vstore"
    runtime = _runtime(path)
    entity = AgentEntity(
        agent_id="agent:planner",
        name="Planner",
        model="test:model",
        capabilities=["plan"],
    )
    run = AgentRunRecord(
        run_id="run-1",
        agent_id=entity.agent_id,
        execution_id="execution-1",
        prompt="plan",
        output="done",
        started_at=10.0,
    )
    try:
        registry = VoodooStoreAgentRegistry()
        await registry.register(entity)
        await registry.record_run(run)

        native = runtime.provider.native
        assert native.collection_definition(b"runtime.agents") == (1, b"json")
        assert native.collection_definition(b"runtime.agent_runs") == (1, b"json")
        assert native.get_record(b"runtime.agents", b"agent:planner") is not None
        assert native.get_record(b"runtime.agent_runs", b"run-1") is not None
        assert (await registry.get("agent:planner")).name == "Planner"
        assert (await registry.get_runs("agent:planner"))[0].run_id == "run-1"
    finally:
        bind_active_runtime_store(None)
        runtime.stop()

    reopened_runtime = _runtime(path)
    try:
        reopened = VoodooStoreAgentRegistry()
        assert (await reopened.get("agent:planner")).model == "test:model"
        assert [item.agent_id for item in await reopened.list_agents()] == [
            "agent:planner"
        ]
        assert (await reopened.get_runs("agent:planner"))[0].output == "done"
    finally:
        bind_active_runtime_store(None)
        reopened_runtime.stop()


@pytest.mark.asyncio
async def test_agent_registry_reads_legacy_and_rejects_future_schema(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path / "agent-codec.vstore")
    try:
        registry = VoodooStoreAgentRegistry()
        native = runtime.provider.native
        legacy = AgentEntity(agent_id="agent:legacy", name="Legacy").to_dict()
        native.put(
            registry._agent_key("agent:legacy"),
            json.dumps(legacy).encode("utf-8"),
        )
        assert (await registry.get("agent:legacy")).name == "Legacy"
        await registry.register(AgentEntity(agent_id="agent:legacy", name="Migrated"))
        assert native.get_record(b"runtime.agents", b"agent:legacy") is not None
        assert native.get(registry._agent_key("agent:legacy")) is None

        legacy_run = AgentRunRecord(
            run_id="run-legacy",
            agent_id="agent:legacy",
            started_at=11.0,
            output="legacy",
        )
        native.put(
            registry._run_key(legacy_run),
            json.dumps(legacy_run.to_dict()).encode("utf-8"),
        )
        await registry.record_run(legacy_run)
        assert native.get_record(b"runtime.agent_runs", b"run-legacy") is not None
        assert native.get(registry._run_key(legacy_run)) is None

        future = dict(legacy)
        future["_schema_version"] = 99
        native.put(
            registry._agent_key("agent:future"),
            json.dumps(future).encode("utf-8"),
        )
        with pytest.raises(ValueError, match="newer than supported"):
            await registry.get("agent:future")
    finally:
        bind_active_runtime_store(None)
        runtime.stop()
