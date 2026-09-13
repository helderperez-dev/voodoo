"""Reactive state primitive.

``state(initial)`` returns a :class:`State` cell that the developer reads with
``get()``, updates with ``set()`` / ``update()``, and observes with
``subscribe()``. When a state cell changes inside an event handler, the
:class:`StateRenderer` re-runs the bound page function and broadcasts a DOM
patch over the existing WebSocket transport — the developer writes zero JS.
"""

from __future__ import annotations

import contextvars
from collections.abc import Callable
from typing import Any

from voodoo.core.errors import StateError

#: ContextVar so state cells can be scoped to a request/page in the future.
_state_context: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "voodoo_state_context", default=None
)

#: Render-time tracking of state cells read during the current page render
#: (spec: reactive loop — @page renders must record which cells they read so
#: StateRenderer can auto-bind them without developer-written bind() calls).
_rendered_cells: contextvars.ContextVar[list[State] | None] = contextvars.ContextVar(
    "voodoo_rendered_cells", default=None
)


def start_render_tracking() -> list[State]:
    """Begin tracking state reads for the current render. Returns the list."""
    cells: list[State] = []
    _rendered_cells.set(cells)
    return cells


def stop_render_tracking() -> list[State]:
    """End tracking and return the cells read during the render."""
    cells = _rendered_cells.get()
    _rendered_cells.set(None)
    return cells or []


def _track_read(cell: State) -> None:
    """Record a cell read (called from State.get during page renders)."""
    cells = _rendered_cells.get()
    if cells is not None and cell not in cells:
        cells.append(cell)


class State:
    """An observable value cell.

    >>> count = State(0)
    >>> count.get()
    0
    >>> count.set(5)
    >>> count.get()
    5
    >>> count.update(lambda x: x + 1)
    >>> count.get()
    6
    """

    __slots__ = ("_value", "_subscribers")

    def __init__(self, initial: Any = None) -> None:
        self._value = initial
        self._subscribers: list[Callable[[Any], None]] = []

    # -- read / write --------------------------------------------------------

    def get(self) -> Any:
        _track_read(self)
        return self._value

    def set(self, value: Any) -> None:
        if value is self._value and not isinstance(value, (int, float, str, bool)):
            return
        self._value = value
        self._notify(value)

    def update(self, fn: Callable[[Any], Any]) -> None:
        if not callable(fn):
            raise StateError("update() requires a callable")
        self._value = fn(self._value)
        self._notify(self._value)

    # -- subscriptions -------------------------------------------------------

    def subscribe(self, fn: Callable[[Any], None]) -> Callable[[], None]:
        """Register *fn* to be called on every change. Returns an unsubscribe."""
        self._subscribers.append(fn)
        return lambda: self._unsubscribe(fn)

    def _unsubscribe(self, fn: Callable[[Any], None]) -> None:
        try:
            self._subscribers.remove(fn)
        except ValueError:
            pass

    def _notify(self, value: Any) -> None:
        for sub in list(self._subscribers):
            try:
                sub(value)
            except Exception:
                pass

    # -- dunder convenience --------------------------------------------------

    def __repr__(self) -> str:
        return f"State({self._value!r})"


def state(initial: Any = None) -> State:
    """Factory: create a reactive state cell with *initial* value."""
    return State(initial)


# ---------------------------------------------------------------------------
# StateRenderer — re-render a page function and broadcast a DOM patch
# ---------------------------------------------------------------------------


class StateRenderer:
    """Binds state cells to page render functions.

    When a state cell changes (via ``set``/``update``) during an event handler,
    the renderer re-invokes the registered page function, renders the result,
    and broadcasts a ``patch`` message over WebSocket so the browser swaps the
    subtree's ``outerHTML``.

    MVP scope: full subtree re-render (no diffing), broadcast to all WS clients.
    """

    def __init__(self) -> None:
        # element_id -> (page_func, state_cells)
        self._bindings: dict[str, tuple[Callable[..., Any], list[State]]] = {}
        # state cell -> unsubscribe callables (one per binding)
        self._unsubscribers: dict[int, list[Callable[[], None]]] = {}

    def bind(
        self,
        element_id: str,
        page_func: Callable[..., Any],
        cells: list[State] | None = None,
    ) -> None:
        """Bind *element_id* to *page_func*, re-rendering on cell changes.

        When *cells* are provided, each cell's ``set``/``update`` schedules a
        re-render of this binding (patched over WebSocket) — the "zero JS"
        reactive loop.
        """
        # Re-binding replaces the old subscription set.
        self.unbind(element_id)
        self._bindings[element_id] = (page_func, cells or [])
        for cell in cells or []:
            unsub = self._subscribe_cell(element_id, cell)
            self._unsubscribers.setdefault(id(cell), []).append(unsub)

    def _subscribe_cell(self, element_id: str, cell: State) -> Callable[[], None]:
        import asyncio

        def _on_change(_value: Any) -> None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                return  # no loop (e.g. sync import-time sets) — skip patch
            loop.create_task(self.rerender(element_id))

        return cell.subscribe(_on_change)

    def unbind(self, element_id: str) -> None:
        binding = self._bindings.pop(element_id, None)
        if binding is None:
            return
        _page_func, cells = binding
        for cell in cells:
            unsubs = self._unsubscribers.pop(id(cell), [])
            for unsub in unsubs:
                unsub()

    async def rerender(self, element_id: str) -> str | None:
        """Re-run the page function for *element_id* and broadcast the patch.

        Returns the rendered HTML (or ``None`` when no binding exists).
        """
        binding = self._bindings.get(element_id)
        if binding is None:
            return None

        page_func, _cells = binding
        import inspect

        result = page_func()
        if inspect.iscoroutine(result):
            result = await result

        html = self._render_component(result)
        # Keep #root present across patches: the client swaps outerHTML, so an
        # unwrapped patch would remove the container div after the first patch.
        if element_id == "root":
            html = f'<div id="root">{html}</div>'
        await self._broadcast_patch(element_id, html)
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


#: Module-level singleton used by event handlers to trigger re-renders.
state_renderer = StateRenderer()
