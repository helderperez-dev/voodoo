"""Foundational components for polished application interfaces.

These primitives cover feedback, navigation, disclosure and small content
patterns. Their APIs stay semantic while leaning on native HTML behavior for
accessibility and progressive enhancement.
"""

from __future__ import annotations

import math
import re
from typing import Any

from voodoo.ui.component import Component

_TONES = frozenset({"primary", "info", "success", "warning", "danger"})
_SIZES = frozenset({"sm", "md", "lg"})


def _choice(component: str, prop: str, value: str, allowed: frozenset[str]) -> str:
    if value not in allowed:
        raise ValueError(
            f"invalid {component} {prop} {value!r}; expected one of {sorted(allowed)}"
        )
    return value


class Alert(Component):
    """A contextual message with optional title and semantic tone."""

    style = "alert"

    def __init__(
        self,
        *children: Any,
        title: Any | None = None,
        tone: str = "info",
        variant: str = "soft",
        **kwargs: Any,
    ) -> None:
        tone = _choice("Alert", "tone", tone, _TONES)
        variant = _choice(
            "Alert", "variant", variant, frozenset({"soft", "outline", "solid"})
        )
        super().__init__(**kwargs)
        self.props = {"tone": tone, "variant": variant}

        if title:
            self.children = (_AlertTitle(title), _AlertContent(*children))
        else:
            self.children = (_AlertContent(*children),)


class _AlertTitle(Component):
    tag = "div"
    style = "alert.title"
    auto_id = False


class _AlertContent(Component):
    tag = "div"
    style = "alert.content"
    auto_id = False


class Progress(Component):
    """A determinate or indeterminate task progress indicator."""

    tag = "progress"
    style = "progress"

    def __init__(
        self,
        value: float | None = None,
        *,
        max: float = 100,
        label: str = "Progress",
        tone: str = "primary",
        size: str = "md",
        **kwargs: Any,
    ) -> None:
        if not math.isfinite(max) or max <= 0:
            raise ValueError("Progress max must be finite and greater than zero")
        if value is not None and (not math.isfinite(value) or not 0 <= value <= max):
            raise ValueError("Progress value must be between zero and max")
        tone = _choice("Progress", "tone", tone, _TONES)
        size = _choice("Progress", "size", size, _SIZES)
        super().__init__(aria_label=label, max=max, **kwargs)
        if value is not None:
            self.attrs["value"] = value
        self.props = {"tone": tone, "size": size}


class Spinner(Component):
    """Compact loading status with a screen-reader label."""

    tag = "span"
    style = "spinner"

    def __init__(
        self,
        label: str = "Loading",
        *,
        size: str = "md",
        **kwargs: Any,
    ) -> None:
        size = _choice("Spinner", "size", size, _SIZES)
        super().__init__(role="status", aria_live="polite", **kwargs)
        self.props = {"size": size}
        self.children = (_SpinnerGlyph(), _VisuallyHidden(label))


class _SpinnerGlyph(Component):
    tag = "span"
    style = "spinner.glyph"
    auto_id = False


class _VisuallyHidden(Component):
    tag = "span"
    style = "visually-hidden"
    auto_id = False


class Breadcrumb(Component):
    """A navigation trail composed from :class:`BreadcrumbItem` objects."""

    tag = "nav"
    style = "breadcrumb"

    def __init__(
        self,
        *items: BreadcrumbItem,
        label: str = "Breadcrumb",
        **kwargs: Any,
    ) -> None:
        if not items:
            raise ValueError("Breadcrumb requires at least one item")
        super().__init__(aria_label=label, **kwargs)
        normalized = tuple(
            item if isinstance(item, BreadcrumbItem) else BreadcrumbItem(str(item))
            for item in items
        )
        if not any(item.current for item in normalized):
            normalized[-1].set_current()
        self.children = (_BreadcrumbList(*normalized),)


class _BreadcrumbList(Component):
    tag = "ol"
    style = "breadcrumb.list"
    auto_id = False


class BreadcrumbItem(Component):
    """One breadcrumb destination or the current page."""

    tag = "li"
    style = "breadcrumb.item"

    def __init__(
        self,
        label: str,
        href: str | None = None,
        *,
        current: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.current = current
        self.label = label
        self.href = href
        self._sync_content()

    def set_current(self) -> None:
        self.current = True
        self._sync_content()

    def _sync_content(self) -> None:
        if self.current or not self.href:
            self.children = (

            )
        else:
            self.children = (_BreadcrumbLink(self.label, href=self.href),)


class _BreadcrumbLink(Component):
    tag = "a"
    style = "breadcrumb.link"
    auto_id = False


class _BreadcrumbCurrent(Component):
    tag = "span"
    style = "breadcrumb.current"
    auto_id = False


class ButtonGroup(Component):
    """Visually and semantically groups related actions."""

    style = "button-group"

    def __init__(
        self,
        *buttons: Component,
        label: str = "Actions",
        orientation: str = "horizontal",
        attached: bool = True,
        **kwargs: Any,
    ) -> None:
        orientation = _choice(
            "ButtonGroup",
            "orientation",
            orientation,
            frozenset({"horizontal", "vertical"}),
        )
        if not buttons:
            raise ValueError("ButtonGroup requires at least one button")
        if not all(isinstance(button, Component) for button in buttons):
            raise TypeError("ButtonGroup children must be Component instances")
        super().__init__(*buttons, role="group", aria_label=label, **kwargs)
        self.props = {"orientation": orientation, "attached": attached}


class Accordion(Component):
    """A set of native disclosure sections."""

    style = "accordion"

    def __init__(
        self,
        *items: AccordionItem,
        variant: str = "separated",
        **kwargs: Any,
    ) -> None:
        variant = _choice(
            "Accordion",
            "variant",
            variant,
            frozenset({"separated", "contained", "ghost"}),
        )
        if not items:
            raise ValueError("Accordion requires at least one AccordionItem")
        if not all(isinstance(item, AccordionItem) for item in items):
            raise TypeError("Accordion children must be AccordionItem instances")
        super().__init__(*items, **kwargs)
        self.props = {"variant": variant}


class AccordionItem(Component):
    """One keyboard-accessible disclosure section."""

    tag = "details"
    style = "accordion.item"

    def __init__(
        self,
        title: Any,
        *children: Any,
        open: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(open=open, **kwargs)
        self.children = (_AccordionSummary(title), _AccordionContent(*children))


class _AccordionSummary(Component):
    tag = "summary"
    style = "accordion.summary"
    auto_id = False


class _AccordionContent(Component):
    tag = "div"
    style = "accordion.content"
    auto_id = False


class Kbd(Component):
    """Keyboard input or shortcut hint."""

    tag = "kbd"
    style = "kbd"


class AspectRatio(Component):
    """Keeps media or arbitrary content at a stable width-to-height ratio."""

    style = "aspect-ratio"
    _RATIO = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*[/\:]\s*(\d+(?:\.\d+)?)\s*$")

    def __init__(
        self,
        child: Component,
        *,
        ratio: str = "16/9",
        **kwargs: Any,
    ) -> None:
        match = self._RATIO.fullmatch(ratio)
        if not match or float(match.group(1)) <= 0 or float(match.group(2)) <= 0:

        super().__init__(child, **kwargs)



__all__ = [
    "Accordion",
    "AccordionItem",
    "Alert",
    "AspectRatio",
    "Breadcrumb",
    "BreadcrumbItem",
    "ButtonGroup",
    "Kbd",
    "Progress",
    "Spinner",
]
