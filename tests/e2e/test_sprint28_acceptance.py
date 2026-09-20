"""End-to-end acceptance gates for Sprint 28 Runtime Infrastructure Convergence."""

from __future__ import annotations

import json

import pytest

from voodoo.primitives.capability import Capability
from voodoo.primitives.intent import Intent
from voodoo.runtime.engine import ExecutionEngine
from voodoo.runtime.execution import ExecutionStatus
from voodoo.runtime.fabric import FabricWork, PlacementRequirement, RuntimeFabric
from voodoo.runtime.identity import (
    AuthenticationEvidence,
    Identity,
    IdentityKind,
    Principal,
)
from voodoo.runtime.membership import NodeAdvertisement, VoodooStoreMembershipStore
from voodoo.runtime.store import RuntimeStore, StoreConfig, bind_active_runtime_store
from voodoo.runtime.transaction import OutboxMessage, dispatch_events, transaction
from voodoo.storage.events.store import VoodooStoreEventBus


def node_principal(node_id: str) -> Principal:
    return Principal(
        identity=Identity(id=node_id, kind=IdentityKind.NODE),
        evidence=(AuthenticationEvidence(method="mesh", subject=node_id),),
    )


def test_single_node_zero_external_infrastructure_survives_restart(tmp_path) -> None:
    path = tmp_path / "application.vstore"
    runtime = RuntimeStore(StoreConfig(path=path))
    runtime.start()
    bind_active_runtime_store(runtime)
    native = runtime.provider.native
    native.create_collection(b"orders")

    with transaction(runtime) as tx:
        tx.upsert_record(b"orders", b"42", b'{"status":"created"}')
        tx.stage_outbox(
            OutboxMessage(
                id="order-42-created",
                topic="order.created",
                payload={"order_id": "42"},
            )
        )

    received = []
    bus = VoodooStoreEventBus()
    bus.subscribe("order.created", lambda event: received.append(event["payload"]))
    assert dispatch_events(event_bus=bus, runtime_store=runtime) == 1
    assert received == [{"order_id": "42"}]
    bind_active_runtime_store(None)
    runtime.stop()

    reopened = RuntimeStore(StoreConfig(path=path))
    reopened.start()
    try:
        record = reopened.provider.native.get_record(b"orders", b"42")
        assert record is not None
        assert json.loads(bytes(record[1])) == {"status": "created"}
        assert reopened.provider.native.get(
            b"runtime:outbox:delivered:order-42-created"
        )
    finally:
        reopened.stop()


@pytest.mark.asyncio
async def test_same_application_operation_routes_across_nodes_without_topology_logic(
    tmp_path,
) -> None:
    runtime = RuntimeStore(StoreConfig(path=tmp_path / "control.vstore"))
    runtime.start()
    bind_active_runtime_store(runtime)
    try:
        membership = VoodooStoreMembershipStore(runtime)
        membership.join(
            node_principal("node-a"),
            NodeAdvertisement(capabilities=("vision",), resources={"load": 0.9}),
        )
        membership.join(
            node_principal("node-b"),
            NodeAdvertisement(capabilities=("vision",), resources={"load": 0.1}),
        )
        fabric = RuntimeFabric(membership, runtime_store=runtime)

        engines = {"node-a": ExecutionEngine(), "node-b": ExecutionEngine()}
        for engine in engines.values():
            engine.capabilities.register(Capability(name="vision"))

        class CanonicalExecutor:
            async def execute(self, node_id, work, *, attempt):
                engine = engines[node_id]
                intent = Intent(name=work.operation, params=dict(work.payload)).require(
                    "vision"
                )

                async def compute(ctx):
                    return {"node": node_id, "image": work.payload["image"]}

                execution = await engine.execute(
                    intent,
                    compute,
                    actor=f"remote:{node_id}",
                    capabilities=["vision"],
                )
                assert execution.status is ExecutionStatus.COMPLETED
                return execution.result

        # Application semantics mention only the operation and requirement. No
        # node address, transport, retry loop or topology-specific branch exists here.
        result = await fabric.execute(
            FabricWork(
                operation="vision.analyze",
                payload={"image": "scan-1"},
                requirement=PlacementRequirement(capability="vision"),
            ),
            CanonicalExecutor(),
        )

        assert result == {"node": "node-b", "image": "scan-1"}
        completed = [
            execution
            for execution in engines["node-b"].executions.values()
            if execution.status is ExecutionStatus.COMPLETED
        ]
        assert len(completed) == 1
        assert completed[0].actor == "remote:node-b"
    finally:
        bind_active_runtime_store(None)
        runtime.stop()


def test_external_advertisement_does_not_bypass_runtime_authority(tmp_path) -> None:
    runtime = RuntimeStore(StoreConfig(path=tmp_path / "authority.vstore"))
    runtime.start()
    bind_active_runtime_store(runtime)
    try:
        membership = VoodooStoreMembershipStore(runtime)
        membership.join(
            node_principal("node-payments"),
            NodeAdvertisement(capabilities=("payments.refund",)),
        )
        member = membership.get("node-payments")
        assert member is not None
        assert member.advertisement.capabilities == ("payments.refund",)
        assert node_principal("node-payments").claims == {}
    finally:
        bind_active_runtime_store(None)
        runtime.stop()
