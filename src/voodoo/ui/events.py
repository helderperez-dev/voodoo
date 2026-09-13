"""Browser event transport and Python-callable interaction bindings.

The public interaction model is Python-first::

    async def save():
        ...

    Button("Save", on_click=save)

Components never need to expose a function name or inline JavaScript. Voodoo
turns callables into opaque binding ids and the client runtime sends those ids
back over the existing WebSocket transport.

The legacy ``@event`` / string-name registry remains available during the
migration window, but first-party components should use :func:`bind_event`.
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from starlette.websockets import WebSocket, WebSocketDisconnect


@dataclass(frozen=True, slots=True)
class UIEvent:
    """Framework-neutral event delivered from the browser to Python.

    Most handlers do not need this object. A zero-argument handler receives no
    transport details; a one-argument handler receives ``value`` by default.
    Annotating the argument as ``UIEvent`` opts into the full event context.
    """

    type: str
    value: Any = None
    element_id: str | None = None
    meta: Mapping[str, Any] = field(default_factory=dict)


class WebSocketManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_patch(self, element_id: str, html: str) -> None:
        message = json.dumps({"type": "patch", "id": element_id, "html": html})
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                self.disconnect(connection)

    async def broadcast_append(self, element_id: str, html: str) -> None:
        message = json.dumps({"type": "append", "id": element_id, "html": html})
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                self.disconnect(connection)


ws_manager = WebSocketManager()

# Legacy public-name registry used by @event and old string-based components.
event_handlers: dict[str, Callable[..., Any]] = {}

# Opaque browser binding -> Python callable. A reverse map keeps the binding
# stable across page rerenders so the rendered DOM does not churn ids.
event_bindings: dict[str, Callable[..., Any]] = {}
_callable_bindings: dict[int, str] = {}


def register_event(name: str, handler: Callable[..., Any]) -> None:
    event_handlers[name] = handler


def bind_event(handler: Callable[..., Any] | str) -> str:
    """Return the browser binding id for *handler*.

    Callables receive an opaque, stable id. Strings are preserved as a legacy
    compatibility path so existing applications keep working while new code can
    pass Python functions directly.
    """

    if isinstance(handler, str):
        return handler
    if not callable(handler):
        raise TypeError("UI event handler must be a callable or legacy event name")

    identity = id(handler)
    binding = _callable_bindings.get(identity)
    if binding is None or event_bindings.get(binding) is not handler:
        binding = f"vdui_{uuid4().hex}"
        _callable_bindings[identity] = binding
        event_bindings[binding] = handler
    return binding


def event(func: Callable[..., Any]) -> Callable[..., Any]:
    """Legacy decorator registering a handler by function name.

    New component code should pass the callable directly (for example
    ``Button(on_click=save)``). The decorator remains intentionally transparent
    for compatibility with existing applications.
    """

    register_event(func.__name__, func)
    return func


async def dispatch_ui_event(
    binding: str,
    *,
    event_type: str,
    element_id: str | None = None,
    value: Any = None,
    meta: Mapping[str, Any] | None = None,
) -> bool:
    """Resolve and invoke one browser event binding.

    Dispatch ergonomics intentionally favor application meaning over transport:

    - ``handler()`` receives nothing;
    - ``handler(value)`` receives the semantic value;
    - ``handler(event: UIEvent)`` receives the complete event;
    - legacy two-argument handlers receive ``(element_id, value)``.

    Returns ``True`` when a handler was found.
    """

    handler = event_bindings.get(binding) or event_handlers.get(binding)
    if handler is None:
        return False

    ui_event = UIEvent(
        type=event_type,
        value=value,
        element_id=element_id,
        meta=dict(meta or {}),
    )
    args = _handler_args(handler, ui_event)
    result = handler(*args)
    if inspect.isawaitable(result):
        await result
    return True


def _handler_args(handler: Callable[..., Any], event_value: UIEvent) -> tuple[Any, ...]:
    """Choose the smallest useful argument surface for a handler."""

    try:
        parameters = list(inspect.signature(handler).parameters.values())
    except (TypeError, ValueError):
        return (event_value.value,)

    positional = [
        parameter
        for parameter in parameters
        if parameter.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    required = [
        parameter
        for parameter in positional
        if parameter.default is inspect.Parameter.empty
    ]

    if not positional and not required:
        return ()

    first = positional[0] if positional else None
    if first is not None and (
        first.annotation is UIEvent
        or first.annotation == "UIEvent"
        or first.name in {"event", "ui_event"}
    ):
        return (event_value,)

    # Preserve the established (element_id, value) contract for handlers that
    # explicitly declare two positional inputs.
    if len(required) >= 2 or len(positional) >= 2:
        return (event_value.element_id, event_value.value)

    return (event_value.value,)


async def websocket_endpoint(websocket: WebSocket) -> None:
    await ws_manager.connect(websocket)
    try:
        while True:
            msg = json.loads(await websocket.receive_text())
            if msg.get("type") != "event":
                continue
            binding = msg.get("binding") or msg.get("event")
            if not binding:
                continue
            await dispatch_ui_event(
                str(binding),
                event_type=str(msg.get("event_type") or "event"),
                element_id=msg.get("id"),
                value=msg.get("value"),
                meta=msg.get("meta") if isinstance(msg.get("meta"), dict) else None,
            )
    except WebSocketDisconnect as exc:
        if getattr(exc, "code", None) not in (1000, 1001):
            print(f"WS Disconnected with code: {getattr(exc, 'code', 'unknown')}")
    except Exception as exc:
        err_str = str(exc)
        if "1000" not in err_str and "1001" not in err_str:
            print(f"WS Error: {err_str}")
    finally:
        ws_manager.disconnect(websocket)
