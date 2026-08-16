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

    def bind(
        self,
        element_id: str,
        page_func: Callable[..., Any],
        cells: list[State] | None = None,
    ) -> None:
        self._bindings[element_id] = (page_func, cells or [])

    def unbind(self, element_id: str) -> None:
        self._bindings.pop(element_id, None)

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
