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
        error: str | None = None,
        required: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        control_id = control.id or f"vd-field-{uuid4().hex[:8]}"
        control.attrs["id"] = control_id
        if error:
            control.attrs["aria-invalid"] = "true"
        described_by: list[str] = []
        hint_id = f"{control_id}-hint"
        error_id = f"{control_id}-error"
        if hint:
            described_by.append(hint_id)
        if error:
            described_by.append(error_id)
        if described_by:
            control.attrs["aria-describedby"] = " ".join(described_by)
        if required:
            control.attrs["required"] = True

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
        if error:
            pieces.append(
                f'<div id="{escape(error_id)}" class="vd-field-error" role="alert">'
                f"{escape(error)}</div>"
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
        if disabled:
            attrs.append("disabled")
        if on_change is not None:
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
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        popover_id = f"{self.id}-panel" if self.id else f"vd-pop-{uuid4().hex[:8]}"
        trigger.attrs["popovertarget"] = popover_id
        trigger.attrs.setdefault("aria-haspopup", "dialog")
        panel = _PopoverPanel(
            *content,
            id=popover_id,
            popover=True,
            data_placement=placement,
        )
        self.children = (trigger, panel)


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
