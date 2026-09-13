"""Sprint 26.6 — trusted participant/session identity seam."""

from __future__ import annotations

import json

import pytest

from voodoo.mesh import MeshNetwork, RemoteExecutionRequest
from voodoo.mesh.client import MeshClient
from voodoo.mesh.session import InMemoryRemoteSessionRegistry
from voodoo.primitives.capability import Capability
from voodoo.runtime import ExecutionEngine


@pytest.mark.asyncio
async def test_required_trusted_session_rejects_missing_token_before_execution():
    engine = ExecutionEngine()
    sessions = InMemoryRemoteSessionRegistry()
    net = MeshNetwork(
        execution_engine=engine,
        remote_authenticator=sessions,
        require_trusted_remote=True,
    )
    called = False

    @net.expose(name="ping")
    async def ping():
        nonlocal called
        called = True
        return "pong"

    outcome = await net.execute_remote(
        RemoteExecutionRequest(operation="ping", actor="forged")
    )

    assert outcome.status == "rejected"
    assert outcome.error["type"] == "RemoteAuthenticationRequired"
    assert called is False
    assert engine.executions == {}


@pytest.mark.asyncio
async def test_invalid_session_is_rejected_before_execution():
    engine = ExecutionEngine()
    sessions = InMemoryRemoteSessionRegistry()
    net = MeshNetwork(
        execution_engine=engine,
        remote_authenticator=sessions,
        require_trusted_remote=True,
    )

    @net.expose(name="ping")
    async def ping():
        return "pong"

    outcome = await net.execute_remote(
        RemoteExecutionRequest(
            operation="ping",
            actor="forged",
            session_token="vms_invalid",
        )
    )

    assert outcome.status == "rejected"
    assert outcome.error["type"] == "RemoteAuthenticationFailed"
    assert engine.executions == {}


@pytest.mark.asyncio
async def test_authenticated_session_overrides_forged_actor_for_authority():
    engine = ExecutionEngine()
    engine.capabilities.register(Capability(name="robot.move"))
    sessions = InMemoryRemoteSessionRegistry()
    token, principal = sessions.issue("robot-controller")
    net = MeshNetwork(
        execution_engine=engine,
        remote_authenticator=sessions,
        require_trusted_remote=True,
    )
    net.grant_remote("robot-controller", "robot.move")

    @net.expose(name="robot.move", capability="robot.move")
    async def move(distance: int):
        return distance

    outcome = await net.execute_remote(
        RemoteExecutionRequest(
            operation="robot.move",
            arguments={"distance": 5},
            actor="admin-forged",
            session_token=token,
        )
    )

    assert outcome.status == "completed"
    execution = engine.get(outcome.execution_id)
    assert execution.actor == "remote:robot-controller"
    assert execution.capabilities == ["robot.move"]
    assert execution.intent.params["_remote_actor"] == "robot-controller"
    assert execution.intent.params["_remote_metadata"]["_trusted_session_id"] == principal.session_id


@pytest.mark.asyncio
async def test_forged_actor_cannot_borrow_another_participants_grant():
    engine = ExecutionEngine()
    engine.capabilities.register(Capability(name="robot.move"))
    sessions = InMemoryRemoteSessionRegistry()
    token, _ = sessions.issue("observer")
    net = MeshNetwork(
        execution_engine=engine,
        remote_authenticator=sessions,
        require_trusted_remote=True,
    )
    net.grant_remote("admin", "robot.move")
    called = False

    @net.expose(name="robot.move", capability="robot.move")
    async def move():
        nonlocal called
        called = True
        return "ok"

    outcome = await net.execute_remote(
        RemoteExecutionRequest(
            operation="robot.move",
            actor="admin",
            session_token=token,
        )
    )

    assert outcome.status == "failed"
    assert outcome.error["type"] == "CapabilityDenied"
    assert called is False
    assert engine.get(outcome.execution_id).actor == "remote:observer"


@pytest.mark.asyncio
async def test_revoked_and_expired_sessions_are_rejected():
    sessions = InMemoryRemoteSessionRegistry()
    revoked_token, principal = sessions.issue("device-a")
    sessions.revoke(principal.session_id)
    expired_token, _ = sessions.issue("device-b", expires_in_seconds=-1)
    engine = ExecutionEngine()
    net = MeshNetwork(
        execution_engine=engine,
        remote_authenticator=sessions,
        require_trusted_remote=True,
    )

    @net.expose(name="ping")
    async def ping():
        return "pong"

    revoked = await net.execute_remote(
        RemoteExecutionRequest(operation="ping", session_token=revoked_token)
    )
    expired = await net.execute_remote(
        RemoteExecutionRequest(operation="ping", session_token=expired_token)
    )

    assert revoked.status == "rejected"
    assert "revoked" in revoked.error["message"]
    assert expired.status == "rejected"
    assert "expired" in expired.error["message"]
    assert engine.executions == {}


def test_session_token_is_excluded_from_request_serialization():
    request = RemoteExecutionRequest(
        operation="ping",
        session_token="vms_super-secret",
    )
    dumped = request.model_dump(mode="json")
    assert "session_token" not in dumped
    assert "vms_super-secret" not in request.model_dump_json()


@pytest.mark.asyncio
async def test_mesh_client_sends_session_token_without_changing_claimed_actor_api():
    client = MeshClient("ws://unused", session_token="vms_secret")
    sent: list[str] = []

    class Socket:
        closed = False

        async def send(self, data: str):
            sent.append(data)

    client.ws = Socket()
    task = __import__("asyncio").create_task(
        client.execute("ping", actor="display-label", request_id="req-auth")
    )
    while not sent:
        await __import__("asyncio").sleep(0)

    payload = json.loads(sent[0])
    assert payload["params"]["session_token"] == "vms_secret"
    assert payload["params"]["actor"] == "display-label"

    msg_id = payload["id"]
    from voodoo.mesh.remote import RemoteExecutionOutcome

    client._pending_requests[msg_id].set_result(
        RemoteExecutionOutcome(request_id="req-auth", status="completed")
    )
    await task
