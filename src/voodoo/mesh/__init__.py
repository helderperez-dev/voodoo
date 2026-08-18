"""Mesh Network — local-first event bus with remote capability.

Mesh is the single realtime channel for the framework. Local events fire
immediately on registered handlers; remote events are serialized over
WebSocket connections using a JSON-RPC 2.0 envelope.

The boundary between local and remote is explicit:

* **Local events** fire on in-process handlers immediately (zero latency,
  no serialization, no auth). Use ``emit()`` / ``on()`` for subsystem coupling.
* **Remote events** are serialized as JSON and sent to connected WebSocket
  nodes. They carry an envelope (id, ts, source, correlation_id) for future
  auth, signing, and replay protection. Use ``expose()`` to register
  functions callable by remote nodes.

All event names must be **namespaced** (e.g. ``"agent.started"`` not
``"started"``). This prevents collisions across subsystems and makes the
event surface discoverable.
"""

import inspect
import json
import time
import uuid
from collections.abc import Callable
from typing import Any

from starlette.websockets import WebSocket, WebSocketDisconnect

from voodoo.mcp import mcp
from voodoo.mesh.client import MeshClient
from voodoo.storage.events import LocalEventBus, VoodooEventBus


def _make_envelope(
    event: str,
    payload: Any,
    *,
    source: str = "voodoo",
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Build a standard event envelope with id, ts, source, correlation_id."""
    if correlation_id is None:
        from voodoo.telemetry import trace_id_var

        correlation_id = trace_id_var.get()
    return {
        "id": str(uuid.uuid4()),
        "ts": time.time(),
        "source": source,
        "correlation_id": correlation_id,
        "event": event,
        "payload": payload,
    }


def _validate_namespace(event: str) -> None:
    """Enforce that event names are namespaced (contain a dot)."""
    if "." not in event:
        raise ValueError(
            f"Mesh event {event!r} must be namespaced (e.g. 'agent.started', not 'started')."
        )


class MeshNetwork:
    def __init__(self, bus: VoodooEventBus | None = None):
        self.bus = bus or LocalEventBus()
        self.exposed_functions: dict[str, Callable] = {}
        self.event_handlers: dict[str, list[Callable]] = {}
        self.active_nodes: list[WebSocket] = []

    def expose(self, name: str | None = None):
        """Decorator to expose a function to the Mesh Network and MCP.

        ``expose`` registers an explicit remote capability. The decorated
        function is callable by connected mesh nodes via JSON-RPC and is
        auto-bridged to MCP for AI IDEs. Permission awareness is captured
        via the ToolRegistry when bridged through MCP.
        """

        def decorator(func: Callable):
            func_name = name or func.__name__
            self.exposed_functions[func_name] = func

            # Auto-bridge to MCP for AI IDEs
            mcp.tool(name=func_name, description=func.__doc__)(func)

            return func

        return decorator

    def on(self, event: str):
        """Decorator to register a handler for a Mesh event.

        Event names must be namespaced (e.g. ``"agent.started"``).
        """
        _validate_namespace(event)

        def decorator(func: Callable):
            if event not in self.event_handlers:
                self.event_handlers[event] = []
            self.event_handlers[event].append(func)
            return func

        return decorator

    async def broadcast(self, event: str, payload: Any):
        """Broadcast an event to all connected Mesh nodes and local handlers.

        Events must be namespaced (e.g. ``"agent.started"``). The event is
        wrapped in a standard envelope with id, ts, source, correlation_id
        before being sent to remote nodes. Local handlers receive the raw
        payload (the envelope is for the remote boundary only).
        """
        _validate_namespace(event)

        envelope = _make_envelope(event, payload)
        message = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "event",
                "params": envelope,
            }
        )

        # Send to all connected nodes (remote boundary)
        for node in self.active_nodes:
            try:
                await node.send_text(message)
            except Exception:  # noqa: BLE001
                pass

        # Also trigger locally via the bus (local boundary)
        self.bus.publish(
            event, payload, source="voodoo", correlation_id=envelope["correlation_id"]
        )
        await self._fire_local(event, payload)

    async def emit(self, event: str, payload: Any):
        """Alias for :meth:`broadcast` — the canonical local event emission."""
        await self.broadcast(event, payload)

    async def _fire_local(self, event: str, payload: Any):
        """Fire local handlers for an event (no remote fan-out).

        Each handler executes through the Voodoo runtime engine as an
        Execution (intent ``mesh:{event}``). When the broadcast happens
        inside another execution, the handler becomes a child execution of
        it (shared trace, ``parent_execution_id`` link).
        """
        if event not in self.event_handlers:
            return

        from voodoo.primitives.intent import Intent
        from voodoo.runtime.context import current_context
        from voodoo.runtime.engine import engine as runtime_engine

        parent = current_context()
        # Run on the engine that owns the current execution (when inside
        # one), otherwise on the global engine.
        engine = (parent.engine if parent is not None else None) or runtime_engine
        for handler in self.event_handlers[event]:
            intent = Intent(name=f"mesh:{event}", params={"payload": payload})

            async def compute(ctx, _handler=handler, _payload=payload):
                if inspect.iscoroutinefunction(_handler):
                    return await _handler(_payload)
                return _handler(_payload)

            try:
                await engine.execute(intent, compute, actor="mesh", parent=parent)
            except Exception as e:  # noqa: BLE001
                print(f"Local mesh event handler error: {e}")

    async def connect(self, endpoint_url: str):
        """Connect to another Mesh Node."""
        return MeshClient(endpoint_url)

    async def _handle_websocket(self, websocket: WebSocket):  # noqa: C901
        """The Starlette WebSocket endpoint for the Mesh Node."""
        await websocket.accept()
        self.active_nodes.append(websocket)
        try:
            while True:
                data = await websocket.receive_text()
                msg = json.loads(data)

                method = msg.get("method")
                params = msg.get("params", {})
                msg_id = msg.get("id")

                if method == "call":
                    func_name = params.get("name")
                    args = params.get("arguments", {})

                    if func_name in self.exposed_functions:
                        func = self.exposed_functions[func_name]
                        try:
                            if inspect.iscoroutinefunction(func):
                                result = await func(**args)
                            else:
                                result = func(**args)

                            if msg_id:
                                await websocket.send_text(
                                    json.dumps(
                                        {
                                            "jsonrpc": "2.0",
                                            "id": msg_id,
                                            "result": result,
                                        }
                                    )
                                )
                        except Exception as e:
                            if msg_id:
                                await websocket.send_text(
                                    json.dumps(
                                        {
                                            "jsonrpc": "2.0",
                                            "id": msg_id,
                                            "error": str(e),
                                        }
                                    )
                                )
                    else:
                        if msg_id:
                            await websocket.send_text(
                                json.dumps(
                                    {
                                        "jsonrpc": "2.0",
                                        "id": msg_id,
                                        "error": "Function not found in Mesh",
                                    }
                                )
                            )

                elif method == "event":
                    # params may be a full envelope or legacy {event, payload}
                    if isinstance(params, dict) and "event" in params:
                        event_name = params.get("event")
                        payload = params.get("payload")
                    else:
                        event_name = None
                        payload = None

                    if event_name:
                        await self._fire_local(event_name, payload)

        except WebSocketDisconnect:
            pass
        except Exception as e:
            print(f"Mesh WS Error: {e}")
        finally:
            if websocket in self.active_nodes:
                self.active_nodes.remove(websocket)


mesh = MeshNetwork()
