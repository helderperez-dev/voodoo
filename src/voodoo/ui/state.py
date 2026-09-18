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
import inspect
from collections.abc import Callable
from typing import Any

from voodoo.core.errors import StateError

_state_context: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "voodoo_state_context", default=None
)
_rendered_cells: contextvars.ContextVar[list[State] | None] = contextvars.ContextVar(
    "voodoo_rendered_cells", default=None
)
_runtime_dependency_context: contextvars.ContextVar[
    tuple[Any, str] | None
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
        graph, consumer = dependency
        graph.observe(consumer, cell.dependency_id)


def start_dependency_tracking(graph: Any, consumer: str) -> contextvars.Token:
    """Bridge UI State reads into the Runtime dependency overlay."""
    return _runtime_dependency_context.set((graph, consumer))


def stop_dependency_tracking(token: contextvars.Token) -> None:
    _runtime_dependency_context.reset(token)


class State:
    """A small observable state cell used by the UI render graph."""

    __slots__ = ("_value", "_subscribers", "dependency_id", "_revision")

    def __init__(self, initial: Any = None) -> None:
        self._value = initial
        self.dependency_id = f"state:{id(self):x}"
        self._revision = 0
        self._subscribers: list[Callable[[Any], None]] = []

    def get(self) -> Any:
        _track_read(self)
        return self._value

    def set(self, value: Any) -> None:
        if value is self._value and not isinstance(value, (int, float, str, bool)):
            return
        self._value = value
        self._revision += 1
        self._notify(value)

    def update(self, fn: Callable[[Any], Any]) -> None:
        if not callable(fn):
            raise StateError("update() requires a callable")
        self._value = fn(self._value)
        self._revision += 1
        self._notify(self._value)

    @property
    def revision(self) -> str:
        return str(self._revision)

    def subscribe(self, fn: Callable[[Any], None]) -> Callable[[], None]:
        self._subscribers.append(fn)
        return lambda: self._unsubscribe(fn)

    def _unsubscribe(self, fn: Callable[[Any], None]) -> None:
        try:
            self._subscribers.remove(fn)
        except ValueError:
            pass

    def _notify(self, value: Any) -> None:
        for subscriber in list(self._subscribers):
            try:
                subscriber(value)
            except Exception:
                # A UI subscriber must never make the state mutation itself fail.
                pass

    def __repr__(self) -> str:
        return f"State({self._value!r})"


def state(initial: Any = None) -> State:
    return State(initial)


class StateRenderer:
    """Automatic reactive render graph for page and region bindings.

    A binding stores only a render function and its *current* State dependencies.
    Every rerender discovers those dependencies again. Multiple mutations in the
    same event-loop turn are coalesced into one render; mutations arriving while
    that render runs schedule one more pass instead of creating a rerender storm.
    """

    def __init__(self) -> None:
        self._bindings: dict[str, tuple[Callable[..., Any], list[State]]] = {}
        self._subscriptions: dict[str, list[Callable[[], None]]] = {}
        self._pending: dict[str, asyncio.Task[None]] = {}
        self._dirty: set[str] = set()

    def bind(
        self,
        element_id: str,
        page_func: Callable[..., Any],
        cells: list[State] | None = None,
    ) -> None:
        """Bind one rendered region to the State cells it currently depends on."""

        self._replace_binding(element_id, page_func, list(cells or []))

    def _replace_binding(
        self,
        element_id: str,
        page_func: Callable[..., Any],
        cells: list[State],
    ) -> None:
        self._unsubscribe_binding(element_id)
        self._bindings[element_id] = (page_func, cells)
        self._subscriptions[element_id] = [
            self._subscribe_cell(element_id, cell) for cell in cells
        ]

    def _subscribe_cell(self, element_id: str, cell: State) -> Callable[[], None]:
        def _on_change(_value: Any) -> None:
            self.invalidate(element_id)

        return cell.subscribe(_on_change)

    def invalidate(self, element_id: str) -> None:
        """Mark a region dirty and schedule at most one render task for it."""

        if element_id not in self._bindings:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        self._dirty.add(element_id)
        task = self._pending.get(element_id)
        if task is None or task.done():
            task = loop.create_task(self._drain(element_id))
            self._pending[element_id] = task
            task.add_done_callback(
                lambda _task, eid=element_id: self._pending.pop(eid, None)
            )

    async def _drain(self, element_id: str) -> None:
        while element_id in self._dirty and element_id in self._bindings:
            self._dirty.discard(element_id)
            await self.rerender(element_id)

    def unbind(self, element_id: str) -> None:
        self._bindings.pop(element_id, None)
        self._unsubscribe_binding(element_id)
        self._dirty.discard(element_id)
        task = self._pending.pop(element_id, None)
        if task is not None and not task.done():
            task.cancel()

    def _unsubscribe_binding(self, element_id: str) -> None:
        for unsubscribe in self._subscriptions.pop(element_id, []):
            unsubscribe()

    async def rerender(self, element_id: str) -> str | None:
        """Render one invalidated region, refresh dependencies and patch the DOM."""

        binding = self._bindings.get(element_id)
        if binding is None:
            return None

        page_func, _old_cells = binding
        start_render_tracking()
        try:
            result = page_func()
            if inspect.isawaitable(result):
                result = await result
            cells = stop_render_tracking()
        except BaseException:
            stop_render_tracking()
            raise

        html = self._render_component(result)

        # Dependency replacement happens before broadcasting so any state
        # mutation triggered immediately after this render observes the new graph.
        self._replace_binding(element_id, page_func, cells)

        # Keep the legacy root wrapper in the transport. The modern client keeps
        # the real #root node stable and patches only its contents.
        wire_html = f'<div id="root">{html}</div>' if element_id == "root" else html
        await self._broadcast_patch(element_id, wire_html)
        return html

    @staticmethod
    def _render_component(result: Any) -> str:
        from voodoo.ui.component import Component

        if isinstance(result, Component):
            return result.render()
        return str(result)

    @staticmethod
    async def _broadcast_patch(element_id: str, html: str) -> None:
        from voodoo.ui.events import ws_manager

        await ws_manager.broadcast_patch(element_id, html)


state_renderer = StateRenderer()
