"""Sprint 26.6 / 28.12 — trusted participant and node identity seam."""

from __future__ import annotations

import pytest

from voodoo.mesh import MeshNetwork, RemoteExecutionRequest
from voodoo.primitives.capability import Capability
from voodoo.runtime import ExecutionEngine, IdentityKind, PolicyDecision
from voodoo.runtime.distributed.auth import (
    InMemoryParticipantResolver,
    ParticipantAuthenticationError,
)


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
async def test_authenticated_node_becomes_runtime_node_principal():
    resolver = InMemoryParticipantResolver()
    credential = resolver.register_node("node-a", credential="node-secret")
    engine = ExecutionEngine()
    engine.capabilities.register(Capability(name="cluster.inspect"))
    seen = {}

    def node_policy(request):
        seen["principal"] = request.principal
        if request.principal is None:
            return PolicyDecision.DENY
        if request.principal.kind is not IdentityKind.NODE:
            return PolicyDecision.DENY
        if not request.principal.authenticated:
            return PolicyDecision.DENY
        return PolicyDecision.ALLOW

    engine.capabilities.policy.register(node_policy)
    net = MeshNetwork(execution_engine=engine, participant_resolver=resolver)
    net.grant_remote("node-a", "cluster.inspect")

    @net.expose(name="cluster.inspect", capability="cluster.inspect")
    async def inspect_cluster():
        return "healthy"

    participant = await net.resolve_participant(
        {"credential": credential, "actor": "forged-node"},
        transport="websocket",
        peer="10.0.0.2",
    )
    assert participant is not None
    principal = participant.to_principal()
    assert principal.kind is IdentityKind.NODE
    assert principal.authenticated is True

    request = net.bind_participant(
        RemoteExecutionRequest(
            request_id="node-principal",
            operation="cluster.inspect",
            actor="forged-node",
        ),
        participant,
    )
    outcome = await net.execute_remote(request, principal=principal)

    assert outcome.status == "completed"
    assert outcome.result == "healthy"
    assert seen["principal"] is principal
    execution = engine.get(outcome.execution_id)
    assert execution is not None
    assert execution.actor == "remote:node-a"
    assert execution.capabilities == ["cluster.inspect"]


@pytest.mark.asyncio
async def test_node_authentication_does_not_grant_capability():
    resolver = InMemoryParticipantResolver()
    credential = resolver.register_node("node-a", credential="node-secret")
    engine = ExecutionEngine()
    engine.capabilities.register(Capability(name="cluster.admin"))
    net = MeshNetwork(execution_engine=engine, participant_resolver=resolver)

    @net.expose(name="cluster.admin", capability="cluster.admin")
    async def cluster_admin():
        return "forbidden"

    participant = await net.resolve_participant(
        {"credential": credential}, transport="websocket"
    )
    assert participant is not None
    request = net.bind_participant(
        RemoteExecutionRequest(
            request_id="node-no-authority",
            operation="cluster.admin",
            actor="fake-admin",
        ),
        participant,
    )
    outcome = await net.execute_remote(request, principal=participant.to_principal())

    assert outcome.status != "completed"


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
