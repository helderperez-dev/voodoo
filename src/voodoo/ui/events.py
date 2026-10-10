"""Session-owned browser events and targeted WebSocket delivery.

HTTP rendering and its WebSocket transport share one opaque UI session. Each
session owns callable bindings and connections; browser patches are delivered
only to that session. Legacy named ``@event`` handlers remain application-level
functions, but they execute inside the caller's session context.
"""

from __future__ import annotations

import asyncio
import contextvars
import inspect
import json
import logging
import secrets
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from starlette.requests import Request
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

__all__ = [
    "UIEvent",
    "UISession",
    "WebSocketManager",
    "activate_ui_session",
    "bind_event",
    "current_ui_session_id",
    "dispatch_ui_event",
    "event",
    "event_bindings",
    "event_handlers",
    "register_event",
    "start_event_binding_tracking",
    "stop_event_binding_tracking",
    "websocket_endpoint",
    "ws_manager",
]

logger = logging.getLogger(__name__)

UI_SESSION_COOKIE = "voodoo_ui_session"
DEFAULT_SESSION_IDLE_TIMEOUT = 300.0
DEFAULT_MAX_SESSIONS = 10_000
DEFAULT_MAX_BINDINGS_PER_SESSION = 5_000
DEFAULT_MAX_MESSAGE_SIZE = 64 * 1024
DEFAULT_MAX_MESSAGES_PER_MINUTE = 600
DEFAULT_SEND_TIMEOUT = 5.0

_current_ui_session: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "voodoo_ui_session", default=None
)
_rendered_event_bindings: contextvars.ContextVar[set[str] | None] = (
    contextvars.ContextVar("voodoo_rendered_event_bindings", default=None)
)


def current_ui_session_id() -> str | None:
    """Return the UI session active in the current render/event context."""

    return _current_ui_session.get()


def start_event_binding_tracking() -> None:
    """Begin collecting callable bindings emitted by one rendered region."""

    _rendered_event_bindings.set(set())


def stop_event_binding_tracking() -> set[str]:
    """Finish callable-binding collection for one rendered region."""

    bindings = _rendered_event_bindings.get()
    _rendered_event_bindings.set(None)
    return bindings or set()


@contextmanager
def activate_ui_session(session_id: str | None) -> Iterator[None]:
    """Run rendering or event dispatch under one UI session identity."""

    token = _current_ui_session.set(session_id)
    try:
        yield
    finally:
        _current_ui_session.reset(token)


@dataclass(frozen=True, slots=True)
class UIEvent:
    """Framework-neutral event delivered from the browser to Python."""

    type: str
    value: Any = None
    element_id: str | None = None
    meta: Mapping[str, Any] = field(default_factory=dict)
    session_id: str | None = None
    principal_id: str | None = None


@dataclass(slots=True)
class UISession:
    """Bounded server-side ownership for one browser interaction session."""

    session_id: str
    principal_id: str | None = None
    event_bindings: dict[str, Callable[..., Any]] = field(default_factory=dict)
    callable_bindings: dict[int, str] = field(default_factory=dict)
    render_bindings: dict[str, set[str]] = field(default_factory=dict)
    state_cells: set[Any] = field(default_factory=set)
    connections: list[WebSocket] = field(default_factory=list)
    created_at: float = field(default_factory=time.monotonic)
    last_seen: float = field(default_factory=time.monotonic)

    def touch(self) -> None:
        self.last_seen = time.monotonic()


class WebSocketManager:
    """Own UI sessions and deliver messages only to their connections."""

    def __init__(
        self,
        *,
        max_sessions: int = DEFAULT_MAX_SESSIONS,
        session_idle_timeout: float = DEFAULT_SESSION_IDLE_TIMEOUT,
        max_bindings_per_session: int = DEFAULT_MAX_BINDINGS_PER_SESSION,
        send_timeout: float = DEFAULT_SEND_TIMEOUT,
    ) -> None:
        self.active_connections: list[WebSocket] = []
        self.sessions: dict[str, UISession] = {}
        self._connection_sessions: dict[int, str] = {}
        self._expiry_tasks: dict[str, asyncio.Task[None]] = {}
        self.max_sessions = max_sessions
        self.session_idle_timeout = session_idle_timeout
        self.max_bindings_per_session = max_bindings_per_session
        self.send_timeout = send_timeout

    @staticmethod
    def _new_session_id() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def _valid_session_id(session_id: str | None) -> bool:
        return bool(session_id and 32 <= len(session_id) <= 128)

    def _evict_inactive_session(self) -> None:
        inactive = [
            session for session in self.sessions.values() if not session.connections
        ]
        if not inactive:
            raise RuntimeError("The UI session capacity is exhausted")
        oldest = min(inactive, key=lambda session: session.last_seen)
        self.destroy_session(oldest.session_id)

    def get_or_create_session(
        self,
        session_id: str | None = None,
        *,
        principal_id: str | None = None,
        rotate_on_principal_change: bool = True,
    ) -> tuple[UISession, bool]:
        """Resolve a session, rotating when its authenticated owner changes."""

        candidate = session_id if self._valid_session_id(session_id) else None
        session = self.sessions.get(candidate or "")
        if session is not None and (
            not rotate_on_principal_change or session.principal_id == principal_id
        ):
            session.touch()
            return session, False

        if len(self.sessions) >= self.max_sessions:
            self._evict_inactive_session()
        created = UISession(
            session_id=self._new_session_id(),
            principal_id=principal_id,
        )
        self.sessions[created.session_id] = created
        return created, True

    def session_for_request(self, request: Request) -> tuple[UISession, bool]:
        """Resolve UI session ownership from an authenticated HTTP request."""

        user = getattr(request.state, "user", None)
        principal_id = None
        if user is not None and getattr(user, "is_authenticated", False):
            principal_id = (
                str(getattr(user, "id", None) or getattr(user, "username", "") or "")
                or None
            )
        return self.get_or_create_session(
            request.cookies.get(UI_SESSION_COOKIE),
            principal_id=principal_id,
        )

    def get_session(self, session_id: str | None) -> UISession | None:
        if session_id is None:
            return None
        session = self.sessions.get(session_id)
        if session is not None:
            session.touch()
        return session

    def retain_render_bindings(
        self, session_id: str, region_id: str, bindings: set[str]
    ) -> None:
        """Replace one region's bindings and discard session-orphaned handlers."""

        session = self.get_session(session_id)
        if session is None:
            return
        session.render_bindings[region_id] = set(bindings)
        retained = set().union(*session.render_bindings.values())
        for binding in list(session.event_bindings):
            if binding in retained:
                continue
            handler = session.event_bindings.pop(binding)
            session.callable_bindings.pop(id(handler), None)

    async def connect(
        self,
        websocket: WebSocket,
        *,
        session_id: str | None,
        principal_id: str | None,
    ) -> UISession:
        """Accept a connection only when its session owner still matches."""

        existing = self.get_session(session_id)
        if existing is not None and existing.principal_id != principal_id:
            await websocket.close(code=4403, reason="UI session owner changed")
            raise PermissionError("UI session principal mismatch")

        session, _created = self.get_or_create_session(
            session_id,
            principal_id=principal_id,
            rotate_on_principal_change=False,
        )
        expiry = self._expiry_tasks.pop(session.session_id, None)
        if expiry is not None:
            expiry.cancel()
        await websocket.accept()
        session.connections.append(websocket)
        self.active_connections.append(websocket)
        self._connection_sessions[id(websocket)] = session.session_id
        session.touch()
        return session

    def disconnect(self, websocket: WebSocket) -> None:
        """Detach one socket and schedule bounded session teardown."""

        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        session_id = self._connection_sessions.pop(id(websocket), None)
        session = self.sessions.get(session_id or "")
        if session is None:
            return
        if websocket in session.connections:
            session.connections.remove(websocket)
        session.touch()
        if not session.connections:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                self.destroy_session(session.session_id)
            else:
                old_task = self._expiry_tasks.pop(session.session_id, None)
                if old_task is not None:
                    old_task.cancel()
                self._expiry_tasks[session.session_id] = loop.create_task(
                    self._expire_session(session.session_id, session.last_seen)
                )

    async def _expire_session(self, session_id: str, last_seen: float) -> None:
        try:
            await asyncio.sleep(self.session_idle_timeout)
            session = self.sessions.get(session_id)
            if (
                session is not None
                and not session.connections
                and session.last_seen <= last_seen
            ):
                self.destroy_session(session_id)
        except asyncio.CancelledError:
            return
        finally:
            current = self._expiry_tasks.get(session_id)
            if current is asyncio.current_task():
                self._expiry_tasks.pop(session_id, None)

    def destroy_session(self, session_id: str) -> None:
        """Remove all server-owned UI state for a disconnected session."""

        session = self.sessions.pop(session_id, None)
        expiry = self._expiry_tasks.pop(session_id, None)
        try:
            current_task = asyncio.current_task()
        except RuntimeError:
            current_task = None
        if expiry is not None and expiry is not current_task:
            expiry.cancel()
        if session is None:
            return
        for connection in list(session.connections):
            if connection in self.active_connections:
                self.active_connections.remove(connection)
            self._connection_sessions.pop(id(connection), None)
        from voodoo.ui.state import state_renderer

        state_renderer.unbind_session(session_id)
        for cell in session.state_cells:
            cell.clear_session(session_id)

    def reset(self) -> None:
        """Synchronously clear UI transport state for tests/shutdown."""

        tasks = list(self._expiry_tasks.values())
        self._expiry_tasks.clear()
        for task in tasks:
            task.cancel()
        for session_id in list(self.sessions):
            self.destroy_session(session_id)
        self.active_connections.clear()
        self._connection_sessions.clear()

    async def send_to_session(self, session_id: str, message: str) -> None:
        """Send a serialized message to every connection owned by one session."""

        session = self.get_session(session_id)
        if session is None:
            return
        for connection in list(session.connections):
            try:
                await asyncio.wait_for(
                    connection.send_text(message), timeout=self.send_timeout
                )
            except (TimeoutError, RuntimeError, WebSocketDisconnect):
                self.disconnect(connection)

    async def broadcast_patch(self, element_id: str, html: str) -> None:
        """Patch the current session; the historical name is API compatibility."""

        session_id = current_ui_session_id()
        if session_id is None:
            logger.warning(
                "Discarded UI patch outside a UI session", extra={"id": element_id}
            )
            return
        message = json.dumps({"type": "patch", "id": element_id, "html": html})
        await self.send_to_session(session_id, message)

    async def broadcast_append(self, element_id: str, html: str) -> None:
        """Append in the current session; never fan out implicitly."""

        session_id = current_ui_session_id()
        if session_id is None:
            logger.warning(
                "Discarded UI append outside a UI session", extra={"id": element_id}
            )
            return
        message = json.dumps({"type": "append", "id": element_id, "html": html})
        await self.send_to_session(session_id, message)


ws_manager = WebSocketManager()

# Legacy named handlers are application-level by design.
event_handlers: dict[str, Callable[..., Any]] = {}

# Compatibility registry used only when code renders outside a UI session.
event_bindings: dict[str, Callable[..., Any]] = {}
_callable_bindings: dict[int, str] = {}


def register_event(name: str, handler: Callable[..., Any]) -> None:
    event_handlers[name] = handler


def _binding_registries() -> tuple[
    dict[str, Callable[..., Any]],
    dict[int, str],
    UISession | None,
]:
    session = ws_manager.get_session(current_ui_session_id())
    if session is None:
        return event_bindings, _callable_bindings, None
    return session.event_bindings, session.callable_bindings, session


def bind_event(handler: Callable[..., Any] | str) -> str:
    """Return a stable opaque binding owned by the current UI session."""

    if isinstance(handler, str):
        return handler
    if not callable(handler):
        raise TypeError("UI event handler must be a callable or legacy event name")

    bindings, reverse, session = _binding_registries()
    identity = id(handler)
    binding = reverse.get(identity)
    if binding is None or bindings.get(binding) is not handler:
        binding = f"vdui_{uuid4().hex}"
        reverse[identity] = binding
        bindings[binding] = handler
        if session is not None and len(bindings) > ws_manager.max_bindings_per_session:
            oldest_binding = next(iter(bindings))
            oldest_handler = bindings.pop(oldest_binding)
            reverse.pop(id(oldest_handler), None)
    tracked = _rendered_event_bindings.get()
    if tracked is not None:
        tracked.add(binding)
    return binding


def event(func: Callable[..., Any]) -> Callable[..., Any]:
    """Register an application-level legacy named handler."""

    register_event(func.__name__, func)
    return func


async def dispatch_ui_event(
    binding: str,
    *,
    event_type: str,
    element_id: str | None = None,
    value: Any = None,
    meta: Mapping[str, Any] | None = None,
    session_id: str | None = None,
) -> bool:
    """Resolve and invoke a binding within its owning UI session."""

    requested_session_id = session_id or current_ui_session_id()
    resolved_session_id = requested_session_id
    inferred_session = False
    if resolved_session_id is None and binding not in event_bindings:
        owners = [
            candidate.session_id
            for candidate in ws_manager.sessions.values()
            if binding in candidate.event_bindings
        ]
        # Keep the direct helper useful for single-session test/docs tooling,
        # while refusing an ambiguous binding that could cross user sessions.
        if len(owners) == 1:
            resolved_session_id = owners[0]
            inferred_session = True
    session = ws_manager.get_session(resolved_session_id)
    if session is not None:
        handler = session.event_bindings.get(binding) or event_handlers.get(binding)
    elif resolved_session_id is not None:
        handler = event_handlers.get(binding)
    else:
        handler = event_bindings.get(binding) or event_handlers.get(binding)
    if handler is None:
        return False

    ui_event = UIEvent(
        type=event_type,
        value=value,
        element_id=element_id,
        meta=dict(meta or {}),
        session_id=resolved_session_id,
        principal_id=session.principal_id if session is not None else None,
    )
    args = _handler_args(handler, ui_event)
    execution_session_id = None if inferred_session else resolved_session_id
    with activate_ui_session(execution_session_id):
        result = handler(*args)
    if inspect.isawaitable(result):
        with activate_ui_session(execution_session_id):
            await result
    if inferred_session:
        # ``dispatch_ui_event`` is also used by the documentation harness as a
        # direct, single-session compatibility helper. Its legacy handlers
        # execute against application state; discard the inferred session's
        # cached copies so the next HTTP render observes that update. Real
        # browser/WebSocket dispatch always has an explicit session context and
        # never takes this path.
        owner = ws_manager.get_session(resolved_session_id)
        if owner is not None:
            for cell in tuple(owner.state_cells):
                cell.clear_session(owner.session_id)
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

    if len(required) >= 2 or len(positional) >= 2:
        return (event_value.element_id, event_value.value)
    return (event_value.value,)


def _websocket_config(websocket: WebSocket) -> Any:
    app_state = getattr(websocket.app, "state", None)
    configured = getattr(app_state, "voodoo_config", None)
    if configured is not None:
        return configured
    from voodoo.config import get_config

    return get_config()


def _origin_allowed(websocket: WebSocket, resolved_config: Any) -> bool:
    origin = websocket.headers.get("origin")
    if origin is None:
        return str(resolved_config.env).lower() != "production"
    parsed = urlsplit(origin)
    host = websocket.headers.get("host", "")
    if parsed.netloc == host and parsed.scheme in {"http", "https"}:
        return True
    return origin in resolved_config.security.cors_origins


def _websocket_principal(websocket: WebSocket, resolved_config: Any) -> str | None:
    token = websocket.cookies.get(resolved_config.auth.cookie_name)
    if not token:
        return None
    from voodoo.auth import AuthError, decode_access_token

    try:
        payload = decode_access_token(
            token,
            secret_key=resolved_config.auth.secret_key,
        )
    except AuthError:
        return None
    return str(payload.get("sub") or payload.get("id") or "") or None


async def _receive_ui_messages(websocket: WebSocket, session: UISession) -> None:
    message_times: list[float] = []
    with activate_ui_session(session.session_id):
        while True:
            raw = await websocket.receive_text()
            if len(raw.encode()) > DEFAULT_MAX_MESSAGE_SIZE:
                await websocket.close(code=1009, reason="UI event is too large")
                return

            now = time.monotonic()
            message_times[:] = [stamp for stamp in message_times if stamp > now - 60]
            if len(message_times) >= DEFAULT_MAX_MESSAGES_PER_MINUTE:
                await websocket.close(code=4429, reason="UI event rate exceeded")
                return
            message_times.append(now)

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.close(code=1007, reason="Invalid UI event JSON")
                return
            if not isinstance(msg, dict) or msg.get("type") != "event":
                continue
            binding = msg.get("binding") or msg.get("event")
            if not binding:
                continue
            handled = await dispatch_ui_event(
                str(binding),
                event_type=str(msg.get("event_type") or "event"),
                element_id=msg.get("id"),
                value=msg.get("value"),
                meta=msg.get("meta") if isinstance(msg.get("meta"), dict) else None,
                session_id=session.session_id,
            )
            if not handled:
                await ws_manager.send_to_session(
                    session.session_id,
                    json.dumps({"type": "error", "code": "unknown_binding"}),
                )


async def websocket_endpoint(websocket: WebSocket) -> None:
    """Receive bounded UI events under authenticated session ownership."""

    resolved_config = _websocket_config(websocket)
    if not _origin_allowed(websocket, resolved_config):
        await websocket.close(code=4403, reason="WebSocket origin is not allowed")
        return

    principal_id = _websocket_principal(websocket, resolved_config)
    try:
        session = await ws_manager.connect(
            websocket,
            session_id=websocket.cookies.get(UI_SESSION_COOKIE),
            principal_id=principal_id,
        )
    except WebSocketDisconnect as exc:
        logger.info("UI WebSocket rejected", extra={"code": exc.code})
        return
    except PermissionError:
        return

    try:
        await _receive_ui_messages(websocket, session)
    except WebSocketDisconnect as exc:
        if exc.code not in (1000, 1001):
            logger.info("UI WebSocket disconnected", extra={"code": exc.code})
    except RuntimeError:
        if websocket.application_state != WebSocketState.DISCONNECTED:
            logger.exception("UI WebSocket runtime failure")
    finally:
        ws_manager.disconnect(websocket)
