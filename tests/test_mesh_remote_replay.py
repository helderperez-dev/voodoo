"""Sprint 26.4 — request replay/idempotency guarantees."""

from __future__ import annotations

import asyncio

import pytest

from voodoo.mesh import MeshNetwork, RemoteExecutionRequest
from voodoo.mesh.replay import SQLiteRemoteReplayStore
from voodoo.runtime import ExecutionEngine


def _request(request_id: str, *, value: int = 1) -> RemoteExecutionRequest:
    return RemoteExecutionRequest(
        request_id=request_id,
        operation="counter.increment",
        actor="client-a",
        arguments={"value": value},
    )


@pytest.mark.asyncio
async def test_duplicate_request_returns_same_outcome_without_second_execution():
    engine = ExecutionEngine()
    net = MeshNetwork(execution_engine=engine)
    calls = 0

    @net.expose(name="counter.increment")
    async def increment(value: int):
        nonlocal calls
        calls += 1
        return calls + value

    request = _request("req-1", value=2)
    first = await net.execute_remote(request)
    second = await net.execute_remote(request)

    assert first.status == "completed"
    assert second.status == "completed"
    assert second.execution_id == first.execution_id
    assert second.trace_id == first.trace_id
    assert second.result == first.result
    assert calls == 1
    assert len(engine.executions) == 1


@pytest.mark.asyncio
async def test_concurrent_duplicate_delivery_executes_only_once():
    engine = ExecutionEngine()
    net = MeshNetwork(execution_engine=engine)
    calls = 0

    @net.expose(name="counter.increment")
    async def increment(value: int):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return calls + value

    request = _request("req-concurrent", value=3)
    first, second = await asyncio.gather(
        net.execute_remote(request),
        net.execute_remote(request),
    )

    assert calls == 1
    assert len(engine.executions) == 1
    assert first.execution_id == second.execution_id
    assert first.result == second.result


@pytest.mark.asyncio
async def test_same_request_id_with_different_payload_is_rejected():
    engine = ExecutionEngine()
    net = MeshNetwork(execution_engine=engine)
    calls = 0

    @net.expose(name="counter.increment")
    async def increment(value: int):
        nonlocal calls
        calls += 1
        return value

    first = await net.execute_remote(_request("req-conflict", value=1))
    conflict = await net.execute_remote(_request("req-conflict", value=2))

    assert first.status == "completed"
    assert conflict.status == "rejected"
    assert conflict.error is not None
    assert conflict.error["type"] == "RemoteReplayConflict"
    assert calls == 1
    assert len(engine.executions) == 1


@pytest.mark.asyncio
async def test_failed_execution_is_replayed_without_retrying_compute():
    engine = ExecutionEngine()
    net = MeshNetwork(execution_engine=engine)
    calls = 0

    @net.expose(name="counter.increment")
    async def increment(value: int):
        nonlocal calls
        calls += 1
        raise RuntimeError(f"boom:{value}")

    request = _request("req-failed", value=7)
    first = await net.execute_remote(request)
    second = await net.execute_remote(request)

    assert first.status == "failed"
    assert second.status == "failed"
    assert second.execution_id == first.execution_id
    assert calls == 1
    assert len(engine.executions) == 1


@pytest.mark.asyncio
async def test_sqlite_replay_survives_process_restart(tmp_path):
    path = tmp_path / "mesh_replay.db"
    engine_a = ExecutionEngine()
    store_a = SQLiteRemoteReplayStore(path)
    net_a = MeshNetwork(execution_engine=engine_a, replay_store=store_a)
    calls = 0

    @net_a.expose(name="counter.increment")
    async def increment(value: int):
        nonlocal calls
        calls += 1
        return value + 10

    request = _request("req-durable", value=5)
    first = await net_a.execute_remote(request)
    store_a.close()

    engine_b = ExecutionEngine()
    store_b = SQLiteRemoteReplayStore(path)
    net_b = MeshNetwork(execution_engine=engine_b, replay_store=store_b)

    @net_b.expose(name="counter.increment")
    async def increment_after_restart(value: int):
        nonlocal calls
        calls += 1
        return value + 100

    replayed = await net_b.execute_remote(request)
    store_b.close()

    assert first.status == "completed"
    assert replayed.status == "completed"
    assert replayed.execution_id == first.execution_id
    assert replayed.result == first.result
    assert calls == 1
    assert engine_b.executions == {}


@pytest.mark.asyncio
async def test_sqlite_replay_detects_conflict_after_restart(tmp_path):
    path = tmp_path / "mesh_replay.db"
    store_a = SQLiteRemoteReplayStore(path)
    net_a = MeshNetwork(execution_engine=ExecutionEngine(), replay_store=store_a)

    @net_a.expose(name="counter.increment")
    async def increment(value: int):
        return value

    await net_a.execute_remote(_request("req-conflict-restart", value=1))
    store_a.close()

    store_b = SQLiteRemoteReplayStore(path)
    net_b = MeshNetwork(execution_engine=ExecutionEngine(), replay_store=store_b)
    conflict = await net_b.execute_remote(
        _request("req-conflict-restart", value=999)
    )
    store_b.close()

    assert conflict.status == "rejected"
    assert conflict.error is not None
    assert conflict.error["type"] == "RemoteReplayConflict"
