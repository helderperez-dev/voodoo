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


def _control_state(
    component: Component,
    *,
    disabled: bool,
    read_only: bool,
    loading: bool,
    error: bool | str,
) -> dict[str, Any]:
    """Apply the shared control-state contract and return serializable props."""
    if disabled or loading:
        component.attrs["disabled"] = True
    if read_only:
        # ``readonly`` is valid for inputs/textareas; aria-readonly keeps the
        # semantic state available for select-like controls as well.
        component.attrs["readonly"] = True
        component.attrs["aria-readonly"] = "true"
    if loading:
        component.attrs["aria-busy"] = "true"
        component.attrs["data-vd-loading"] = "true"
    if error:
        component.attrs["aria-invalid"] = "true"
        component.attrs["data-vd-state"] = "error"
    return {
        "disabled": disabled or loading,
        "read_only": read_only,
        "loading": loading,
        "error": bool(error),
    }


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
        read_only: bool = False,
        error: bool | str = False,
        **kwargs: Any,
    ) -> None:
        unavailable = disabled or read_only or loading or bool(error)
        super().__init__(*children, **kwargs)
        self.attrs.setdefault("type", "button")
        if on_click is not None and not unavailable:
            _event_attr(self, "click", on_click)
        if unavailable:
            self.attrs["disabled"] = True
            self.attrs["aria-disabled"] = "true"
        if read_only:
            self.attrs["aria-readonly"] = "true"
        if loading:
            self.attrs["aria-busy"] = "true"
            self.attrs["data-vd-loading"] = "true"
        if error:
            self.attrs["aria-invalid"] = "true"
            if isinstance(error, str):
                self.attrs["data-vd-error"] = error
        self.props = {
            "variant": variant,
            "size": size,
            "loading": loading,
            "disabled": disabled,
            "read_only": read_only,
            "error": error,
        }


class Form(Component):
    """Semantic form surface with optional generated submit action.

    ``submit="Save"`` is the happy path for the common case. Voodoo creates a
    correctly typed submit button so application code does not need to know the
    browser's ``type="submit"`` mechanic. Custom submit controls remain possible
    by composing an explicit :class:`Button` in ``children``.
    """

    tag = "form"
    style = "form"

    def __init__(
        self,
        *children: Any,
        on_submit: EventHandler | None = None,
        submit: str | None = None,
        submit_variant: str = "primary",
        disabled: bool = False,
        read_only: bool = False,
        loading: bool = False,
        error: bool | str = False,
        **kwargs: Any,
    ) -> None:
        unavailable = disabled or read_only or loading or bool(error)
        if submit is not None:
            children = (
                *children,
                Button(
                    submit,
                    type="submit",
                    variant=submit_variant,
                    disabled=unavailable,
                ),
            )
        super().__init__(*children, **kwargs)
        if unavailable:
            self.attrs["aria-disabled"] = "true"
        if read_only:
            self.attrs["aria-readonly"] = "true"
        if loading:
            self.attrs["aria-busy"] = "true"
        if error:
            self.attrs["aria-invalid"] = "true"
            self.attrs["data-vd-state"] = "error"
            if isinstance(error, str):
                self.attrs["data-vd-error"] = error
        if on_submit is not None and not unavailable:
            _event_attr(self, "submit", on_submit)
        self.props = {
            "disabled": disabled,
            "read_only": read_only,
            "loading": loading,
            "error": error,
        }


class Input(Component):
    tag = "input"
    style: str | None = "input"

    def __init__(
        self,
        *children: Any,
        on_change: EventHandler | None = None,
        on_input: EventHandler | None = None,
        size: str | None = None,
        disabled: bool = False,
        read_only: bool = False,
        loading: bool = False,
        error: bool | str = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(*children, **kwargs)
        unavailable = disabled or read_only or loading
        if not unavailable:
            _event_attr(self, "change", on_change)
            _event_attr(self, "input", on_input)
        self.attrs.setdefault("type", "text")
        if self.attrs["type"] in ("checkbox", "radio", "hidden"):
            self.style = None
        self.props = {
            "size": size,
            **_control_state(
                self,
                disabled=disabled,
                read_only=read_only,
                loading=loading,
                error=error,
            ),
        }


class Textarea(Component):
    tag = "textarea"
    style = "textarea"

    def __init__(
        self,
        *children: Any,
        on_change: EventHandler | None = None,
        on_input: EventHandler | None = None,
        disabled: bool = False,
        read_only: bool = False,
        loading: bool = False,
        error: bool | str = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(*children, **kwargs)
        unavailable = disabled or read_only or loading
        if not unavailable:
            _event_attr(self, "change", on_change)
            _event_attr(self, "input", on_input)
        self.props = _control_state(
            self,
            disabled=disabled,
            read_only=read_only,
            loading=loading,
            error=error,
        )


class Select(Component):
    tag = "select"
    style = "select"

    def __init__(
        self,
        *children: Any,
        on_change: EventHandler | None = None,
        disabled: bool = False,
        read_only: bool = False,
        loading: bool = False,
        error: bool | str = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(*children, **kwargs)
        if not (disabled or read_only or loading):
            _event_attr(self, "change", on_change)
        self.props = _control_state(
            self,
            disabled=disabled,
            read_only=read_only,
            loading=loading,
            error=error,
        )


class Checkbox(Input):
    def __init__(
        self,
        *children: Any,
        on_change: EventHandler | None = None,
        disabled: bool = False,
        read_only: bool = False,
        loading: bool = False,
        error: bool | str = False,
        **kwargs: Any,
    ) -> None:
        kwargs["type"] = "checkbox"
        super().__init__(
            *children,
            on_change=on_change,
            disabled=disabled,
            read_only=read_only,
            loading=loading,
            error=error,
            **kwargs,
        )
        self.style = "checkbox"


class Radio(Input):
    def __init__(
        self,
        *children: Any,
        on_change: EventHandler | None = None,
        disabled: bool = False,
        read_only: bool = False,
        loading: bool = False,
        error: bool | str = False,
        **kwargs: Any,
    ) -> None:
        kwargs["type"] = "radio"
        super().__init__(
            *children,
            on_change=on_change,
            disabled=disabled,
            read_only=read_only,
            loading=loading,
            error=error,
            **kwargs,
        )
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
        read_only: bool = False,
        loading: bool = False,
        error: bool | str = False,
        **kwargs: Any,
    ) -> None:
        unavailable = disabled or read_only or loading or bool(error)
        state_attrs: dict[str, Any] = {}
        if unavailable:
            state_attrs["aria_disabled"] = "true"
        if read_only:
            state_attrs["aria_readonly"] = "true"
        if loading:
            state_attrs["aria_busy"] = "true"
        if error:
            state_attrs["aria_invalid"] = "true"
            if isinstance(error, str):
                state_attrs["data_vd_error"] = error
        super().__init__(**state_attrs, **kwargs)
        self._binding = bind_event(on_send) if not unavailable else None
        self._placeholder = placeholder
        self._unavailable = unavailable
        self.props = {
            "disabled": disabled,
            "read_only": read_only,
            "loading": loading,
            "error": error,
        }

    def render(self) -> str:
        disabled_attr = " disabled" if self._unavailable else ""
        binding_attrs = (
            f'data-vd-enter-send="{escape(self._binding)}"'
            if self._binding
            else ""
        )
        trigger_attrs = (
            f'data-vd-enter-send-trigger="{escape(self._binding)}"'
            if self._binding
            else ""
        )
        return (
            f"<div{self._render_attrs()}>"
            f'<textarea class="vd-composer-input" rows="1" '
            f'placeholder="{escape(self._placeholder)}" '
            f"{binding_attrs}{disabled_attr}></textarea>"
            f'<button type="button" class="vd-composer-send" '
            f"{trigger_attrs}{disabled_attr}>"
            f"{Icon('send').render()}</button>"
            "</div>"
        )


class ThemeToggle(Component):
    """Theme control using a Voodoo client action rather than inline JS."""

    tag = "button"
    style = "theme-toggle"

    def __init__(
        self,
        label: str = "Toggle theme",
        *,
        disabled: bool = False,
        read_only: bool = False,
        loading: bool = False,
        error: bool | str = False,
        **kwargs: Any,
    ) -> None:
        unavailable = disabled or read_only or loading or bool(error)
        state_attrs: dict[str, Any] = {}
        if unavailable:
            state_attrs["disabled"] = True
            state_attrs["aria_disabled"] = "true"
        if read_only:
            state_attrs["aria_readonly"] = "true"
        if loading:
            state_attrs["aria_busy"] = "true"
        if error:
            state_attrs["aria_invalid"] = "true"
            if isinstance(error, str):
                state_attrs["data_vd_error"] = error
        super().__init__(**state_attrs, **kwargs)
        self.attrs["type"] = "button"
        self.attrs["aria-label"] = label
        if not unavailable:
            self.attrs["data-vd-action"] = "toggle-theme"
        self.children = (
            Text("☀", class_="vd-theme-toggle-sun"),
            Text("☾", class_="vd-theme-toggle-moon"),
        )
        self.props = {
            "disabled": disabled,
            "read_only": read_only,
            "loading": loading,
            "error": error,
        }
