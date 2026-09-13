"""Sprint 26.5 — structured distributed Execution outcomes."""

from __future__ import annotations

import asyncio
import json

import pytest

from voodoo.mesh import MeshNetwork, RemoteExecutionOutcome, RemoteExecutionRequest
from voodoo.mesh.client import MeshClient
from voodoo.primitives.capability import Capability
from voodoo.runtime import ExecutionEngine
from voodoo.runtime.execution import ExecutionStatus


@pytest.mark.asyncio
async def test_waiting_outcome_crosses_remote_boundary_and_refreshes_after_approval():
    engine = ExecutionEngine()
    engine.capabilities.register(Capability(name="device.reboot"))
    engine.capabilities.require_approval("device.reboot")
    net = MeshNetwork(execution_engine=engine)
    net.grant_remote("operator", "device.reboot")
    calls = 0

    @net.expose(name="device.reboot", capability="device.reboot")
    async def reboot():
        nonlocal calls
        calls += 1
        return {"rebooted": True}

    request = RemoteExecutionRequest(
        request_id="req-waiting",
        operation="device.reboot",
        actor="operator",
    )
    waiting = await net.execute_remote(request)

    assert waiting.status == "waiting"
    assert waiting.execution_id is not None
    assert waiting.error is not None
    assert waiting.error["type"] == "ApprovalRequired"
    assert calls == 0
    execution = engine.get(waiting.execution_id)
    assert execution is not None
    assert execution.status is ExecutionStatus.WAITING

    await engine.approve(waiting.execution_id, by="ops")
    refreshed = await net.execute_remote(request)

    assert refreshed.status == "completed"
    assert refreshed.execution_id == waiting.execution_id
    assert refreshed.result == {"rebooted": True}
    assert refreshed.error is None
    assert calls == 1
    assert engine.get(waiting.execution_id).status is ExecutionStatus.COMPLETED


@pytest.mark.asyncio
async def test_failed_remote_execution_is_structured_not_flattened():
    engine = ExecutionEngine()
    net = MeshNetwork(execution_engine=engine)

    @net.expose(name="service.fail")
    async def fail():
        raise RuntimeError("service exploded")

    outcome = await net.execute_remote(
        RemoteExecutionRequest(operation="service.fail", actor="client-a")
    )

    assert outcome.status == "failed"
    assert outcome.execution_id is not None
    assert outcome.trace_id is not None
    assert outcome.error is not None
    assert outcome.error["type"] == "ExecutionError"
    assert "service exploded" in outcome.error["message"]


@pytest.mark.asyncio
async def test_wire_response_always_contains_full_structured_outcome():
    net = MeshNetwork(execution_engine=ExecutionEngine())
    sent: list[str] = []

    class Socket:
        async def send_text(self, data: str):
            sent.append(data)

    outcome = RemoteExecutionOutcome(
        request_id="req-1",
        execution_id="exec-1",
        trace_id="trace-1",
        status="waiting",
        error={"type": "ApprovalRequired", "message": "approval required"},
    )
    await net._send_remote_outcome(Socket(), message_id="rpc-1", outcome=outcome)

    payload = json.loads(sent[0])
    assert payload["id"] == "rpc-1"
    assert payload["outcome"]["status"] == "waiting"
    assert payload["outcome"]["execution_id"] == "exec-1"
    assert payload["outcome"]["error"]["type"] == "ApprovalRequired"
    # Legacy callers still receive a normal JSON-RPC error projection.
    assert payload["error"] == "approval required"


@pytest.mark.asyncio
async def test_structured_client_receive_does_not_turn_waiting_into_exception():
    client = MeshClient("ws://unused")
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    client._pending_requests["rpc-1"] = future
    client._structured_requests.add("rpc-1")

    response = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "rpc-1",
            "error": "approval required",
            "outcome": {
                "request_id": "req-1",
                "execution_id": "exec-1",
                "trace_id": "trace-1",
                "status": "waiting",
                "error": {
                    "type": "ApprovalRequired",
                    "message": "approval required",
                },
            },
        }
    )

    class Socket:
        def __aiter__(self):
            self._done = False
            return self

        async def __anext__(self):
            if self._done:
                raise StopAsyncIteration
            self._done = True
            return response

    client.ws = Socket()
    await client._receive_loop()
    outcome = await future

    assert isinstance(outcome, RemoteExecutionOutcome)
    assert outcome.status == "waiting"
    assert outcome.error["type"] == "ApprovalRequired"


@pytest.mark.asyncio
async def test_client_execute_sends_stable_request_identity_and_lineage():
    client = MeshClient("ws://unused")
    sent: list[str] = []

    class Socket:
        closed = False

        async def send(self, data: str):
            sent.append(data)

    client.ws = Socket()
    task = asyncio.create_task(
        client.execute(
            "robot.inspect",
            arguments={"zone": "A"},
            actor="planner",
            request_id="stable-request",
            correlation_id="trace-parent",
            parent_execution_id="exec-parent",
            target_entity_id="robot-01",
            metadata={"mission": "m-1"},
        )
    )

    while not sent:
        await asyncio.sleep(0)

    payload = json.loads(sent[0])
    msg_id = payload["id"]
    params = payload["params"]
    assert params == {
        "operation": "robot.inspect",
        "arguments": {"zone": "A"},
        "actor": "planner",
        "request_id": "stable-request",
        "correlation_id": "trace-parent",
        "parent_execution_id": "exec-parent",
        "target_entity_id": "robot-01",
        "metadata": {"mission": "m-1"},
    }

    client._pending_requests[msg_id].set_result(
        RemoteExecutionOutcome(
            request_id="stable-request",
            execution_id="exec-child",
            trace_id="trace-child",
            status="completed",
            result={"ok": True},
        )
    )
    outcome = await task
    assert outcome.status == "completed"
