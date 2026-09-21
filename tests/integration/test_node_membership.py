"""Sprint 28.12/28.13 acceptance for authenticated node membership."""

from __future__ import annotations

import pytest

from voodoo.runtime import AuthenticationEvidence, Identity, IdentityKind, Principal
from voodoo.runtime.distributed import (
    MemberStatus,
    NodeAdvertisement,
    VoodooStoreMembershipStore,
)
from voodoo.runtime.store import RuntimeStore, StoreConfig, bind_active_runtime_store


@pytest.fixture
def runtime_store(tmp_path):
    runtime = RuntimeStore(StoreConfig(path=tmp_path / "application.vstore"))
    runtime.start()
    bind_active_runtime_store(runtime)
    try:
        yield runtime
    finally:
        bind_active_runtime_store(None)
        runtime.stop()


def _node(node_id: str = "node-a") -> Principal:
    return Principal(
        identity=Identity(id=node_id, kind=IdentityKind.NODE),
        evidence=(AuthenticationEvidence(method="mesh:test", subject=node_id),),
    )


def test_authenticated_node_join_is_durable(runtime_store) -> None:
    store = VoodooStoreMembershipStore()
    advertisement = NodeAdvertisement(
        runtime_version="3.0-dev",
        capabilities=("compute.gpu",),
        resources={"cpu": 8, "memory_mb": 16384},
        services=("inference",),
        location="lab-a",
        store_ownership=("orders",),
    )

    joined = store.join(_node(), advertisement)

    assert joined.status is MemberStatus.ACTIVE
    assert store.get("node-a") == joined
    assert store.list() == [joined]


def test_advertised_capabilities_are_not_runtime_authority(runtime_store) -> None:
    principal = _node()
    store = VoodooStoreMembershipStore()
    membership = store.join(
        principal,
        NodeAdvertisement(capabilities=("cluster.admin", "payment.execute")),
    )

    assert membership.advertisement.capabilities == (
        "cluster.admin",
        "payment.execute",
    )
    assert principal.claims == {}


def test_heartbeat_updates_health_metadata_without_rejoining(runtime_store) -> None:
    principal = _node()
    store = VoodooStoreMembershipStore()
    joined = store.join(principal, NodeAdvertisement(resources={"load": 0.8}))
    refreshed = store.heartbeat(
        principal,
        NodeAdvertisement(resources={"load": 0.2}, services=("worker",)),
    )

    assert refreshed.joined_at == joined.joined_at
    assert refreshed.last_seen_at >= joined.last_seen_at
    assert refreshed.advertisement.resources == {"load": 0.2}
    assert refreshed.advertisement.services == ("worker",)


def test_membership_suspect_and_leave_lifecycle(runtime_store) -> None:
    principal = _node()
    store = VoodooStoreMembershipStore()
    store.join(principal)

    suspect = store.mark_suspect("node-a")
    assert suspect.status is MemberStatus.SUSPECT

    left = store.leave(principal)
    assert left.status is MemberStatus.LEFT
    assert store.list() == []
    assert store.list(include_left=True) == [left]


def test_membership_survives_store_restart(tmp_path) -> None:
    path = tmp_path / "application.vstore"
    runtime = RuntimeStore(StoreConfig(path=path))
    runtime.start()
    bind_active_runtime_store(runtime)
    VoodooStoreMembershipStore().join(
        _node(), NodeAdvertisement(services=("scheduler",))
    )
    bind_active_runtime_store(None)
    runtime.stop()

    reopened = RuntimeStore(StoreConfig(path=path))
    reopened.start()
    bind_active_runtime_store(reopened)
    try:
        membership = VoodooStoreMembershipStore().get("node-a")
        assert membership is not None
        assert membership.status is MemberStatus.ACTIVE
        assert membership.advertisement.services == ("scheduler",)
    finally:
        bind_active_runtime_store(None)
        reopened.stop()


def test_non_node_or_unauthenticated_principal_cannot_join(runtime_store) -> None:
    store = VoodooStoreMembershipStore()
    user = Principal(
        identity=Identity(id="user:1", kind=IdentityKind.USER),
        evidence=(AuthenticationEvidence(method="test", subject="1"),),
    )
    unauthenticated_node = Principal(
        identity=Identity(id="node-b", kind=IdentityKind.NODE)
    )

    with pytest.raises(PermissionError, match="node identities"):
        store.join(user)
    with pytest.raises(PermissionError, match="authenticated"):
        store.join(unauthenticated_node)
