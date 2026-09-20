"""Sprint 28.13-28.17 acceptance for the governed node fabric."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from voodoo.runtime.fabric import (
    FabricRoutingError,
    FabricWork,
    NoEligibleNodeError,
    PlacementRequirement,
    RuntimeFabric,
    WorkNotFailoverSafeError,
)
from voodoo.runtime.identity import (
    AuthenticationEvidence,
    Identity,
    IdentityKind,
    Principal,
)
from voodoo.runtime.membership import NodeAdvertisement, VoodooStoreMembershipStore
from voodoo.runtime.store import RuntimeStore, StoreConfig, bind_active_runtime_store


@pytest.fixture
def runtime_store(tmp_path):
    runtime = RuntimeStore(StoreConfig(path=tmp_path / "fabric.vstore"))
    runtime.start()
    bind_active_runtime_store(runtime)
    try:
        yield runtime
    finally:
        bind_active_runtime_store(None)
        runtime.stop()


def node_principal(node_id: str) -> Principal:
    return Principal(
        Identity(id=node_id, kind=IdentityKind.NODE),
        evidence=(AuthenticationEvidence(method="mesh", subject=node_id),),
    )


def join(
    store: VoodooStoreMembershipStore,
    node_id: str,
    *,
    capabilities=(),
    services=(),
    ownership=(),
    location=None,
    load=0.0,
):
    return store.join(
        node_principal(node_id),
        NodeAdvertisement(
            capabilities=tuple(capabilities),
            services=tuple(services),
            store_ownership=tuple(ownership),
            location=location,
            resources={"load": load},
        ),
    )


def test_placement_uses_capability_ownership_locality_and_load(runtime_store) -> None:
    memberships = VoodooStoreMembershipStore(runtime_store)
    join(
        memberships,
        "node-a",
        capabilities=("vision",),
        services=("inference",),
        location="lab-a",
        load=0.8,
    )
    join(
        memberships,
        "node-b",
        capabilities=("vision",),
        services=("inference",),
        ownership=("images",),
        location="lab-a",
        load=0.3,
    )
    join(
        memberships,
        "node-c",
        capabilities=("vision",),
        services=("inference",),
        location="lab-b",
        load=0.0,
    )

    fabric = RuntimeFabric(memberships, runtime_store=runtime_store)
    decision = fabric.place(
        PlacementRequirement(
            capability="vision",
            service="inference",
            owner="images",
            location="lab-a",
        )
    )

    assert decision.node_id == "node-b"
    assert "data-owner" in decision.reasons
    assert "locality" in decision.reasons


def test_discovery_never_treats_advertisement_as_authority(runtime_store) -> None:
    memberships = VoodooStoreMembershipStore(runtime_store)
    member = join(memberships, "node-a", capabilities=("payments.execute",))

    assert member.advertisement.capabilities == ("payments.execute",)
    assert node_principal("node-a").claims == {}


def test_health_sweep_excludes_stale_node_from_routing(runtime_store) -> None:
    memberships = VoodooStoreMembershipStore(runtime_store)
    member = join(memberships, "node-a", capabilities=("gpu",))
    fabric = RuntimeFabric(memberships, runtime_store=runtime_store)

    changed = fabric.sweep_health(
        suspect_after_seconds=10,
        now=member.last_seen_at + timedelta(seconds=11),
    )

    assert changed == ["node-a"]
    with pytest.raises(NoEligibleNodeError):
        fabric.place(PlacementRequirement(capability="gpu"))


def test_fabric_lease_is_durable_and_generation_increases(runtime_store) -> None:
    memberships = VoodooStoreMembershipStore(runtime_store)
    join(memberships, "node-a")
    fabric = RuntimeFabric(memberships, runtime_store=runtime_store)
    now = datetime(2026, 9, 14, tzinfo=UTC)

    first = fabric.acquire_lease("work-1", "node-a", now=now)
    second = fabric.acquire_lease("work-1", "node-a", now=now + timedelta(seconds=1))

    assert first.generation == 1
    assert second.generation == 2
    assert fabric.get_lease("work-1") == second


@pytest.mark.asyncio
async def test_retryable_work_fails_over_to_second_active_node(runtime_store) -> None:
    memberships = VoodooStoreMembershipStore(runtime_store)
    join(memberships, "node-a", capabilities=("gpu",), load=0.0)
    join(memberships, "node-b", capabilities=("gpu",), load=0.5)
    fabric = RuntimeFabric(memberships, runtime_store=runtime_store)
    attempts = []

    class Executor:
        async def execute(self, node_id, work, *, attempt):
            attempts.append((node_id, work.idempotency_key, attempt))
            if node_id == "node-a":
                raise ConnectionError("node-a unavailable")
            return {"node": node_id, "ok": True}

    work = FabricWork(
        id="work-failover",
        idempotency_key="stable-key",
        operation="model.run",
        requirement=PlacementRequirement(capability="gpu"),
        max_attempts=2,
    )
    result = await fabric.execute(work, Executor())

    assert result == {"node": "node-b", "ok": True}
    assert attempts == [
        ("node-a", "stable-key", 1),
        ("node-b", "stable-key", 2),
    ]
    assert fabric.get_lease(work.id) is None


@pytest.mark.asyncio
async def test_non_retryable_work_never_moves_to_another_node(runtime_store) -> None:
    memberships = VoodooStoreMembershipStore(runtime_store)
    join(memberships, "node-a", capabilities=("robot.arm",), load=0.0)
    join(memberships, "node-b", capabilities=("robot.arm",), load=0.2)
    fabric = RuntimeFabric(memberships, runtime_store=runtime_store)
    called = []

    class Executor:
        async def execute(self, node_id, work, *, attempt):
            called.append(node_id)
            raise TimeoutError("unknown physical effect state")

    work = FabricWork(
        operation="robot.move",
        requirement=PlacementRequirement(capability="robot.arm"),
        retryable=False,
        max_attempts=2,
    )

    with pytest.raises(WorkNotFailoverSafeError):
        await fabric.execute(work, Executor())
    assert called == ["node-a"]


@pytest.mark.asyncio
async def test_bounded_failover_stops_after_declared_attempts(runtime_store) -> None:
    memberships = VoodooStoreMembershipStore(runtime_store)
    for node_id in ("node-a", "node-b", "node-c"):
        join(memberships, node_id, capabilities=("compute",))
    fabric = RuntimeFabric(memberships, runtime_store=runtime_store)
    called = []

    class Executor:
        async def execute(self, node_id, work, *, attempt):
            called.append(node_id)
            raise ConnectionError(node_id)

    work = FabricWork(
        operation="compute.run",
        requirement=PlacementRequirement(capability="compute"),
        max_attempts=2,
    )

    with pytest.raises(FabricRoutingError, match="exhausted 2"):
        await fabric.execute(work, Executor())
    assert len(called) == 2
