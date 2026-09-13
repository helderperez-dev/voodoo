"""Python-first interactive Voodoo components.

This module is the interaction layer for the component library. Components
express semantic browser events through ``data-vd-*`` attributes while
:mod:`voodoo.static.client.js` owns the transport and DOM mechanics.

No first-party component in this module emits inline JavaScript.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from voodoo.ui.component import Component, escape
from voodoo.ui.events import bind_event
from voodoo.ui.library import Icon, Text

EventHandler = Callable[..., Any] | str


def _event_attr(
    component: Component, event_type: str, handler: EventHandler | None
) -> None:
    if handler is not None:
        component.attrs[f"data-vd-event-{event_type}"] = bind_event(handler)


class Button(Component):
    """Primary action control.

    ``on_click`` accepts a Python callable directly. ``loading`` is semantic:
    it disables repeated activation and announces busy state automatically.
    """

    tag = "button"
    style = "button"

    def __init__(
        self,
        *children: Any,
        on_click: EventHandler | None = None,
        variant: str | None = None,
        size: str | None = None,
        loading: bool = False,
        disabled: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(*children, **kwargs)
        self.attrs.setdefault("type", "button")
        _event_attr(self, "click", on_click)
        if disabled or loading:
            self.attrs["disabled"] = True
        if loading:
            self.attrs["aria-busy"] = "true"
            self.attrs["data-vd-loading"] = "true"
        self.props = {
            "variant": variant,
            "size": size,
            "loading": loading,
            "disabled": disabled,
        }


class Form(Component):
    tag = "form"
    style = "form"

    def __init__(
        self,
        *children: Any,
        on_submit: EventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*children, **kwargs)
        _event_attr(self, "submit", on_submit)


class Input(Component):
    tag = "input"
    style: str | None = "input"

    def __init__(
        self,
        *children: Any,
        on_change: EventHandler | None = None,
        on_input: EventHandler | None = None,
        size: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*children, **kwargs)
        _event_attr(self, "change", on_change)
        _event_attr(self, "input", on_input)
        self.attrs.setdefault("type", "text")
        if self.attrs["type"] in ("checkbox", "radio", "hidden"):
            self.style = None
        self.props = {"size": size}


class Textarea(Component):
    tag = "textarea"
    style = "textarea"

    def __init__(
        self,
        *children: Any,
        on_change: EventHandler | None = None,
        on_input: EventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*children, **kwargs)
        _event_attr(self, "change", on_change)
        _event_attr(self, "input", on_input)


class Select(Component):
    tag = "select"
    style = "select"

    def __init__(
        self,
        *children: Any,
        on_change: EventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*children, **kwargs)
        _event_attr(self, "change", on_change)


class Checkbox(Input):
    def __init__(
        self,
        *children: Any,
        on_change: EventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        kwargs["type"] = "checkbox"
        super().__init__(*children, on_change=on_change, **kwargs)
        self.style = "checkbox"


class Radio(Input):
    def __init__(
        self,
        *children: Any,
        on_change: EventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        kwargs["type"] = "radio"
        super().__init__(*children, on_change=on_change, **kwargs)
        self.style = "radio"


class Composer(Component):
    """Chat composer with Python-callable send behavior and no inline JS."""

    style = "composer"

    def __init__(
        self,
        *,
        on_send: EventHandler,
        placeholder: str = "Type a message…",
        disabled: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._binding = bind_event(on_send)
        self._placeholder = placeholder
        self._disabled = disabled

    def render(self) -> str:
        disabled_attr = " disabled" if self._disabled else ""
        return (
            f"<div{self._render_attrs()}>"
            f'<textarea class="vd-composer-input" rows="1" '
            f'placeholder="{escape(self._placeholder)}" '
            f'data-vd-enter-send="{escape(self._binding)}"{disabled_attr}></textarea>'
            f'<button type="button" class="vd-composer-send" '
            f'data-vd-enter-send-trigger="{escape(self._binding)}"{disabled_attr}>'
            f"{Icon('send').render()}</button>"
            "</div>"
        )


class ThemeToggle(Component):
    """Theme control using a Voodoo client action rather than inline JS."""

    tag = "button"
    style = "theme-toggle"

    def __init__(self, label: str = "Toggle theme", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.attrs["type"] = "button"
        self.attrs["aria-label"] = label
        self.attrs["data-vd-action"] = "toggle-theme"
        self.children = (
            Text("☀", class_="vd-theme-toggle-sun"),
            Text("☾", class_="vd-theme-toggle-moon"),
        )
