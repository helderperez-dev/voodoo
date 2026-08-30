"""Edge device simulator — protocol-faithful test client (EDGE §41).

Simulates an external device (the future ESP32 reference client) speaking
``voodoo-edge/v1`` over HTTP or MQTT. It NEVER bypasses the Edge Protocol
by calling internal runtime APIs — everything goes through the transports,
which is exactly what makes it valuable as an integration test harness.

    from voodoo.edge.simulator import DeviceSimulator, HTTPSimulatorTransport

    sim = DeviceSimulator(HTTPSimulatorTransport("http://testserver"))
    await sim.enroll(enrollment_key)
    await sim.connect()
    await sim.send_event("temperature.changed", {"value": 31.4})
    effects = await sim.fetch_effects()
    await sim.ack_effect(effect["effect_id"], "completed")
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any
from uuid import uuid4

import httpx

from voodoo.edge.protocol import (
    PROTOCOL_VERSION,
    EdgeMessageType,
    make_message,
)

__all__ = [
    "SimulatorTransport",
    "HTTPSimulatorTransport",
    "DeviceSimulator",
]


def _mid() -> str:
    return f"msg_{uuid4().hex[:20]}"


# ---------------------------------------------------------------------------
# Transport seam — the simulator only speaks Edge Protocol
# ---------------------------------------------------------------------------


class SimulatorTransport(ABC):
    """Abstract transport the simulator uses — mirrors a real device."""

    @abstractmethod
    async def enroll(
        self, enrollment_key: str, firmware_version: str | None = None
    ) -> dict[str, Any]:
        """Consume enrollment → {device_id, credential, ...}."""

    @abstractmethod
    async def send(
        self, message_type: str, payload: dict[str, Any], *, session_id: str = ""
    ) -> dict[str, Any]:
        """Send a message, return the response payload dict."""

    @abstractmethod
    async def fetch_effects(self) -> list[dict[str, Any]]:
        """Fetch pending effects (HTTP polling path)."""


class HTTPSimulatorTransport(SimulatorTransport):
    """Speaks the Edge HTTP API — trivially testable with TestClient.

    ``app`` (optional ASGI app) enables fully in-process testing: the
    simulator talks to the app over ASGI without opening sockets.
    """

    def __init__(self, base_url: str = "http://testserver", app: Any = None) -> None:
        self._base = base_url.rstrip("/")
        self._app = app
        self._credential: str | None = None

    def _client(self) -> httpx.AsyncClient:
        if self._app is not None:
            transport = httpx.ASGITransport(app=self._app)  # type: ignore[arg-type]
            return httpx.AsyncClient(transport=transport, base_url=self._base)
        return httpx.AsyncClient(base_url=self._base)

    def set_credential(self, credential: str) -> None:
        self._credential = credential

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._credential:
            headers["X-Device-Credential"] = self._credential
        return headers

    async def enroll(
        self, enrollment_key: str, firmware_version: str | None = None
    ) -> dict[str, Any]:
        async with self._client() as client:
            resp = await client.post(
                "/v1/edge/enroll",
                json={
                    "enrollment_key": enrollment_key,
                    "firmware_version": firmware_version,
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def send(
        self, message_type: str, payload: dict[str, Any], *, session_id: str = ""
    ) -> dict[str, Any]:
        route = {
            "hello": "/v1/edge/hello",
            "event": "/v1/edge/events",
            "state_sync": "/v1/edge/state",
            "heartbeat": "/v1/edge/heartbeat",
            "auth": "/v1/edge/auth",
        }.get(message_type)
        if route is None:
            raise ValueError(f"No HTTP route for message type '{message_type}'")
        async with self._client() as client:
            resp = await client.post(route, json=payload, headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    async def fetch_effects(self) -> list[dict[str, Any]]:
        async with self._client() as client:
            resp = await client.get("/v1/edge/effects", headers=self._headers())
            resp.raise_for_status()
            return resp.json().get("effects", [])


class MQTTSimulatorTransport(SimulatorTransport):
    """Speaks the Edge MQTT topics — used with a live broker in dev."""

    def __init__(
        self, device_id: str, *, broker: str = "localhost", port: int = 1883
    ) -> None:
        self.device_id = device_id
        self._broker = broker
        self._port = port
        self._credential: str | None = None
        self._client: Any | None = None
        self._effects: list[dict[str, Any]] = []

    def set_credential(self, credential: str) -> None:
        self._credential = credential

    async def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        import paho.mqtt.client as mqtt

        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"sim-{self.device_id}",
        )
        client.on_message = self._on_message
        client.connect(self._broker, self._port)
        client.loop_start()
        self._client = client
        import time

        time.sleep(0.2)  # allow CONNACK + SUBACK
        client.subscribe(f"voodoo/v1/devices/{self.device_id}/effects", qos=1)
        return client

    def _on_message(self, client: Any, userdata: Any, msg: Any) -> None:
        try:
            envelope = json.loads(msg.payload)
            self._effects.append(envelope.get("payload", {}))
        except json.JSONDecodeError:
            pass

    async def enroll(
        self, enrollment_key: str, firmware_version: str | None = None
    ) -> dict[str, Any]:
        raise NotImplementedError(
            "Enrollment runs over HTTP; MQTT devices enroll via HTTP then "
            "authenticate over MQTT (EDGE §34/§35)."
        )

    async def send(
        self, message_type: str, payload: dict[str, Any], *, session_id: str = ""
    ) -> dict[str, Any]:
        client = await self._ensure_client()
        if message_type == "auth":
            payload = {"credential": self._credential or "", **payload}
        kind = {
            "auth": "auth",
            "hello": "events",  # HELLO rides the events topic pre-session
            "event": "events",
            "state_sync": "state",
            "heartbeat": "heartbeat",
        }.get(message_type)
        if kind is None:
            raise ValueError(f"No MQTT topic for message type '{message_type}'")
        body = dict(payload)
        if session_id:
            body["session_id"] = session_id
        envelope = make_message(
            EdgeMessageType(message_type), device_id=self.device_id, payload=body
        )
        info = client.publish(
            f"voodoo/v1/devices/{self.device_id}/{kind}",
            envelope.model_dump_json(),
            qos=1,
        )
        if info.rc != 0:
            raise RuntimeError(f"MQTT publish failed rc={info.rc}")
        return {"published": True}

    async def fetch_effects(self) -> list[dict[str, Any]]:
        await self._ensure_client()
        out = self._effects
        self._effects = []
        return out


# ---------------------------------------------------------------------------
# Simulator — a virtual device lifecycle (EDGE §41)
# ---------------------------------------------------------------------------


class DeviceSimulator:
    """A virtual external device exercising the full Edge Protocol.

    The simulator mirrors the intended ESP32 client API (EDGE §57):
    enroll → connect → announce → state → events → effects → ack.
    """

    def __init__(self, transport: SimulatorTransport) -> None:
        self.transport = transport
        self.device_id: str = ""
        self.credential: str = ""
        self.session_id: str = ""
        self.capabilities: list[str] = []
        self.connected: bool = False

    # -- lifecycle ------------------------------------------------------------

    async def enroll(
        self, enrollment_key: str, firmware_version: str | None = None
    ) -> None:
        result = await self.transport.enroll(enrollment_key, firmware_version)
        self.device_id = result["device_id"]
        self.credential = result["credential"]
        if isinstance(self.transport, HTTPSimulatorTransport):
            self.transport.set_credential(self.credential)
        else:
            self.transport.set_credential(self.credential)

    async def connect(
        self, *, device_type: str = "esp32-sim", capabilities: list[str] | None = None
    ) -> None:
        """AUTH + HELLO: authenticate, then announce type/capabilities."""
        if not self.credential:
            raise RuntimeError("Simulator must enroll before connecting")
        response = await self.transport.send(
            "auth",
            {"device_id": self.device_id, "credential": self.credential},
        )
        self.session_id = str(response.get("session_id", ""))
        self.capabilities = list(response.get("capabilities", capabilities or []))
        await self.transport.send(
            "hello",
            {
                "device_id": self.device_id,
                "device_type": device_type,
                "protocol_version": PROTOCOL_VERSION,
                "capabilities": capabilities or self.capabilities,
            },
            session_id=self.session_id,
        )
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False
        self.session_id = ""
        self._last_state_version = getattr(self, "_last_state_version", 0)

    # -- state & events ---------------------------------------------------------

    async def send_state(
        self, state: dict[str, Any], state_version: int
    ) -> dict[str, Any]:
        return await self.transport.send(
            "state_sync",
            {"state": state, "state_version": state_version},
            session_id=self.session_id,
        )

    async def send_event(
        self, event_name: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return await self.transport.send(
            "event",
            {
                "event_name": event_name,
                "event_payload": payload or {},
                "message_id": _mid(),
            },
            session_id=self.session_id,
        )

    async def heartbeat(self) -> dict[str, Any]:
        return await self.transport.send(
            "heartbeat", {"uptime_seconds": 1}, session_id=self.session_id
        )

    # -- effects ------------------------------------------------------------------

    async def fetch_effects(self) -> list[dict[str, Any]]:
        """Poll pending effects (HTTP transport; MQTT pushes instead)."""
        return await self.transport.fetch_effects()

    async def ack_effect(
        self, effect_id: str, status: str = "completed"
    ) -> dict[str, Any]:
        if isinstance(self.transport, HTTPSimulatorTransport):
            return await self._ack_http(effect_id, status)
        return await self.transport.send(
            "effect_ack",
            {"effect_id": effect_id, "status": status},
            session_id=self.session_id,
        )

    async def _ack_http(self, effect_id: str, status: str) -> dict[str, Any]:
        assert isinstance(self.transport, HTTPSimulatorTransport)
        async with self.transport._client() as client:
            resp = await client.post(
                f"/v1/edge/effects/{effect_id}/ack",
                json={"status": status},
                headers={
                    "X-Device-Credential": self.credential,
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            return resp.json()
