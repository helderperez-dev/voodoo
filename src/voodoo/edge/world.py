"""World-aware Edge convergence helpers.

This module closes the semantic boundary between the Edge protocol and the
World Model without creating a second runtime. ``WorldAwareDeviceGateway``
subclasses the canonical :class:`voodoo.edge.gateway.DeviceGateway` and only
adds evidence projection after the normal authentication/idempotency/execution
path has completed.

Effects remain commands. World state changes only when a device reports state
or explicit observed evidence.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from voodoo.edge.gateway import DeviceGateway
from voodoo.edge.models import AuthenticatedDeviceContext, Device
from voodoo.edge.protocol import EdgeMessage
from voodoo.world import Entity, Observation, WorldModel

__all__ = ["EdgeWorldBridge", "WorldAwareDeviceGateway"]


def _flatten(value: dict[str, Any], prefix: str = "") -> list[tuple[str, Any]]:
    """Flatten nested device state into dotted World property paths."""
    result: list[tuple[str, Any]] = []
    for key, item in value.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(item, dict):
            result.extend(_flatten(item, path))
        else:
            result.append((path, item))
    return result


def _timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class EdgeWorldBridge:
    """Project explicit device evidence into a :class:`WorldModel`.

    The bridge is deliberately evidence-only: it never turns an outbound
    Effect into observed truth. State syncs are device-reported evidence;
    semantic events may carry an explicit ``observations`` list; effect ACKs
    may carry ``observed_state`` when the device actually measured the result.
    """

    def __init__(self, world: WorldModel) -> None:
        self.world = world

    def ensure_device(self, device: Device) -> Entity:
        entity = self.world.entity(device.entity_id)
        if entity is not None:
            return entity
        return self.world.put_entity(
            Entity(
                id=device.entity_id,
                type="device",
                properties={},
                metadata={
                    "device_id": device.device_id,
                    "device_type": device.type,
                    "name": device.name,
                },
            )
        )

    def ingest_state(
        self,
        device: Device,
        message: EdgeMessage,
        state: dict[str, Any],
        *,
        execution_id: str | None = None,
    ) -> list[Observation]:
        """Project a device state report into append-only World observations."""
        self.ensure_device(device)
        observed_at = _timestamp(message.timestamp)
        observations: list[Observation] = []
        for property_path, value in _flatten(state):
            observation = self.world.observe(
                device.entity_id,
                property_path,
                value,
                source=f"edge:{device.device_id}",
                observed_at=observed_at,
                trace_id=message.trace_id,
                execution_id=execution_id,
                observation_id=f"edge:{message.message_id}:state:{property_path}",
                metadata={
                    "message_id": message.message_id,
                    "message_type": message.type.value,
                },
            )
            observations.append(observation)
        return observations

    def ingest_event_observations(
        self,
        device: Device,
        message: EdgeMessage,
        observations: list[dict[str, Any]],
        *,
        execution_id: str | None = None,
    ) -> list[Observation]:
        """Ingest explicit evidence attached to a semantic device event."""
        self.ensure_device(device)
        result: list[Observation] = []
        for index, item in enumerate(observations):
            property_path = str(item.get("property", "")).strip()
            if not property_path or "value" not in item:
                continue
            event_time = _timestamp(item.get("observed_at")) or _timestamp(
                message.timestamp
            )
            confidence = float(item.get("confidence", 1.0))
            result.append(
                self.world.observe(
                    device.entity_id,
                    property_path,
                    item["value"],
                    source=str(item.get("source") or f"edge:{device.device_id}"),
                    confidence=confidence,
                    observed_at=event_time,
                    trace_id=message.trace_id,
                    execution_id=execution_id,
                    observation_id=(
                        f"edge:{message.message_id}:event:{index}:{property_path}"
                    ),
                    metadata={
                        "message_id": message.message_id,
                        "message_type": message.type.value,
                        "event_name": message.payload.get("event_name"),
                    },
                )
            )
        return result


class WorldAwareDeviceGateway(DeviceGateway):
    """Canonical DeviceGateway plus explicit Edge → World evidence projection."""

    def __init__(self, *args: Any, world: WorldModel, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.world = world
        self.world_bridge = EdgeWorldBridge(world)

    async def _device_for_world(self, device_id: str) -> Device | None:
        device = await self.store.get_device(device_id)
        if device is not None:
            self.world_bridge.ensure_device(device)
        return device

    async def handle_hello(
        self, message: EdgeMessage, ctx: AuthenticatedDeviceContext
    ) -> EdgeMessage:
        response = await super().handle_hello(message, ctx)
        await self._device_for_world(ctx.device_id)
        return response

    async def handle_state_sync(
        self, message: EdgeMessage, ctx: AuthenticatedDeviceContext
    ) -> EdgeMessage:
        response = await super().handle_state_sync(message, ctx)
        device = await self._device_for_world(ctx.device_id)
        if device is not None:
            state = dict(response.payload.get("state") or {})
            self.world_bridge.ingest_state(device, message, state)
        return response

    async def handle_event(
        self, message: EdgeMessage, ctx: AuthenticatedDeviceContext
    ) -> EdgeMessage:
        response = await super().handle_event(message, ctx)
        device = await self._device_for_world(ctx.device_id)
        if device is None:
            return response
        event_payload = message.payload.get("event_payload")
        explicit = (
            event_payload.get("observations", [])
            if isinstance(event_payload, dict)
            else []
        )
        if isinstance(explicit, list) and explicit:
            self.world_bridge.ingest_event_observations(
                device,
                message,
                [item for item in explicit if isinstance(item, dict)],
                execution_id=response.payload.get("execution_id"),
            )
        return response

    async def handle_effect_ack(
        self, message: EdgeMessage, ctx: AuthenticatedDeviceContext
    ) -> EdgeMessage:
        response = await super().handle_effect_ack(message, ctx)
        device = await self._device_for_world(ctx.device_id)
        observed_state = message.payload.get("observed_state")
        if device is not None and isinstance(observed_state, dict):
            delivery = await self.store.get_effect_delivery(
                str(message.payload.get("effect_id", ""))
            )
            self.world_bridge.ingest_state(
                device,
                message,
                observed_state,
                execution_id=delivery.execution_id if delivery else None,
            )
        return response
