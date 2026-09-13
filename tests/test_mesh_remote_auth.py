"""Sprint 26.6 — trusted participant/session authentication seam."""

from __future__ import annotations

import pytest

from voodoo.mesh import MeshNetwork, RemoteExecutionRequest
from voodoo.mesh.auth import (
    InMemoryParticipantResolver,
    ParticipantAuthenticationError,
)
from voodoo.primitives.capability import Capability
from voodoo.runtime import ExecutionEngine


@pytest.mark.asyncio
async def test_resolver_binds_credential_to_immutable_participant_identity():
    resolver = InMemoryParticipantResolver()
    credential = resolver.register("node-a", credential="secret-a")
    net = MeshNetwork(participant_resolver=resolver)

    identity = await net.resolve_participant(
        {"credential": credential, "actor": "impersonated-admin"},
        transport="websocket",
    )

    assert identity is not None
    assert identity.participant_id == "node-a"
    assert identity.runtime_actor == "remote:node-a"

    request = RemoteExecutionRequest(
        request_id="auth-1",
        operation="system.read",
        actor="impersonated-admin",
    )
    bound = net.bind_participant(request, identity)

    assert bound.actor == "node-a"
    assert request.actor == "impersonated-admin"


@pytest.mark.asyncio
async def test_invalid_credential_fails_before_execution_or_authority():
    resolver = InMemoryParticipantResolver()
    resolver.register("node-a", credential="secret-a")
    engine = ExecutionEngine()
    net = MeshNetwork(execution_engine=engine, participant_resolver=resolver)

    with pytest.raises(ParticipantAuthenticationError):
        await net.resolve_participant(
            {"credential": "wrong", "actor": "node-a"},
            transport="websocket",
        )

    assert engine.executions == {}


@pytest.mark.asyncio
async def test_missing_credential_fails_when_resolver_is_configured():
    resolver = InMemoryParticipantResolver()
    net = MeshNetwork(participant_resolver=resolver)

    with pytest.raises(ParticipantAuthenticationError, match="missing"):
        await net.resolve_participant(
            {"actor": "node-a"},
            transport="websocket",
        )


@pytest.mark.asyncio
async def test_authenticated_identity_drives_server_side_authority():
    resolver = InMemoryParticipantResolver()
    credential = resolver.register("node-a", credential="secret-a")
    engine = ExecutionEngine()
    engine.capabilities.register(Capability(name="system.read"))
    net = MeshNetwork(
        execution_engine=engine,
        participant_resolver=resolver,
    )
    net.grant_remote("node-a", "system.read")

    called = 0

    @net.expose(name="system.read", capability="system.read")
    async def read_system():
        nonlocal called
        called += 1
        return "ok"

    identity = await net.resolve_participant(
        {"credential": credential, "actor": "someone-else"},
        transport="websocket",
    )
    request = net.bind_participant(
        RemoteExecutionRequest(
            request_id="auth-authority",
            operation="system.read",
            actor="someone-else",
        ),
        identity,
    )
    outcome = await net.execute_remote(request)

    assert outcome.status == "completed"
    assert outcome.result == "ok"
    assert called == 1
    execution = engine.get(outcome.execution_id)
    assert execution is not None
    assert execution.actor == "remote:node-a"


@pytest.mark.asyncio
async def test_revoke_credential_immediately_prevents_identity_resolution():
    resolver = InMemoryParticipantResolver()
    credential = resolver.register("node-a", credential="secret-a")
    resolver.revoke(credential)
    net = MeshNetwork(participant_resolver=resolver)

    with pytest.raises(ParticipantAuthenticationError, match="invalid"):
        await net.resolve_participant(
            {"credential": credential},
            transport="websocket",
        )


def test_mesh_client_carries_credential_as_transport_evidence():
    from voodoo.mesh.client import MeshClient

    client = MeshClient("ws://example.test", credential="mesh-secret")

    assert client.credential == "mesh-secret"
    assert client._credential_params() == {"credential": "mesh-secret"}
