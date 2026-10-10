from __future__ import annotations

import asyncio

import pytest

from voodoo.edge.errors import TransportError
from voodoo.edge.mqtt import EdgeMQTTTransport


@pytest.mark.asyncio
async def test_mqtt_start_converts_expected_connect_failures(monkeypatch):
    """Broker connection failures become redacted transport errors."""
    import paho.mqtt.client as mqtt

    class FailingClient:
        def __init__(self, **_kwargs):
            pass

        def username_pw_set(self, *_args):
            pass

        def tls_set(self):
            pass

        def connect(self, *_args, **_kwargs):
            raise RuntimeError("password=broker-secret unavailable")

    monkeypatch.setattr(mqtt, "Client", FailingClient)
    transport = object.__new__(EdgeMQTTTransport)
    transport._client_id = "test"
    transport._broker_url = "broker"
    transport._port = 1883
    transport._username = None
    transport._password = None
    transport._tls = False
    transport._keepalive = 60
    transport._qos = 1
    transport._loop = None
    transport._connected = asyncio.Event()
    transport._client = None

    with pytest.raises(TransportError, match=r"password=\[REDACTED\]"):
        await transport.start()
