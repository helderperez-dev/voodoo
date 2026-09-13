"""Semantic layout primitives layered on the stable Voodoo layout model."""

from __future__ import annotations

from typing import Any

from voodoo.ui.library import Page as _Page


class Page(_Page):
    """Primary application page surface.

    ``density`` changes the rhythm of first-party controls without requiring a
    second component set or application CSS. ``comfortable`` is the default;
    operational dashboards can opt into ``compact``.
    """

    def __init__(
        self,
        *children: Any,
        size: str = "lg",
        pad: bool = True,
        density: str = "comfortable",
        **kwargs: Any,
    ) -> None:
        if density not in {"comfortable", "compact"}:
            raise ValueError("Page density must be 'comfortable' or 'compact'")
        super().__init__(*children, size=size, pad=pad, **kwargs)
        self.props["density"] = density
        if density != "comfortable":
            self.attrs["data-vd-density"] = density
