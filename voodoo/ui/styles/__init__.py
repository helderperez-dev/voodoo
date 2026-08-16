"""StyleAdapter contract.

Components never embed CSS framework classes. They declare a semantic style
key (``"button"``, ``"card"``, ``"table.cell"``) plus props; the active
adapter resolves that to a concrete class string. Swapping Voodoo CSS for
Tailwind (or anything else) means implementing this protocol once —
components and apps do not change.

The default adapter (:class:`~voodoo.adapters.voodoo_css.VoodooCSSAdapter`) is
installed at import time. To use Tailwind instead::

    from voodoo import TailwindAdapter, set_style_adapter
    set_style_adapter(TailwindAdapter())
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from voodoo.theme import Theme


@runtime_checkable
class StyleAdapter(Protocol):
    def component_classes(
        self, component: str, props: dict[str, Any], theme: Theme
    ) -> str:
        """Return the class string for a semantic component style.

        Args:
            component: Semantic style key (e.g. ``"button"``, ``"table.cell"``).
            props: Semantic props (``variant``, ``size``, ``level``, …) plus
                ``class_`` holding the developer-supplied classes.
            theme: The active theme (for token-driven styling).
        """
        ...


class NoopAdapter:
    """Minimal adapter: no framework classes, ``class_`` passes through."""

    def component_classes(
        self, component: str, props: dict[str, Any], theme: Theme
    ) -> str:
        return ""


_adapter: StyleAdapter


def set_style_adapter(adapter: StyleAdapter) -> None:
    """Install a global style adapter (affects all subsequent renders)."""
    global _adapter
    _adapter = adapter


def current_adapter() -> StyleAdapter:
    return _adapter


def _install_default() -> None:
    from voodoo.adapters.voodoo_css import VoodooCSSAdapter

    set_style_adapter(VoodooCSSAdapter())


_install_default()
