"""Sprint 28.10 acceptance for Principal -> Capability -> Policy -> Execution."""

from __future__ import annotations

import pytest

from voodoo.primitives.capability import Capability
from voodoo.primitives.intent import Intent
from voodoo.runtime import (
    AuthenticationEvidence,
    ExecutionContext,
    ExecutionEngine,
    Identity,
    IdentityKind,
    PolicyDecision,
    PolicyResult,
    Principal,
    execute,
)
from voodoo.runtime.errors import CapabilityDenied


def _principal(identity_id: str = "user:42") -> Principal:
    return Principal(
        identity=Identity(id=identity_id, kind=IdentityKind.USER),
        evidence=(AuthenticationEvidence(method="token", subject="42"),),
        claims={"roles": ["admin"], "scopes": ["*"]},
    )


@pytest.mark.asyncio
async def test_principal_enters_top_level_canonical_execution() -> None:
    engine = ExecutionEngine()
    principal = _principal()
    seen: dict[str, object] = {}

    def compute(ctx: ExecutionContext):
        seen["principal"] = ctx.principal
        seen["actor"] = ctx.actor
        seen["capabilities"] = list(ctx.capabilities)
        return "ok"

    execution = await engine.execute(Intent(name="inspect"), compute, principal=principal)

    assert execution.result == "ok"
    assert execution.actor == "user:42"
    assert seen["principal"] is principal
    assert seen["actor"] == "user:42"
    assert seen["capabilities"] == []


@pytest.mark.asyncio
async def test_explicit_actor_override_keeps_authenticated_principal() -> None:
    engine = ExecutionEngine()
    principal = _principal()
    seen: dict[str, object] = {}

    def compute(ctx: ExecutionContext):
        seen["principal"] = ctx.principal
        seen["actor"] = ctx.actor
        return "ok"

    execution = await engine.execute(
        Intent(name="impersonated-operation"),
        compute,
        principal=principal,
        actor="service:gateway",
    )

    assert execution.actor == "service:gateway"
    assert seen == {"principal": principal, "actor": "service:gateway"}


@pytest.mark.asyncio
async def test_principal_claims_do_not_satisfy_required_capability() -> None:
    engine = ExecutionEngine()
    principal = _principal()
    intent = Intent(name="admin-action").require("system.admin")

    with pytest.raises(CapabilityDenied):
        await engine.execute(intent, lambda ctx: "forbidden", principal=principal)

    execution = engine.recent(1)[0]
    assert execution.actor == principal.actor
    assert execution.capabilities == []


@pytest.mark.asyncio
async def test_explicit_capability_and_policy_inspect_same_principal() -> None:
    engine = ExecutionEngine()
    principal = _principal()
    engine.capabilities.register(Capability(name="report.read"))
    seen: dict[str, object] = {}

    def identity_policy(request):
        seen["principal"] = request.principal
        seen["actor"] = request.actor
        if request.principal is None or not request.principal.authenticated:
            return PolicyResult(PolicyDecision.DENY, reason="authentication required")
        return PolicyDecision.ALLOW

    engine.capabilities.policy.register(identity_policy)
    intent = Intent(name="report").require("report.read")
    execution = await engine.execute(intent, lambda ctx: "report", principal=principal)

    assert execution.result == "report"
    assert seen == {"principal": principal, "actor": principal.actor}


@pytest.mark.asyncio
async def test_child_execution_inherits_parent_principal() -> None:
    engine = ExecutionEngine()
    principal = _principal("user:7")
    parent = ExecutionContext.for_principal(principal)
    seen: dict[str, object] = {}

    def child_compute(ctx: ExecutionContext):
        seen["principal"] = ctx.principal
        seen["actor"] = ctx.actor
        seen["parent_execution_id"] = ctx.parent_execution_id
        return "child"

    execution = await engine.execute(
        Intent(name="child"),
        child_compute,
        parent=parent,
    )

    assert execution.parent_execution_id == parent.execution_id
    assert execution.actor == principal.actor
    assert seen["principal"] is principal
    assert seen["actor"] == principal.actor
    assert seen["parent_execution_id"] == parent.execution_id


@pytest.mark.asyncio
async def test_public_runtime_execute_forwards_principal() -> None:
    principal = _principal("user:99")

    execution = await execute(
        Intent(name="public-api-principal"),
        lambda ctx: ctx.principal.id if ctx.principal else None,
        principal=principal,
    )

    assert execution.result == "user:99"
    assert execution.actor == "user:99"
