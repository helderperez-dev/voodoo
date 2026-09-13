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

import asyncio
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
    RemoteAuthorityRegistry,
    RemoteExecutionOutcome,
    RemoteExecutionRequest,
)
from voodoo.mesh.replay import (
    InMemoryRemoteReplayStore,
    RemoteReplayStore,
    request_fingerprint,
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
        remote_authority: RemoteAuthorityRegistry | None = None,
        replay_store: RemoteReplayStore | None = None,
    ):
        if bus is None:
            from voodoo.adapters.registry import registry

            self.bus = registry.get_events()
        else:
            self.bus = bus
        self.execution_engine = execution_engine
        self.remote_authority = remote_authority or RemoteAuthorityRegistry()
        self.replay_store = replay_store or InMemoryRemoteReplayStore()
        self._remote_request_locks: dict[str, asyncio.Lock] = {}
        self.node_id = str(uuid.uuid4())
        self.peers: set[str] = set()
        self.active_agents: dict[str, Any] = {}
        self.exposed_functions: dict[str, Callable] = {}
        self.exposed_operations: dict[str, ExposedOperation] = {}
        self.event_handlers: dict[str, list[Callable]] = {}
        self.active_nodes: list[WebSocket] = []
        self.subscriptions: set[str] = set()

    def grant_remote(self, actor: str, *capabilities: Any) -> None:
        """Assign remote authority on the receiving node."""
        self.remote_authority.grant(actor, *capabilities)

    def revoke_remote(self, actor: str, *capability_names: str) -> None:
        """Revoke server-side authority from one remote participant."""
        self.remote_authority.revoke(actor, *capability_names)

    def expose(
        self,
        name: str | None = None,
        *,
        capability: str | None = None,
        intent_name: str | None = None,
    ):
        """Expose a function to Mesh and MCP with runtime operation metadata."""

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
            mcp.tool(name=func_name, description=func.__doc__)(func)
            return func

        return decorator

    def on(self, event: str):
        """Decorator to register a handler for a Mesh event."""
        _validate_namespace(event)

        def decorator(func: Callable):
            if event not in self.event_handlers:
                self.event_handlers[event] = []
            self.event_handlers[event].append(func)
            return func

        return decorator

    async def broadcast(self, event: str, payload: Any):
        """Broadcast an event to all connected Mesh nodes and local handlers."""
        _validate_namespace(event)

        envelope = _make_envelope(event, payload)
        message = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "event",
                "params": envelope,
            }
        )

        for node in self.active_nodes:
            try:
                await node.send_text(message)
            except Exception:  # noqa: BLE001
                pass

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
        """Fire local handlers for an event (no remote fan-out)."""
        if event not in self.event_handlers:
            return

        from voodoo.primitives.intent import Intent
        from voodoo.runtime.context import current_context

        parent = current_context()
        engine = (
            parent.engine if parent is not None else None
        ) or self._runtime_engine()
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

    def _replayed_outcome(
        self, request: RemoteExecutionRequest
    ) -> RemoteExecutionOutcome | None:
        record = self.replay_store.get(request.request_id)
        if record is None:
            return None
        if record.fingerprint != request_fingerprint(request):
            return RemoteExecutionOutcome.rejected(
                request,
                error_type="RemoteReplayConflict",
                message="request_id was already used for a different remote request",
            )

        outcome = record.outcome.model_copy(deep=True)
        if outcome.execution_id is None:
            return outcome

        # Replay storage remembers request identity. Canonical Execution remains
        # authoritative for lifecycle changes after WAITING/HITL resume.
        execution = self._runtime_engine().get(outcome.execution_id)
        if execution is None or execution.status.value == outcome.status:
            return outcome

        error = None
        if execution.failed:
            error = {
                "type": "ExecutionFailed",
                "message": execution.error or "execution failed",
            }
        refreshed = RemoteExecutionOutcome.from_execution(
            request,
            execution,
            error=error,
        )
        self.replay_store.save(request, refreshed)
        return refreshed

    async def execute_remote(
        self, request: RemoteExecutionRequest
    ) -> RemoteExecutionOutcome:
        """Execute one request once and replay its canonical outcome on duplicates."""
        lock = self._remote_request_locks.setdefault(request.request_id, asyncio.Lock())
        async with lock:
            replayed = self._replayed_outcome(request)
            if replayed is not None:
                return replayed

            outcome = await self._execute_remote_once(request)
            if outcome.execution_id is not None:
                self.replay_store.save(request, outcome)
            return outcome

    async def _execute_remote_once(
        self, request: RemoteExecutionRequest
    ) -> RemoteExecutionOutcome:
        operation = self.exposed_operations.get(request.operation)
        if operation is None:
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
        granted_capabilities = self.remote_authority.names_for(request.actor)

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
                capabilities=granted_capabilities,
            )
            return RemoteExecutionOutcome.from_execution(request, execution)
        except Exception as error:
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
        """Send both structured Runtime truth and the legacy RPC projection."""
        if message_id is None:
            return

        response: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": message_id,
            "voodoo": outcome.transport_metadata(),
            "outcome": outcome.model_dump(mode="json"),
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
                    except Exception as error:
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
    "RemoteAuthorityRegistry",
    "ExposedOperation",
]
