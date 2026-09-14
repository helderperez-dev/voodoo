"""Sprint 28.9 acceptance for Runtime-native identity semantics."""

from __future__ import annotations

from pathlib import Path

from voodoo.auth.user import AuthUser
from voodoo.primitives.capability import Capability
from voodoo.runtime import (
    AuthenticationEvidence,
    ExecutionContext,
    Identity,
    IdentityKind,
    IdentityStatus,
    PolicyDecision,
    PolicyEngine,
    PolicyResult,
    Principal,
    RuntimeStore,
    StoreConfig,
    VoodooStoreIdentityStore,
)


def _runtime(path: Path) -> RuntimeStore:
    runtime = RuntimeStore(StoreConfig(path=path))
    runtime.start()
    return runtime


def test_identity_store_persists_all_runtime_identity_kinds(tmp_path: Path) -> None:
    path = tmp_path / "application.vstore"
    runtime = _runtime(path)
    store = VoodooStoreIdentityStore(runtime)
    identities = [
        Identity(id="user:1", kind=IdentityKind.USER, display_name="Alice"),
        Identity(id="agent:planner", kind=IdentityKind.AGENT),
        Identity(id="service:billing", kind=IdentityKind.SERVICE),
        Identity(id="device:robot-7", kind=IdentityKind.DEVICE),
        Identity(id="node:jundiai-1", kind=IdentityKind.NODE),
    ]
    for identity in identities:
        store.save(identity)

    assert [item.id for item in store.list()] == [
        "agent:planner",
        "device:robot-7",
        "node:jundiai-1",
        "service:billing",
        "user:1",
    ]
    assert store.get("device:robot-7").kind is IdentityKind.DEVICE
    assert [item.id for item in store.list(kind=IdentityKind.NODE)] == [
        "node:jundiai-1"
    ]
    runtime.stop()

    reopened_runtime = _runtime(path)
    try:
        reopened = VoodooStoreIdentityStore(reopened_runtime)
        assert reopened.get("user:1").display_name == "Alice"
        assert len(reopened.list()) == 5
        assert reopened.delete("service:billing") is True
        assert reopened.delete("service:billing") is False
        assert reopened.get("service:billing") is None
    finally:
        reopened_runtime.stop()


def test_principal_is_identity_plus_authentication_not_authority() -> None:
    principal = Principal(
        identity=Identity(id="agent:planner", kind=IdentityKind.AGENT),
        evidence=(
            AuthenticationEvidence(
                method="token",
                subject="planner",
                issuer="voodoo-test",
            ),
        ),
        claims={"roles": ["admin"], "scopes": ["*"]},
    )
    context = ExecutionContext.for_principal(principal)

    assert principal.authenticated is True
    assert context.actor == "agent:planner"
    assert context.principal is principal
    assert context.capabilities == []
    assert context.has_capability("system.admin") is False

    context.grant(Capability(name="system.inspect"))
    assert context.has_capability("system.inspect") is True
    assert context.has_capability("system.admin") is False


def test_principal_propagates_to_child_and_policy_can_inspect_identity() -> None:
    principal = Principal(
        identity=Identity(id="device:robot-7", kind=IdentityKind.DEVICE),
        evidence=(AuthenticationEvidence(method="mtls", subject="robot-7"),),
    )
    context = ExecutionContext.for_principal(principal)
    child = context.child(actor="agent:navigator")

    assert child.principal is principal
    assert child.actor == "agent:navigator"

    policy = PolicyEngine()

    def devices_need_approval(request):
        if request.principal and request.principal.kind is IdentityKind.DEVICE:
            return PolicyResult(
                PolicyDecision.REQUIRE_APPROVAL,
                reason="device action requires operator approval",
            )
        return PolicyDecision.ABSTAIN

    policy.register(devices_need_approval)
    result = policy.evaluate("motor.move", context=child)
    assert result.decision is PolicyDecision.REQUIRE_APPROVAL


def test_auth_user_projects_to_principal_without_roles_becoming_capabilities() -> None:
    auth_user = AuthUser(
        id=42,
        email="user@example.com",
        username="operator",
        role="admin",
        roles=["admin"],
        scopes=["*"],
        auth_type="token",
        is_authenticated=True,
    )

    principal = auth_user.to_principal()
    assert principal is not None
    assert principal.id == "user:42"
    assert principal.kind is IdentityKind.USER
    assert principal.authenticated is True
    assert principal.claims == {"roles": ["admin"], "scopes": ["*"]}

    context = ExecutionContext.for_principal(principal)
    assert context.capabilities == []
    assert context.has_capability("admin") is False
    assert context.has_capability("*") is False


def test_inactive_identity_cannot_form_authenticated_principal() -> None:
    principal = Principal(
        identity=Identity(
            id="node:retired",
            kind=IdentityKind.NODE,
            status=IdentityStatus.REVOKED,
        ),
        evidence=(AuthenticationEvidence(method="mtls", subject="retired"),),
    )

    assert principal.authenticated is False
