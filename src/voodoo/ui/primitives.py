"""High-level Voodoo UI primitives with excellent defaults.

These components intentionally expose semantic application concepts rather
than browser mechanics. They compose the existing Component model and native
browser capabilities, keeping JavaScript out of application code.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import uuid4

from voodoo.ui.component import Component, escape
from voodoo.ui.events import bind_event

EventHandler = Callable[..., Any] | str


def _first_native_control(component: Component) -> Component | None:
    """Find the first labelable native control in a composite component."""
    if component.tag in {"input", "select", "textarea"}:
        return component
    for child in component.children:
        if isinstance(child, Component):
            control = _first_native_control(child)
            if control is not None:
                return control
    return None


def _apply_field_state(
    target: Component,
    *,
    disabled: bool,
    read_only: bool,
    loading: bool,
    error: bool | str,
) -> tuple[bool, str | None]:
    unavailable = disabled or read_only or loading
    if unavailable:
        target.attrs["disabled"] = True
        target.attrs["aria_disabled"] = "true"
        for event_key in (
            "data_vd_event_change",
            "data-vd-event-change",
            "data_vd_event_input",
            "data-vd-event-input",
        ):
            target.attrs.pop(event_key, None)
    if read_only:
        target.attrs["readonly"] = True
        target.attrs["aria_readonly"] = "true"
    if loading:
        target.attrs["aria_busy"] = "true"
    error_text = error if isinstance(error, str) else None
    if error:
        target.attrs["aria-invalid"] = "true"
        if error_text:
            target.attrs["data-vd-error"] = error_text
    return unavailable, error_text


class Field(Component):
    """A complete form field: label, control, hint and error in one component.

    Example::

        Field("Email", Input(name="email"), hint="Work email")
    """

    style = "field"

    def __init__(
        self,
        label: str,
        control: Component,
        *,
        hint: str | None = None,
        error: bool | str = False,
        required: bool = False,
        disabled: bool = False,
        read_only: bool = False,
        loading: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        native_control = _first_native_control(control)
        target = native_control or control
        control_id = target.id or f"vd-field-{uuid4().hex[:8]}"
        target.attrs["id"] = control_id
        unavailable, error_text = _apply_field_state(
            target,
            disabled=disabled,
            read_only=read_only,
            loading=loading,
            error=error,
        )
        self.attrs.update(
            {
                "aria_disabled": "true" if unavailable else None,
                "aria_readonly": "true" if read_only else None,
                "aria_busy": "true" if loading else None,
                "aria_invalid": "true" if error else None,
            }
        )
        described_by: list[str] = []
        hint_id = f"{control_id}-hint"
        error_id = f"{control_id}-error"
        if hint:
            described_by.append(hint_id)
        if error_text:
            described_by.append(error_id)
        if described_by:
            target.attrs["aria-describedby"] = " ".join(described_by)
        if required:
            target.attrs["required"] = True

        self.props = {
            "disabled": disabled,
            "read_only": read_only,
            "loading": loading,
            "error": error,
        }

        label_suffix = ' <span aria-hidden="true">*</span>' if required else ""
        pieces = [
            f'<label class="vd-field-label" for="{escape(control_id)}">'
            f"{escape(label)}{label_suffix}</label>",
            '<div class="vd-field-control">',
            control.render(),
            "</div>",
        ]
        if hint:
            pieces.append(
                f'<div id="{escape(hint_id)}" class="vd-field-hint">{escape(hint)}</div>'
            )
        if error_text:
            pieces.append(
                f'<div id="{escape(error_id)}" class="vd-field-error" role="alert">'
                f"{escape(error_text)}</div>"
            )
        self._markup = "".join(pieces)

    def render(self) -> str:
        return f"<div{self._render_attrs()}>{self._markup}</div>"


class Switch(Component):
    """Accessible boolean control with a Python-callable ``on_change`` handler."""

    style = "switch"

    def __init__(
        self,
        label: str | None = None,
        *,
        checked: bool = False,
        disabled: bool = False,
        read_only: bool = False,
        loading: bool = False,
        error: bool | str = False,
        on_change: EventHandler | None = None,
        description: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        input_id = f"{self.id}-input" if self.id else f"vd-switch-{uuid4().hex[:8]}"
        aria_checked = "true" if checked else "false"
        attrs = [
            f'id="{escape(input_id)}"',
            'type="checkbox"',
            'role="switch"',
            f'aria-checked="{aria_checked}"',
            'class="vd-switch-input"',
        ]
        if checked:
            attrs.append("checked")
        if disabled or read_only or loading:
            attrs.append("disabled")
        if read_only:
            attrs.append('aria-readonly="true"')
        if loading:
            attrs.extend(['aria-busy="true"', 'data-vd-loading="true"'])
        if error:
            attrs.extend(['aria-invalid="true"', 'data-vd-state="error"'])
        # Keep the transport contract aligned with the native control state:
        # unavailable switches must not expose an event binding that can be
        # invoked through the client event bridge.
        if on_change is not None and not (disabled or read_only or loading):
            attrs.append(f'data-vd-event-change="{escape(bind_event(on_change))}"')

        label_html = ""
        if label:
            description_html = (
                f'<span class="vd-switch-description">{escape(description)}</span>'
                if description
                else ""
            )
            label_html = (
                f'<label class="vd-switch-copy" for="{escape(input_id)}">'
                f'<span class="vd-switch-label">{escape(label)}</span>'
                f"{description_html}</label>"
            )
        self._markup = (
            f"<input {' '.join(attrs)}>"
            f'<label class="vd-switch-track" for="{escape(input_id)}">'
            f'<span class="vd-switch-thumb" aria-hidden="true"></span></label>'
            f"{label_html}"
        )

    def render(self) -> str:
        return f"<div{self._render_attrs()}>{self._markup}</div>"


class Tooltip(Component):
    """Concise contextual help with keyboard-accessible semantics."""

    style = "tooltip"

    def __init__(self, child: Component, content: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        tooltip_id = f"{self.id}-content" if self.id else f"vd-tip-{uuid4().hex[:8]}"
        existing = child.attrs.get("aria-describedby")
        child.attrs["aria-describedby"] = (
            f"{existing} {tooltip_id}" if existing else tooltip_id
        )
        if child.attrs.get("tabindex") is None and child.tag not in {
            "button",
            "a",
            "input",
            "select",
            "textarea",
        }:
            child.attrs["tabindex"] = "0"
        self._markup = (
            f'<span class="vd-tooltip-anchor">{child.render()}</span>'
            f'<span id="{escape(tooltip_id)}" role="tooltip" '
            f'class="vd-tooltip-content">{escape(content)}</span>'
        )

    def render(self) -> str:
        return f"<span{self._render_attrs()}>{self._markup}</span>"


class Popover(Component):
    """Native, progressively enhanced contextual surface.

    ``trigger`` can be any Component. Voodoo wires the browser's native
    popover target relationship automatically.
    """

    style = "popover-shell"

    def __init__(
        self,
        trigger: Component,
        *content: Any,
        placement: str = "bottom-start",
        disabled: bool = False,
        read_only: bool = False,
        loading: bool = False,
        error: bool | str = False,
        **kwargs: Any,
    ) -> None:
        unavailable = disabled or read_only or loading or bool(error)
        super().__init__(**kwargs)
        popover_id = f"{self.id}-panel" if self.id else f"vd-pop-{uuid4().hex[:8]}"
        if not unavailable:
            trigger.attrs["popovertarget"] = popover_id
        else:
            trigger.attrs["aria-disabled"] = "true"
            trigger.attrs["disabled"] = True
        if read_only:
            trigger.attrs["aria-readonly"] = "true"
        if loading:
            trigger.attrs["aria-busy"] = "true"
        if error:
            trigger.attrs["aria-invalid"] = "true"
            if isinstance(error, str):
                trigger.attrs["data-vd-error"] = error
        trigger.attrs.setdefault("aria-haspopup", "dialog")
        panel = _PopoverPanel(
            *content,
            id=popover_id,
            popover=True,
            data_placement=placement,
            aria_disabled="true" if unavailable else None,
            aria_busy="true" if loading else None,
            aria_invalid="true" if error else None,
            data_vd_error=error if isinstance(error, str) else None,
        )
        self.children = (trigger, panel)
        self.props = {
            "disabled": disabled,
            "read_only": read_only,
            "loading": loading,
            "error": error,
        }


class _PopoverPanel(Component):
    tag = "div"
    style = "popover"
    auto_id = False


class Skeleton(Component):
    """Layout-preserving loading placeholder."""

    style = "skeleton"

    def __init__(
        self,
        *,
        width: str | None = None,
        height: str | None = None,
        lines: int = 1,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        styles: list[str] = []
        if width:
            styles.append(f"width:{width}")
        if height:
            styles.append(f"height:{height}")
        if styles:
            self.attrs["style"] = ";".join(styles)
        self.attrs["aria-hidden"] = "true"
        self.children = tuple(
            _SkeletonLine(class_=f"vd-skeleton-line vd-skeleton-line--{i + 1}")
            for i in range(max(1, lines))
        )


class _SkeletonLine(Component):
    tag = "span"
    auto_id = False
