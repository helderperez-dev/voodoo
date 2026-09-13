"""Sprint 26.7 — zero-infrastructure two-node distributed acceptance."""

from __future__ import annotations

import pytest

from voodoo.mesh import MeshNetwork, RemoteExecutionRequest
from voodoo.mesh.auth import InMemoryParticipantResolver, ParticipantAuthenticationError
from voodoo.primitives.capability import Capability
from voodoo.runtime import ExecutionEngine
from voodoo.runtime.execution import ExecutionStatus
from voodoo.runtime.policy import PolicyDecision, PolicyResult


async def _deliver(
    node: MeshNetwork,
    *,
    credential: str | None,
    params: dict,
):
    """Local transport harness exercising the same auth/normalize/runtime seam."""
    wire = dict(params)
    if credential is not None:
        wire["credential"] = credential
    identity = await node.resolve_participant(wire, transport="local-acceptance")
    request = RemoteExecutionRequest.from_jsonrpc(wire, message_id="rpc-local")
    request = node.bind_participant(request, identity)
    return await node.execute_remote(request)


def _nodes():
    node_a = MeshNetwork(execution_engine=ExecutionEngine())
    resolver = InMemoryParticipantResolver()
    credential = resolver.register(node_a.node_id, credential="node-a-secret")
    engine_b = ExecutionEngine()
    node_b = MeshNetwork(
        execution_engine=engine_b,
        participant_resolver=resolver,
    )
    return node_a, node_b, engine_b, credential


@pytest.mark.asyncio
async def test_two_node_authenticated_success_and_lineage():
    node_a, node_b, engine_b, credential = _nodes()
    engine_b.capabilities.register(Capability(name="robot.inspect"))
    node_b.grant_remote(node_a.node_id, "robot.inspect")

    @node_b.expose(name="robot.inspect", capability="robot.inspect")
    async def inspect(zone: str):
        return {"zone": zone, "healthy": True}

    outcome = await _deliver(
        node_b,
        credential=credential,
        params={
            "operation": "robot.inspect",
            "arguments": {"zone": "A"},
            "actor": "forged-admin",
            "request_id": "accept-success",
            "correlation_id": "mission-trace",
            "parent_execution_id": "caller-exec",
            "target_entity_id": "robot-01",
            "metadata": {"mission": "m-1"},
        },
    )

    assert outcome.status == "completed"
    assert outcome.result == {"zone": "A", "healthy": True}
    execution = engine_b.get(outcome.execution_id)
    assert execution is not None
    assert execution.actor == f"remote:{node_a.node_id}"
    assert execution.intent.params["_remote_request_id"] == "accept-success"
    assert execution.intent.params["_remote_correlation_id"] == "mission-trace"
    assert execution.intent.params["_remote_parent_execution_id"] == "caller-exec"
    assert execution.intent.params["_target_entity_id"] == "robot-01"


@pytest.mark.asyncio
async def test_two_node_missing_authority_is_denied_before_compute():
    _, node_b, engine_b, credential = _nodes()
    engine_b.capabilities.register(Capability(name="robot.move"))
    calls = 0

    @node_b.expose(name="robot.move", capability="robot.move")
    async def move():
        nonlocal calls
        calls += 1
        return "moved"

    outcome = await _deliver(
        node_b,
        credential=credential,
        params={
            "operation": "robot.move",
            "request_id": "accept-denied",
        },
    )

    assert outcome.status == "failed"
    assert outcome.error is not None
    assert outcome.error["type"] == "CapabilityDenied"
    assert calls == 0


@pytest.mark.asyncio
async def test_two_node_contextual_policy_denial():
    node_a, node_b, engine_b, credential = _nodes()
    engine_b.capabilities.register(Capability(name="robot.move"))
    node_b.grant_remote(node_a.node_id, "robot.move")
    calls = 0

    def deny_restricted(request):
        if request.target_entity_id == "restricted-zone":
            return PolicyResult(
                PolicyDecision.DENY,
                reason="restricted operational zone",
            )
        return PolicyDecision.ALLOW

    engine_b.capabilities.policy.register(deny_restricted, name="zone-policy")

    @node_b.expose(name="robot.move", capability="robot.move")
    async def move():
        nonlocal calls
        calls += 1
        return "moved"

    outcome = await _deliver(
        node_b,
        credential=credential,
        params={
            "operation": "robot.move",
            "request_id": "accept-policy",
            "target_entity_id": "restricted-zone",
        },
    )

    assert outcome.status == "failed"
    assert outcome.error is not None
    assert outcome.error["type"] == "CapabilityDenied"
    assert calls == 0


@pytest.mark.asyncio
async def test_two_node_waiting_duplicate_and_approval_resume_same_execution():
    node_a, node_b, engine_b, credential = _nodes()
    engine_b.capabilities.register(Capability(name="device.reboot"))
    engine_b.capabilities.require_approval("device.reboot")
    node_b.grant_remote(node_a.node_id, "device.reboot")
    calls = 0

    @node_b.expose(name="device.reboot", capability="device.reboot")
    async def reboot():
        nonlocal calls
        calls += 1
        return {"rebooted": True}

    params = {
        "operation": "device.reboot",
        "request_id": "accept-waiting",
    }
    waiting = await _deliver(node_b, credential=credential, params=params)
    duplicate = await _deliver(node_b, credential=credential, params=params)

    assert waiting.status == "waiting"
    assert duplicate.status == "waiting"
    assert duplicate.execution_id == waiting.execution_id
    assert calls == 0
    assert engine_b.get(waiting.execution_id).status is ExecutionStatus.WAITING

    await engine_b.approve(waiting.execution_id, by="operator")
    completed = await _deliver(node_b, credential=credential, params=params)

    assert completed.status == "completed"
    assert completed.execution_id == waiting.execution_id
    assert completed.result == {"rebooted": True}
    assert calls == 1


@pytest.mark.asyncio
async def test_two_node_callable_failure_is_canonical_failed_execution():
    _, node_b, engine_b, credential = _nodes()

    @node_b.expose(name="service.fail")
    async def fail():
        raise RuntimeError("boom")

    outcome = await _deliver(
        node_b,
        credential=credential,
        params={"operation": "service.fail", "request_id": "accept-fail"},
    )

    assert outcome.status == "failed"
    assert outcome.execution_id is not None
    assert engine_b.get(outcome.execution_id).status is ExecutionStatus.FAILED


@pytest.mark.asyncio
async def test_disconnect_then_retry_replays_without_second_compute():
    _, node_b, engine_b, credential = _nodes()
    calls = 0

    @node_b.expose(name="service.once")
    async def once():
        nonlocal calls
        calls += 1
        return calls

    params = {"operation": "service.once", "request_id": "lost-response"}
    lost_response = await _deliver(node_b, credential=credential, params=params)
    retried = await _deliver(node_b, credential=credential, params=params)

    assert retried.execution_id == lost_response.execution_id
    assert retried.result == lost_response.result == 1
    assert calls == 1
    assert len(engine_b.executions) == 1


@pytest.mark.asyncio
async def test_unknown_operation_creates_no_execution():
    _, node_b, engine_b, credential = _nodes()

    outcome = await _deliver(
        node_b,
        credential=credential,
        params={"operation": "missing.operation", "request_id": "unknown"},
    )

    assert outcome.status == "rejected"
    assert outcome.error["type"] == "RemoteOperationNotFound"
    assert engine_b.executions == {}


@pytest.mark.asyncio
async def test_authentication_failure_precedes_protocol_execution():
    _, node_b, engine_b, _ = _nodes()

    with pytest.raises(ParticipantAuthenticationError):
        await _deliver(
            node_b,
            credential="wrong-secret",
            params={"operation": "anything", "request_id": "bad-auth"},
        )

    assert engine_b.executions == {}


def test_malformed_payload_is_rejected_before_runtime():
    with pytest.raises(ValueError, match="arguments"):
        RemoteExecutionRequest.from_jsonrpc(
            {"operation": "robot.inspect", "arguments": ["not", "an", "object"]}
        )
