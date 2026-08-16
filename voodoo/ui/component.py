"""The Voodoo component model.

Every UI element — built-in or user-defined — renders through ONE code path:
:class:`Component.render`. Styling never lives in component definitions; a
component declares a semantic style key (e.g. ``"button"``) plus props, and
the active :class:`~voodoo.ui.styles.StyleAdapter` resolves the class string.

Guarantees provided by the base:

- **Child flattening** — ``str | int | float | Component | None | iterable``
  are all valid children and are flattened recursively.
- **Attribute pipeline** — ``class_`` / ``className`` merge into ``class``,
  ``for_`` → ``for``, ``aria_label`` → ``aria-label``, ``data_x`` / ``data-x``
  → ``data-x``; ``True`` renders a bare attribute; ``None``/``False`` omit.
- **Escaping** — text children and attribute values are HTML-escaped. Event
  handler attributes (``on*``, framework-generated) and :class:`Html` content
  are the only trusted paths.
"""

from __future__ import annotations

import html
from collections.abc import Iterable
from typing import Any, ClassVar
from uuid import uuid4

SELF_CLOSING_TAGS = frozenset({"input", "img", "br", "hr"})


def escape(value: Any) -> str:
    """Escape a value for safe interpolation into HTML text or attributes."""
    return html.escape(str(value), quote=True)


def _attr_name(key: str) -> str:
    if key == "className" or key == "class_":
        return "class"
    return key.replace("_", "-")


def _flatten(children: tuple[Any, ...]) -> tuple[Any, ...]:
    """Recursively flatten iterables and drop None values."""
    flat: list[Any] = []
    for child in children:
        if child is None:
            continue
        if isinstance(child, (str, int, float, Component)):  # noqa: UP038
            flat.append(child)
        elif isinstance(child, Iterable):
            flat.extend(_flatten(tuple(child)))
        else:
            flat.append(child)
    return tuple(flat)


class Component:
    """Base class for all rendered UI elements."""

    tag: str = "div"
    #: Semantic style key resolved by the active StyleAdapter (None = unstyled).
    style: str | None = None
    #: Generate a random element id when none is provided (needed for WS patches).
    auto_id: ClassVar[bool] = True

    def __init__(
        self,
        *children: Any,
        id: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.children: tuple[Any, ...] = _flatten(children)
        self.props: dict[str, Any] = {}
        self.attrs: dict[str, Any] = {}
        if id is None and self.auto_id:
            id = f"vd-{uuid4().hex[:8]}"
        if id is not None:
            self.attrs["id"] = id
        self.attrs.update(kwargs)

    # -- public API ----------------------------------------------------------

    def render(self) -> str:
        """Serialize this component (and its subtree) to HTML."""
        attrs = self._render_attrs()
        inner = self._render_children()
        if self.tag in SELF_CLOSING_TAGS:
            return f"<{self.tag}{attrs} />"
        return f"<{self.tag}{attrs}>{inner}</{self.tag}>"

    def __str__(self) -> str:
        return self.render()

    @property
    def id(self) -> str | None:
        """The element id (auto-generated when ``auto_id`` is set)."""
        return self.attrs.get("id")

    # -- internals -----------------------------------------------------------

    def user_class(self) -> str:
        """The developer-supplied class string (``class_`` / ``className``)."""
        parts = [
            str(self.attrs[key])
            for key in ("class_", "className")
            if self.attrs.get(key)
        ]
        return " ".join(parts)

    def framework_classes(self, user_class: str = "") -> str:
        """Classes contributed by the active style adapter for this style key."""
        if self.style is None:
            return ""
        from voodoo.theme import default_theme
        from voodoo.ui.styles import current_adapter

        props = {**self.props, "class_": user_class}
        return current_adapter().component_classes(self.style, props, default_theme)

    def _render_attrs(self) -> str:
        """Build the attribute string.

        For styled components the merged class (framework + user) renders
        last; plain components keep ``class`` at its declared position.
        """
        user_class = self.user_class() if self.style is not None else ""
        framework = self.framework_classes(user_class) if self.style is not None else ""
        merged = " ".join(part for part in (framework, user_class) if part)

        rendered: list[str] = []
        for key, value in self.attrs.items():
            name = _attr_name(key)
            if name == "class":
                if self.style is not None:
                    continue  # merged class is emitted last
                if value:
                    rendered.append(f'class="{escape(value)}"')
                continue
            if value is None or value is False:
                continue
            if value is True:
                rendered.append(name)
                continue
            if name.startswith("on"):
                # Event handlers are framework-generated JS — emitted verbatim.
                rendered.append(f'{name}="{value}"')
            else:
                rendered.append(f'{name}="{escape(value)}"')

        if merged:
            rendered.append(f'class="{escape(merged)}"')

        return f" {' '.join(rendered)}" if rendered else ""

    def _render_children(self) -> str:
        return "".join(
            child.render() if isinstance(child, Component) else escape(child)
            for child in self.children
        )


class Html(Component):
    """Escape hatch: renders children as pre-built HTML without escaping."""

    auto_id: ClassVar[bool] = False

    def render(self) -> str:
        return self._render_children()

    def _render_children(self) -> str:
        return "".join(
            child.render() if isinstance(child, Component) else str(child)
            for child in self.children
        )
