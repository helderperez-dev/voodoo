"""Sprint 26.3 — remote authority is server-side and policy-equivalent."""

from __future__ import annotations

import pytest

from voodoo.mesh import MeshNetwork, RemoteExecutionRequest
from voodoo.primitives.capability import Capability
from voodoo.runtime import ExecutionEngine
from voodoo.runtime.execution import ExecutionStatus
from voodoo.runtime.policy import PolicyDecision, PolicyResult


def _request(operation: str, *, actor: str = "device-a", **kwargs):
    return RemoteExecutionRequest(
        operation=operation,
        actor=actor,
        arguments=kwargs,
        target_entity_id="robot-01",
    )


@pytest.mark.asyncio
async def test_global_registration_is_not_ambient_remote_authority():
    engine = ExecutionEngine()
    engine.capabilities.register(Capability(name="robot.move"))
    net = MeshNetwork(execution_engine=engine)
    called = False

    @net.expose(capability="robot.move")
    async def move(distance: int):
        nonlocal called
        called = True
        return distance

    outcome = await net.execute_remote(_request("move", distance=3))

    assert outcome.status == "failed"
    assert outcome.error is not None
    assert outcome.error["type"] == "CapabilityDenied"
    assert called is False
    execution = engine.get(outcome.execution_id)
    assert execution is not None
    assert execution.status is ExecutionStatus.FAILED
    assert execution.actor == "remote:device-a"


@pytest.mark.asyncio
async def test_server_side_grant_allows_remote_operation():
    engine = ExecutionEngine()
    engine.capabilities.register(Capability(name="robot.move"))
    net = MeshNetwork(execution_engine=engine)
    net.grant_remote("device-a", "robot.move")

    @net.expose(capability="robot.move")
    async def move(distance: int):
        return {"moved": distance}

    outcome = await net.execute_remote(_request("move", distance=4))

    assert outcome.status == "completed"
    assert outcome.result == {"moved": 4}
    execution = engine.get(outcome.execution_id)
    assert execution is not None
    assert execution.capabilities == ["robot.move"]
    assert execution.actor == "remote:device-a"


@pytest.mark.asyncio
async def test_network_payload_cannot_self_authorize():
    engine = ExecutionEngine()
    engine.capabilities.register(Capability(name="robot.move"))
    net = MeshNetwork(execution_engine=engine)
    called = False

    @net.expose(capability="robot.move")
    async def move():
        nonlocal called
        called = True
        return "moved"

    request = RemoteExecutionRequest.from_jsonrpc(
        {
            "operation": "move",
            "actor": "device-a",
            "capabilities": ["robot.move"],
            "arguments": {},
        }
    )
    outcome = await net.execute_remote(request)

    assert outcome.status == "failed"
    assert called is False
    assert net.remote_authority.names_for("device-a") == []


@pytest.mark.asyncio
async def test_remote_grant_can_be_revoked_immediately():
    engine = ExecutionEngine()
    engine.capabilities.register(Capability(name="robot.move"))
    net = MeshNetwork(execution_engine=engine)
    net.grant_remote("device-a", "robot.move")

    @net.expose(capability="robot.move")
    async def move():
        return "ok"

    allowed = await net.execute_remote(_request("move"))
    assert allowed.status == "completed"

    net.revoke_remote("device-a", "robot.move")
    denied = await net.execute_remote(_request("move"))
    assert denied.status == "failed"
    assert denied.error is not None
    assert denied.error["type"] == "CapabilityDenied"


@pytest.mark.asyncio
async def test_policy_still_narrows_server_side_remote_grant():
    engine = ExecutionEngine()
    engine.capabilities.register(Capability(name="robot.move"))
    observed = {}

    def deny_restricted_target(request):
        observed["actor"] = request.actor
        observed["target"] = request.target_entity_id
        if request.target_entity_id == "robot-01":
            return PolicyResult(
                PolicyDecision.DENY,
                reason="robot is in a restricted operating state",
            )
        return PolicyDecision.ALLOW

    engine.capabilities.policy.register(deny_restricted_target, name="restricted-robot")
    net = MeshNetwork(execution_engine=engine)
    net.grant_remote("device-a", "robot.move")
    called = False

    @net.expose(capability="robot.move")
    async def move():
        nonlocal called
        called = True
        return "ok"

    outcome = await net.execute_remote(_request("move"))

    assert outcome.status == "failed"
    assert outcome.error is not None
    assert outcome.error["type"] == "CapabilityDenied"
    assert "restricted operating state" in outcome.error["message"]
    assert observed == {"actor": "remote:device-a", "target": "robot-01"}
    assert called is False


def test_remote_authority_registry_normalizes_actor_namespace():
    net = MeshNetwork(execution_engine=ExecutionEngine())
    net.grant_remote("device-a", "robot.read")
    net.grant_remote("remote:device-a", "robot.move")

    assert net.remote_authority.names_for("device-a") == ["robot.move", "robot.read"]
    assert net.remote_authority.names_for("remote:device-a") == [
        "robot.move",
        "robot.read",
    ]
