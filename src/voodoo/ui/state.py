"""Reactive UI state and dependency-driven rendering.

``state(initial)`` creates an observable cell. Reads performed while a page or
reactive region renders are tracked automatically. When one of those cells
changes Voodoo schedules a rerender, discovers the dependency set again and
patches the browser over the existing WebSocket connection.

Application code does not call a rerender function and does not need browser
JavaScript.
"""

from __future__ import annotations

import asyncio
import contextvars
import copy
import inspect
from collections.abc import Callable
from typing import Any

from voodoo.core.errors import StateError

__all__ = [
    "State",
    "StateRenderer",
    "start_dependency_tracking",
    "start_render_tracking",
    "state",
    "state_renderer",
    "stop_dependency_tracking",
    "stop_render_tracking",
]

StateScope = str
BindingKey = str | tuple[str, str]


def _current_session_id() -> str | None:
    from voodoo.ui.events import current_ui_session_id

    return current_ui_session_id()


_state_context: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "voodoo_state_context", default=None
)
_rendered_cells: contextvars.ContextVar[list[State] | None] = contextvars.ContextVar(
    "voodoo_rendered_cells", default=None
)
_runtime_dependency_context: contextvars.ContextVar[
    tuple[Any, str, set[str]] | None
] = contextvars.ContextVar("voodoo_runtime_dependency_context", default=None)


def start_render_tracking() -> list[State]:
    cells: list[State] = []
    _rendered_cells.set(cells)
    return cells


def stop_render_tracking() -> list[State]:
    cells = _rendered_cells.get()
    _rendered_cells.set(None)
    return cells or []


def _track_read(cell: State) -> None:
    cells = _rendered_cells.get()
    if cells is not None and cell not in cells:
        cells.append(cell)
    dependency = _runtime_dependency_context.get()
    if dependency is not None:
        graph, _consumer, sources = dependency
        sources.add(cell.dependency_id)
        cell._attach_dependency_graph(graph)


def start_dependency_tracking(graph: Any, consumer: str) -> contextvars.Token:
    """Bridge UI State reads into the Runtime dependency overlay."""
    return _runtime_dependency_context.set((graph, consumer, set()))


def stop_dependency_tracking(token: contextvars.Token) -> None:
    dependency = _runtime_dependency_context.get()
    try:
        if dependency is not None:
            graph, consumer, sources = dependency
            graph.replace(consumer, sources)
    finally:
        _runtime_dependency_context.reset(token)


class State:
    """A small observable state cell used by the UI render graph."""

    __slots__ = (
        "_value",
        "_session_values",
        "_subscribers",
        "dependency_id",
        "_revision",
        "_session_revisions",
        "_dependency_graphs",
        "scope",
    )

    def __init__(self, initial: Any = None, *, scope: StateScope = "session") -> None:
        if scope not in {"session", "application"}:
            raise StateError("State scope must be 'session' or 'application'")
        self._value = initial
        self._session_values: dict[str, Any] = {}
        self.scope = scope
        self.dependency_id = f"state:{id(self):x}"
        self._revision = 0
        self._session_revisions: dict[str, int] = {}
        self._dependency_graphs: list[Any] = []
        self._subscribers: list[tuple[str | None, Callable[[Any], None]]] = []

    def _session_value(self, session_id: str) -> Any:
        from voodoo.ui.events import ws_manager

        session = ws_manager.get_session(session_id)
        if session is not None:
            session.state_cells.add(self)
        if session_id not in self._session_values:
            try:
                self._session_values[session_id] = copy.deepcopy(self._value)
            except (TypeError, ValueError) as exc:
                raise StateError(
                    "Session state initial values must be copyable; use "
                    "scope='application' only for deliberately shared state"
                ) from exc
        return self._session_values[session_id]

    def get(self) -> Any:
        _track_read(self)
        session_id = _current_session_id()
        if self.scope == "session" and session_id is not None:
            return self._session_value(session_id)
        return self._value

    def set(self, value: Any) -> None:
        session_id = _current_session_id() if self.scope == "session" else None
        current = self._session_value(session_id) if session_id else self._value
        if value is current and not isinstance(value, (int, float, str, bool)):
            return
        if session_id is not None:
            self._session_values[session_id] = value
            self._session_revisions[session_id] = (
                self._session_revisions.get(session_id, 0) + 1
            )
        else:
            self._value = value
            self._revision += 1
        self._invalidate_dependencies()
        self._notify(value, session_id=session_id)

    def update(self, fn: Callable[[Any], Any]) -> None:
        if not callable(fn):
            raise StateError("update() requires a callable")
        self.set(fn(self.get()))

    @property
    def revision(self) -> str:
        session_id = _current_session_id()
        if self.scope == "session" and session_id is not None:
            return str(self._session_revisions.get(session_id, 0))
        return str(self._revision)

    def _attach_dependency_graph(self, graph: Any) -> None:
        if graph not in self._dependency_graphs:
            self._dependency_graphs.append(graph)

    def _invalidate_dependencies(self) -> None:
        for graph in self._dependency_graphs:
            graph.invalidate(self.dependency_id, revision=self.revision)

    def subscribe(
        self,
        fn: Callable[[Any], None],
        *,
        session_id: str | None = None,
    ) -> Callable[[], None]:
        subscription = (session_id, fn)
        self._subscribers.append(subscription)
        return lambda: self._unsubscribe(subscription)

    def _unsubscribe(
        self, subscription: tuple[str | None, Callable[[Any], None]]
    ) -> None:
        try:
            self._subscribers.remove(subscription)
        except ValueError:
            pass

    def _notify(self, value: Any, *, session_id: str | None) -> None:
        for owner_session, subscriber in list(self._subscribers):
            if self.scope == "session" and owner_session != session_id:
                continue
            try:
                subscriber(value)
            except (RuntimeError, StateError):
                # A stale UI subscriber cannot roll back the state mutation.
                continue

    def clear_session(self, session_id: str) -> None:
        """Release values and subscriptions owned by a closed UI session."""

        self._session_values.pop(session_id, None)
        self._session_revisions.pop(session_id, None)
        self._subscribers = [
            subscription
            for subscription in self._subscribers
            if subscription[0] != session_id
        ]

    def __repr__(self) -> str:
        return f"State({self._value!r})"


def state(initial: Any = None, *, scope: StateScope = "session") -> State:
    """Create reactive state, isolated per UI session by default."""

    return State(initial, scope=scope)


class StateRenderer:
    """Automatic reactive render graph for page and region bindings.

    A binding stores only a render function and its *current* State dependencies.
    Every rerender discovers those dependencies again. Multiple mutations in the
    same event-loop turn are coalesced into one render; mutations arriving while
    that render runs schedule one more pass instead of creating a rerender storm.
    """

    def __init__(self) -> None:
        self._bindings: dict[BindingKey, tuple[Callable[..., Any], list[State]]] = {}
        self._subscriptions: dict[BindingKey, list[Callable[[], None]]] = {}
        self._pending: dict[BindingKey, asyncio.Task[None]] = {}
        self._dirty: set[BindingKey] = set()

    @staticmethod
    def _binding_key(element_id: str, session_id: str | None = None) -> BindingKey:
        resolved_session = session_id or _current_session_id()
        return (
            (resolved_session, element_id)
            if resolved_session is not None
            else element_id
        )

    @staticmethod
    def _binding_parts(key: BindingKey) -> tuple[str | None, str]:
        return key if isinstance(key, tuple) else (None, key)

    def bind(
        self,
        element_id: str,
        page_func: Callable[..., Any],
        cells: list[State] | None = None,
        *,
        session_id: str | None = None,
    ) -> None:
        """Bind one rendered region to the State cells it currently depends on."""

        key = self._binding_key(element_id, session_id)
        self._replace_binding(key, page_func, list(cells or []))

    def _replace_binding(
        self,
        key: BindingKey,
        page_func: Callable[..., Any],
        cells: list[State],
    ) -> None:
        self._unsubscribe_binding(key)
        self._bindings[key] = (page_func, cells)
        self._subscriptions[key] = [self._subscribe_cell(key, cell) for cell in cells]

    def _subscribe_cell(self, key: BindingKey, cell: State) -> Callable[[], None]:
        def _on_change(_value: Any) -> None:
            self._invalidate_key(key)

        session_id, _element_id = self._binding_parts(key)
        return cell.subscribe(_on_change, session_id=session_id)

    def invalidate(self, element_id: str) -> None:
        """Mark a region dirty and schedule at most one render task for it."""

        key = self._binding_key(element_id)
        self._invalidate_key(key)

    def _invalidate_key(self, key: BindingKey) -> None:
        if key not in self._bindings:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        self._dirty.add(key)
        task = self._pending.get(key)
        if task is None or task.done():
            task = loop.create_task(self._drain(key))
            self._pending[key] = task

            def _remove_pending(
                _task: asyncio.Task[None], binding_key: BindingKey = key
            ) -> None:
                self._pending.pop(binding_key, None)

            task.add_done_callback(_remove_pending)

    async def _drain(self, key: BindingKey) -> None:
        while key in self._dirty and key in self._bindings:
            self._dirty.discard(key)
            await self._rerender_key(key)

    def unbind(self, element_id: str) -> None:
        key = self._binding_key(element_id)
        self._unbind_key(key)

    def _unbind_key(self, key: BindingKey) -> None:
        self._bindings.pop(key, None)
        self._unsubscribe_binding(key)
        self._dirty.discard(key)
        task = self._pending.pop(key, None)
        if task is not None and not task.done():
            task.cancel()

    def unbind_session(self, session_id: str) -> None:
        """Release every render binding and reactive value for one session."""

        cells: set[State] = set()
        for key in list(self._bindings):
            if isinstance(key, tuple) and key[0] == session_id:
                cells.update(self._bindings[key][1])
                self._unbind_key(key)
        for cell in cells:
            cell.clear_session(session_id)

    def reset(self) -> None:
        """Release every binding and pending render task."""

        for key in list(self._bindings):
            self._unbind_key(key)

    def _unsubscribe_binding(self, key: BindingKey) -> None:
        for unsubscribe in self._subscriptions.pop(key, []):
            unsubscribe()

    async def rerender(self, element_id: str) -> str | None:
        """Render one invalidated region, refresh dependencies and patch the DOM."""

        key = self._binding_key(element_id)
        return await self._rerender_key(key)

    async def _rerender_key(self, key: BindingKey) -> str | None:
        binding = self._bindings.get(key)
        if binding is None:
            return None

        session_id, element_id = self._binding_parts(key)
        page_func, _old_cells = binding
        from voodoo.ui.events import activate_ui_session

        with activate_ui_session(session_id):
            if session_id is not None:
                from voodoo.ui.events import start_event_binding_tracking

                start_event_binding_tracking()
            start_render_tracking()
            try:
                result = page_func()
                if inspect.isawaitable(result):
                    result = await result
                cells = stop_render_tracking()
            except (Exception, asyncio.CancelledError):
                stop_render_tracking()
                if session_id is not None:
                    from voodoo.ui.events import stop_event_binding_tracking

                    stop_event_binding_tracking()
                raise

            if session_id is not None:
                from voodoo.ui.events import (
                    stop_event_binding_tracking,
                    ws_manager,
                )

                try:
                    html = self._render_component(result)
                    rendered_bindings = stop_event_binding_tracking()
                except (Exception, asyncio.CancelledError):
                    stop_event_binding_tracking()
                    raise
                ws_manager.retain_render_bindings(
                    session_id, element_id, rendered_bindings
                )
            else:
                html = self._render_component(result)

            # Dependency replacement happens before broadcasting so any state
            # mutation after this render observes the new graph.
            self._replace_binding(key, page_func, cells)

            wire_html = f'<div id="root">{html}</div>' if element_id == "root" else html
            await self._broadcast_patch(element_id, wire_html)
            return html

    @staticmethod
    def _render_component(result: Any) -> str:
        from voodoo.seo import SEO
        from voodoo.ui.component import Component

        # A page may return ``(SEO, Component)`` (or the reverse) — the same
        # contract ``render_page_result`` honours on first render. A reactive
        # re-render patches only the ``#root`` body, so unwrap the tuple and
        # render just the component; the SEO metadata belongs to ``<head>``.
        component = result
        if isinstance(result, tuple) and len(result) == 2:
            first, second = result
            if isinstance(first, SEO):
                component = second
            elif isinstance(second, SEO):
                component = first

        if isinstance(component, Component):
            return component.render()
        return str(component)

    @staticmethod
    async def _broadcast_patch(element_id: str, html: str) -> None:
        from voodoo.ui.events import ws_manager

        await ws_manager.broadcast_patch(element_id, html)


state_renderer = StateRenderer()
