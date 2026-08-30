"""Edge MQTT transport — broker-connected Edge Protocol channel (EDGE §35–§38).

Uses paho-mqtt (mature, actively maintained) with its asyncio bridge —
no second event-loop model (EDGE §69). The transport subscribes to the
versioned topic namespace and delegates every message to the shared
DeviceGateway, guaranteeing HTTP/MQTT semantic equivalence (EDGE §36).

QoS 1 (at-least-once) is deliberate: the stable ``message_id`` /
``effect_id`` provide application-level idempotency, which remains
required regardless of QoS (EDGE §37).

The paho-mqtt dependency is optional (``voodoo[edge]`` extra); importing
this module without it raises a clear ImportError.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

from voodoo.edge.errors import TransportError
from voodoo.edge.gateway import DeviceGateway
from voodoo.edge.models import TransportKind
from voodoo.edge.protocol import EdgeMessageType, make_message

if TYPE_CHECKING:
    pass

logger = logging.getLogger("voodoo.edge.mqtt")

__all__ = ["EdgeMQTTTransport", "topic_for"]


# ---------------------------------------------------------------------------
# Topic namespace — voodoo/v1/devices/{device_id}/{inbox} (EDGE §35)
# ---------------------------------------------------------------------------

TOPIC_PREFIX = "voodoo/v1/devices"

# device → runtime
TOPIC_EVENTS = "events"
TOPIC_STATE = "state"
TOPIC_ACK = "ack"
TOPIC_HEARTBEAT = "heartbeat"
TOPIC_AUTH = "auth"

# runtime → device
TOPIC_EFFECTS = "effects"

_INBOX_TOPICS = {
    TOPIC_EVENTS: EdgeMessageType.EVENT,
    TOPIC_STATE: EdgeMessageType.STATE_SYNC,
    TOPIC_ACK: EdgeMessageType.EFFECT_ACK,
    TOPIC_HEARTBEAT: EdgeMessageType.HEARTBEAT,
    TOPIC_AUTH: EdgeMessageType.AUTH,
}


def topic_for(device_id: str, kind: str) -> str:
    """Build a namespaced topic for a device message kind."""
    return f"{TOPIC_PREFIX}/{device_id}/{kind}"


def parse_topic(topic: str) -> tuple[str, str] | None:
    """Split ``voodoo/v1/devices/{device_id}/{kind}`` → (device_id, kind)."""
    parts = topic.split("/")
    if (
        len(parts) != 5
        or parts[0] != "voodoo"
        or parts[1] != "v1"
        or parts[2] != "devices"
    ):
        return None
    return parts[3], parts[4]


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------


class EdgeMQTTTransport:
    """Bridges an MQTT broker to the DeviceGateway.

    Parameters
    ----------
    gateway:
        The shared gateway — identical runtime behavior to HTTP (EDGE §36).
    broker_url:
        Broker host (no scheme), e.g. ``"localhost"``.
    port:
        Broker port (default 1883; 8883 for TLS).
    """

    def __init__(
        self,
        gateway: DeviceGateway,
        *,
        broker_url: str = "localhost",
        port: int = 1883,
        tls: bool = False,
        username: str | None = None,
        password: str | None = None,
        client_id: str = "voodoo-edge-runtime",
        keepalive: int = 60,
        qos: int = 1,
    ) -> None:
        try:
            import paho.mqtt.client as mqtt  # noqa: F401 — availability probe
        except ImportError as e:  # pragma: no cover
            raise ImportError(
                "MQTT transport requires the optional extra "
                "'voodoo-framework[edge]' (paho-mqtt). Install it or use "
                "the HTTP transport."
            ) from e

        self._gateway = gateway
        self._broker_url = broker_url
        self._port = port
        self._tls = tls
        self._username = username
        self._password = password
        self._client_id = client_id
        self._keepalive = keepalive
        self._qos = qos
        self._client: Any | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._connected = asyncio.Event()
        # Per-device subscriptions for outbound effects.
        self._device_queues: dict[str, asyncio.Queue[Any]] = {}

    # -- lifecycle ----------------------------------------------------------

    async def start(self) -> None:
        """Connect to the broker and subscribe to all device inbox topics."""
        import paho.mqtt.client as mqtt

        self._loop = asyncio.get_running_loop()
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=self._client_id,
        )
        if self._username:
            client.username_pw_set(self._username, self._password or "")
        if self._tls:
            client.tls_set()
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.on_disconnect = self._on_disconnect
        self._client = client
        try:
            client.connect(self._broker_url, self._port, keepalive=self._keepalive)
        except Exception as e:  # noqa: BLE001
            raise TransportError(f"MQTT connect failed: {e}") from e
        client.loop_start()  # background network thread
        await asyncio.wait_for(self._connected.wait(), timeout=10.0)

    async def stop(self) -> None:
        """Disconnect cleanly."""
        if self._client is not None:
            self._client.disconnect()
            self._client.loop_stop()
            self._client = None

    @property
    def connected(self) -> bool:
        return self._client is not None and self._connected.is_set()

    # -- outbound: effects to devices ---------------------------------------

    async def publish_effect(self, device_id: str, effect: dict[str, Any]) -> None:
        """Publish an effect message on the device's effects topic."""
        if self._client is None:
            raise TransportError("Transport not started")
        message = make_message(
            EdgeMessageType.EFFECT, device_id=device_id, payload=effect
        )
        topic = topic_for(device_id, TOPIC_EFFECTS)
        info = self._client.publish(topic, message.model_dump_json(), qos=self._qos)
        if info.rc != 0:
            raise TransportError(f"MQTT publish failed (rc={info.rc})")
        delivery = await self._gateway.store.get_effect_delivery(
            str(effect.get("effect_id", ""))
        )
        if delivery is not None:
            await self._gateway.store.mark_effect_delivered(delivery.effect_id)

    # -- paho callbacks (network thread) → asyncio --------------------------

    def _on_connect(
        self, client: Any, userdata: Any, flags: Any, rc: int, props: Any = None
    ) -> None:
        if rc == 0:
            # Subscribe to every device inbox topic via wildcard.
            client.subscribe(f"{TOPIC_PREFIX}/+/+", qos=self._qos)
            if self._loop is not None:
                self._loop.call_soon_threadsafe(self._connected.set)
        else:
            logger.error("MQTT connect rejected rc=%s", rc)

    def _on_disconnect(
        self, client: Any, userdata: Any, flags: Any, rc: int, props: Any = None
    ) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._connected.clear)

    def _on_message(self, client: Any, userdata: Any, msg: Any) -> None:
        if self._loop is None:
            return
        payload = msg.payload.decode("utf-8", errors="replace")
        asyncio.run_coroutine_threadsafe(
            self._handle_inbox(msg.topic, payload), self._loop
        )

    async def _handle_inbox(self, topic: str, payload: str) -> None:
        """Route a decoded inbox message through the shared gateway."""
        parsed = parse_topic(topic)
        if parsed is None:
            logger.warning("Ignoring malformed topic %s", topic)
            return
        device_id, kind = parsed
        expected_type = _INBOX_TOPICS.get(kind)
        if expected_type is None:
            logger.warning("Ignoring unknown topic kind %s", kind)
            return
        try:
            raw = json.loads(payload)
        except json.JSONDecodeError:
            logger.warning("Malformed JSON on %s", topic)
            return
        # Normalize into the canonical envelope typed for the topic kind.
        raw.setdefault("type", expected_type.value)
        raw.setdefault("device_id", device_id)
        try:
            await self._gateway.handle_message(raw, transport=TransportKind.MQTT)
        except Exception as e:  # noqa: BLE001 — broker handler must never crash
            logger.warning("Gateway rejected message on %s: %s", topic, e)
