"""Sprint 26.1/26.2 — canonical remote requests and governed Mesh ingress."""

from __future__ import annotations

import json

import pytest
from starlette.websockets import WebSocketDisconnect

from voodoo.mesh import MeshNetwork
from voodoo.mesh.remote import RemoteExecutionRequest
from voodoo.runtime import ExecutionContext, ExecutionEngine
from voodoo.runtime.execution import ExecutionStatus


def test_legacy_jsonrpc_call_normalizes_to_canonical_request():
    request = RemoteExecutionRequest.from_jsonrpc(
        {"name": "math.add", "arguments": {"a": 2, "b": 3}},
        message_id="rpc-123",
    )

    assert request.request_id == "rpc-123"
    assert request.operation == "math.add"
    assert request.arguments == {"a": 2, "b": 3}
    assert request.actor == "anonymous"
    assert request.runtime_actor == "remote:anonymous"


def test_canonical_remote_request_preserves_lineage_and_target():
    request = RemoteExecutionRequest.from_jsonrpc(
        {
            "schema_version": 1,
            "request_id": "req-1",
            "operation": "device.inspect",
            "arguments": {"detail": True},
            "actor": "node-a",
            "correlation_id": "corr-1",
            "parent_execution_id": "exec-parent",
            "target_entity_id": "device-7",
            "metadata": {"zone": "lab"},
        }
    )

    assert request.request_id == "req-1"
    assert request.runtime_actor == "remote:node-a"
    assert request.correlation_id == "corr-1"
    assert request.parent_execution_id == "exec-parent"
    assert request.target_entity_id == "device-7"
    assert request.metadata == {"zone": "lab"}


def test_remote_request_rejects_malformed_arguments_before_compute():
    with pytest.raises(ValueError, match="arguments must be an object"):
        RemoteExecutionRequest.from_jsonrpc(
            {"name": "bad.call", "arguments": ["not", "a", "mapping"]}
        )


def test_expose_keeps_callable_compatibility_and_registers_operation_metadata():
    net = MeshNetwork(execution_engine=ExecutionEngine())

    @net.expose(
        name="device.reboot",
        capability="device.control",
        intent_name="device:reboot",
    )
    def reboot(device_id: str):
        return device_id

    assert net.exposed_functions["device.reboot"] is reboot
    operation = net.exposed_operations["device.reboot"]
    assert operation.func is reboot
    assert operation.capability == "device.control"
    assert operation.intent_name == "device:reboot"


@pytest.mark.asyncio
async def test_remote_call_runs_only_through_execution_engine():
    engine = ExecutionEngine()
    net = MeshNetwork(execution_engine=engine)
    observed_context: dict[str, str] = {}

    @net.expose(name="math.add")
    async def add(a: int, b: int):
        from voodoo.runtime.context import current_context

        ctx = current_context()
        assert ctx is not None
        observed_context["execution_id"] = ctx.execution_id
        observed_context["actor"] = ctx.actor
        return a + b

    request = RemoteExecutionRequest(
        request_id="req-add",
        operation="math.add",
        arguments={"a": 2, "b": 5},
        actor="node-a",
        correlation_id="caller-trace",
    )
    outcome = await net.execute_remote(request)

    assert outcome.status == "completed"
    assert outcome.result == 7
    assert outcome.execution_id is not None
    assert outcome.trace_id is not None
    assert observed_context == {
        "execution_id": outcome.execution_id,
        "actor": "remote:node-a",
    }

    execution = engine.get(outcome.execution_id)
    assert execution is not None
    assert execution.status is ExecutionStatus.COMPLETED
    assert execution.actor == "remote:node-a"
    assert execution.intent is not None
    assert execution.intent.name == "mesh.call:math.add"
    assert execution.intent.params["_remote_request_id"] == "req-add"
    assert execution.intent.params["_remote_correlation_id"] == "caller-trace"


@pytest.mark.asyncio
async def test_remote_target_is_carried_into_runtime_intent_for_policy_context():
    engine = ExecutionEngine()
    net = MeshNetwork(execution_engine=engine)

    @net.expose(name="device.read")
    def read_device():
        return "ok"

    outcome = await net.execute_remote(
        RemoteExecutionRequest(
            request_id="req-target",
            operation="device.read",
            actor="operator-a",
            target_entity_id="device-42",
        )
    )

    execution = engine.get(outcome.execution_id or "")
    assert execution is not None and execution.intent is not None
    assert execution.intent.params["_target_entity_id"] == "device-42"


@pytest.mark.asyncio
async def test_remote_callable_failure_is_canonical_failed_execution():
    engine = ExecutionEngine()
    net = MeshNetwork(execution_engine=engine)

    @net.expose(name="system.fail")
    def fail():
        raise RuntimeError("boom")

    outcome = await net.execute_remote(
        RemoteExecutionRequest(
            request_id="req-fail",
            operation="system.fail",
            actor="node-b",
        )
    )

    assert outcome.status == "failed"
    assert outcome.execution_id is not None
    assert outcome.error is not None
    assert outcome.error["type"] == "ExecutionError"
    assert "boom" in outcome.error["message"]

    execution = engine.get(outcome.execution_id)
    assert execution is not None
    assert execution.status is ExecutionStatus.FAILED
    assert execution.error == "boom"
    assert execution.actor == "remote:node-b"


@pytest.mark.asyncio
async def test_unknown_remote_operation_is_rejected_without_execution():
    engine = ExecutionEngine()
    net = MeshNetwork(execution_engine=engine)

    outcome = await net.execute_remote(
        RemoteExecutionRequest(
            request_id="req-missing",
            operation="missing.operation",
            actor="node-c",
        )
    )

    assert outcome.status == "rejected"
    assert outcome.execution_id is None
    assert outcome.error == {
        "type": "RemoteOperationNotFound",
        "message": "Function not found in Mesh: missing.operation",
    }
    assert engine.executions == {}


@pytest.mark.asyncio
async def test_declared_remote_capability_is_enforced_before_callable_runs():
    engine = ExecutionEngine()
    net = MeshNetwork(execution_engine=engine)
    called = False

    @net.expose(name="device.reboot", capability="device.control")
    def reboot():
        nonlocal called
        called = True
        return "rebooted"

    outcome = await net.execute_remote(
        RemoteExecutionRequest(
            request_id="req-denied",
            operation="device.reboot",
            actor="untrusted-node",
        )
    )

    assert called is False
    assert outcome.status == "failed"
    assert outcome.execution_id is not None
    assert outcome.error is not None
    assert outcome.error["type"] == "CapabilityDenied"

    execution = engine.get(outcome.execution_id)
    assert execution is not None
    assert execution.status is ExecutionStatus.FAILED
    assert execution.intent is not None
    assert execution.intent.requires == ["device.control"]


@pytest.mark.asyncio
async def test_remote_websocket_call_keeps_legacy_result_and_adds_execution_metadata():
    engine = ExecutionEngine()
    net = MeshNetwork(execution_engine=engine)

    @net.expose(name="math.double")
    def double(value: int):
        return value * 2

    incoming = [
        json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "call",
                "id": "rpc-double",
                "params": {
                    "name": "math.double",
                    "arguments": {"value": 4},
                    "actor": "node-wire",
                },
            }
        )
    ]
    sent: list[str] = []

    class FakeWebSocket:
        async def accept(self):
            return None

        async def receive_text(self):
            if incoming:
                return incoming.pop(0)
            raise WebSocketDisconnect()

        async def send_text(self, data: str):
            sent.append(data)

    websocket = FakeWebSocket()
    await net._handle_websocket(websocket)  # type: ignore[arg-type]

    assert len(sent) == 1
    response = json.loads(sent[0])
    assert response["id"] == "rpc-double"
    assert response["result"] == 8
    assert response["voodoo"]["request_id"] == "rpc-double"
    assert response["voodoo"]["status"] == "completed"
    assert response["voodoo"]["execution_id"] in engine.executions


def test_exposed_operation_builds_runtime_intent_without_leaking_arguments_as_kwargs():
    engine = ExecutionEngine()
    net = MeshNetwork(execution_engine=engine)

    @net.expose(name="inspect.context")
    def inspect_context():
        return None

    request = RemoteExecutionRequest(
        request_id="req-context",
        operation="inspect.context",
        actor="node-a",
        arguments={"user_value": "kept"},
        parent_execution_id="parent-1",
    )
    intent = net.exposed_operations["inspect.context"].intent_for(request)

    assert intent.params["arguments"] == {"user_value": "kept"}
    assert intent.params["_remote_parent_execution_id"] == "parent-1"


@pytest.mark.asyncio
async def test_remote_callable_sees_normal_execution_context_type():
    engine = ExecutionEngine()
    net = MeshNetwork(execution_engine=engine)
    contexts: list[ExecutionContext] = []

    @net.expose(name="runtime.context")
    def capture_context():
        from voodoo.runtime.context import current_context

        ctx = current_context()
        assert ctx is not None
        contexts.append(ctx)
        return ctx.execution_id

    outcome = await net.execute_remote(
        RemoteExecutionRequest(
            request_id="req-context-type",
            operation="runtime.context",
            actor="node-context",
        )
    )

    assert outcome.status == "completed"
    assert len(contexts) == 1
    assert isinstance(contexts[0], ExecutionContext)
    assert contexts[0].engine is engine
    assert outcome.result == outcome.execution_id
