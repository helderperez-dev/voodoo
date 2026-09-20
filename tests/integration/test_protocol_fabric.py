"""Sprint 28.17 acceptance for language-neutral node fabric schemas."""

from __future__ import annotations

from voodoo.protocol import (
    FABRIC_SCHEMA_VERSION,
    PROTOCOL_ENTITIES,
    FabricWorkOutcome,
    FabricWorkRequest,
    NodeAdvertisement,
    NodeMembership,
)


def test_fabric_protocol_entities_are_part_of_public_registry() -> None:
    assert FABRIC_SCHEMA_VERSION == 1
    assert PROTOCOL_ENTITIES["NodeAdvertisement"] is NodeAdvertisement
    assert PROTOCOL_ENTITIES["NodeMembership"] is NodeMembership
    assert PROTOCOL_ENTITIES["FabricWorkRequest"] is FabricWorkRequest
    assert PROTOCOL_ENTITIES["FabricWorkOutcome"] is FabricWorkOutcome


def test_fabric_work_request_round_trips_without_runtime_types() -> None:
    request = FabricWorkRequest(
        work_id="work-1",
        idempotency_key="stable-1",
        operation="vision.analyze",
        payload={"image": "scan-1"},
        required_capability="vision",
        attempt=2,
        source_node_id="node-a",
        target_node_id="node-b",
        unknown_transport_hint="ignored",
    )

    restored = FabricWorkRequest.model_validate_json(request.model_dump_json())

    assert restored == request
    assert restored.target_node_id == "node-b"
    assert not hasattr(restored, "unknown_transport_hint")


def test_node_advertisement_is_descriptive_not_authority() -> None:
    advertisement = NodeAdvertisement(
        node_id="node-a",
        capabilities=["payments.refund"],
        resources={"load": 0.2},
    )

    payload = advertisement.model_dump(mode="json")

    assert payload["capabilities"] == ["payments.refund"]
    assert "grants" not in payload
    assert "principal" not in payload
    assert "policy" not in payload
