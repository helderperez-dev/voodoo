"""Mesh Network — local-first event bus with governed remote execution.

Mesh is the single realtime channel for the framework. Local events fire
immediately on registered handlers; remote events are serialized over
WebSocket connections using a JSON-RPC 2.0 envelope.

The boundary between local and remote is explicit:

* **Local events** fire on in-process handlers immediately (zero serialization).
  Use ``emit()`` / ``on()`` for subsystem coupling. Handlers still enter the
  canonical :class:`~voodoo.runtime.engine.ExecutionEngine`.
* **Remote events** are serialized as JSON and sent to connected WebSocket
  nodes. They carry an envelope (id, ts, source, correlation_id).
* **Remote calls** are normalized into a semantic request and then enter the
  same ExecutionEngine used by local runtime work. Transport connectivity is
  never an alternate execution lifecycle.

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
from voodoo.mesh.remote import (
    ExposedOperation,
    RemoteExecutionOutcome,
    RemoteExecutionRequest,
)
from voodoo.storage.events import VoodooEventBus


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
    """Local-first event router plus governed distributed execution ingress."""

    def __init__(
        self,
        bus: VoodooEventBus | None = None,
        *,
        execution_engine: Any | None = None,
    ):
        if bus is None:
            from voodoo.adapters.registry import registry

            self.bus = registry.get_events()
        else:
            self.bus = bus
        self.execution_engine = execution_engine
        self.node_id = str(uuid.uuid4())
        self.peers: set[str] = set()
        self.active_agents: dict[str, Any] = {}
        # Compatibility registry: callers may still inspect the raw callable.
        self.exposed_functions: dict[str, Callable] = {}
        # Canonical semantic registration used by remote execution ingress.
        self.exposed_operations: dict[str, ExposedOperation] = {}
        self.event_handlers: dict[str, list[Callable]] = {}
        self.active_nodes: list[WebSocket] = []
        self.subscriptions: set[str] = set()

    def expose(
        self,
        name: str | None = None,
        *,
        capability: str | None = None,
        intent_name: str | None = None,
    ):
        """Expose a function to Mesh and MCP with runtime operation metadata.

        Existing ``@mesh.expose()`` and ``@mesh.expose(name="...")`` usage
        remains compatible. ``capability`` declares an Intent requirement; the
        existing ExecutionEngine capability/policy boundary decides whether it
        may run.

        Sprint 26.1/26.2 normalizes asserted remote actor identity but does not
        yet claim transport authentication. Authentication/session resolution
        is a later Sprint 26 slice.
        """

        def decorator(func: Callable):
            func_name = name or func.__name__
            self.exposed_functions[func_name] = func
            self.exposed_operations[func_name] = ExposedOperation(
                name=func_name,
                func=func,
                capability=capability,
                intent_name=intent_name,
                description=func.__doc__,
            )

            # Preserve the existing MCP bridge. Mesh remote calls themselves
            # no longer invoke this callable directly.
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

    def _runtime_engine(self):
        if self.execution_engine is not None:
            return self.execution_engine
        from voodoo.runtime.engine import engine as runtime_engine

        return runtime_engine

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

        parent = current_context()
        # Run on the engine that owns the current execution (when inside one),
        # otherwise use the explicitly injected engine or global Runtime.
        engine = (parent.engine if parent is not None else None) or self._runtime_engine()
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

    async def execute_remote(
        self, request: RemoteExecutionRequest
    ) -> RemoteExecutionOutcome:
        """Execute one normalized remote request through the canonical Runtime.

        Unknown operations are rejected before an Execution is created.
        Application failures remain canonical failed Executions and their
        execution/trace identity is projected back to the caller.
        """
        operation = self.exposed_operations.get(request.operation)
        if operation is None:
            # Compatibility for callers that populated exposed_functions
            # directly before Sprint 26 operation metadata existed.
            func = self.exposed_functions.get(request.operation)
            if func is not None:
                operation = ExposedOperation(name=request.operation, func=func)

        if operation is None:
            return RemoteExecutionOutcome.rejected(
                request,
                error_type="RemoteOperationNotFound",
                message=f"Function not found in Mesh: {request.operation}",
            )

        engine = self._runtime_engine()
        intent = operation.intent_for(request)

        async def compute(ctx):
            result = operation.func(**request.arguments)
            if inspect.isawaitable(result):
                return await result
            return result

        try:
            execution = await engine.execute(
                intent,
                compute,
                actor=request.runtime_actor,
            )
            return RemoteExecutionOutcome.from_execution(request, execution)
        except Exception as error:  # Runtime errors carry canonical lineage.
            from voodoo.runtime.errors import ExecutionError

            execution = None
            structured_error: dict[str, Any]
            if isinstance(error, ExecutionError):
                structured_error = error.describe()
                if error.execution_id is not None:
                    execution = engine.get(error.execution_id)
            else:
                structured_error = {
                    "type": type(error).__name__,
                    "message": str(error),
                }

            if execution is not None:
                return RemoteExecutionOutcome.from_execution(
                    request,
                    execution,
                    error=structured_error,
                )
            return RemoteExecutionOutcome.rejected(
                request,
                error_type=structured_error.get("type", "RemoteExecutionError"),
                message=structured_error.get("message", str(error)),
            )

    async def connect(self, endpoint_url: str):
        """Connect to another Mesh Node."""
        return MeshClient(endpoint_url)

    async def _send_remote_outcome(
        self,
        websocket: WebSocket,
        *,
        message_id: Any,
        outcome: RemoteExecutionOutcome,
    ) -> None:
        """Project a governed outcome onto the legacy JSON-RPC wire contract.

        ``MeshClient.call()`` historically returns the raw application result,
        so completed calls keep that behavior. Canonical Voodoo execution
        identity is attached as an additive ``voodoo`` metadata member. Sprint
        26.5 can evolve the client-facing lifecycle contract without breaking
        this compatibility path.
        """
        if message_id is None:
            return

        response: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": message_id,
            "voodoo": outcome.transport_metadata(),
        }
        if outcome.status == "completed":
            response["result"] = outcome.result
        else:
            error = outcome.error or {
                "type": "RemoteExecutionError",
                "message": f"Remote execution ended with status {outcome.status}",
            }
            response["error"] = error.get("message", str(error))
        await websocket.send_text(json.dumps(response, default=str))

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
                    try:
                        request = RemoteExecutionRequest.from_jsonrpc(
                            params,
                            message_id=str(msg_id) if msg_id is not None else None,
                        )
                    except Exception as error:  # validation/protocol failure
                        if msg_id is not None:
                            await websocket.send_text(
                                json.dumps(
                                    {
                                        "jsonrpc": "2.0",
                                        "id": msg_id,
                                        "error": str(error),
                                    }
                                )
                            )
                        continue

                    outcome = await self.execute_remote(request)
                    await self._send_remote_outcome(
                        websocket,
                        message_id=msg_id,
                        outcome=outcome,
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

__all__ = [
    "MeshNetwork",
    "mesh",
    "RemoteExecutionRequest",
    "RemoteExecutionOutcome",
    "ExposedOperation",
]
