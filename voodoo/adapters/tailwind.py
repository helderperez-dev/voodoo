"""The default Tailwind adapter.

This module is the ONLY place in the framework that knows Tailwind class
syntax. Components declare semantic style keys; this adapter maps them to
concrete utility classes, reproducing the historical default look
byte-for-byte while adding themed ``variant``/``size`` props.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from voodoo.theme import Theme

# ---------------------------------------------------------------------------
# Buttons — legacy default kept byte-identical; semantic variants opt-in
# ---------------------------------------------------------------------------

_BTN_DEFAULT = (
    "inline-flex items-center justify-center rounded-md text-sm font-medium "
    "transition-colors focus-visible:outline-none focus-visible:ring-1 "
    "focus-visible:ring-[var(--color-primary)] disabled:pointer-events-none "
    "disabled:opacity-50 bg-[var(--color-text)] text-[var(--color-surface)] "
    "hover:bg-[var(--color-text)]/90 h-9 px-4 py-2"
)

_BTN_BASE = (
    "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md "
    "text-sm font-medium transition-colors focus-visible:outline-none "
    "focus-visible:ring-1 focus-visible:ring-[var(--color-primary)] "
    "disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none "
    "[&_svg]:size-4 [&_svg]:shrink-0"
)

_BTN_SIZES = {
    "sm": "h-8 px-3 text-xs",
    "md": "h-9 px-4 py-2",
    "lg": "h-10 px-6 text-base",
}

_BTN_VARIANTS = {
    "primary": (
        "bg-[var(--color-primary)] text-white "
        "hover:bg-[var(--color-primary-hover)] cursor-pointer"
    ),
    "secondary": (
        "bg-[var(--color-secondary)] text-white hover:opacity-90 cursor-pointer"
    ),
    "outline": (
        "border border-[var(--color-border)] bg-transparent "
        "text-[var(--color-text)] hover:bg-[var(--color-surface)] cursor-pointer"
    ),
    "ghost": (
        "bg-transparent text-[var(--color-text-muted)] "
        "hover:bg-[var(--color-surface)] hover:text-[var(--color-text)] "
        "cursor-pointer"
    ),
    "danger": ("bg-[var(--color-danger)] text-white hover:opacity-90 cursor-pointer"),
}

# Legacy "already styled" heuristic: if the developer supplied background /
# border / hover classes, the framework stays out of the way.
_BTN_MARKERS = ("bg-", "border", "hover:")

# ---------------------------------------------------------------------------
# Forms — legacy defaults kept byte-identical
# ---------------------------------------------------------------------------

_INPUT_DEFAULT = (
    "flex h-9 w-full rounded-md border border-[var(--color-border)] "
    "bg-transparent px-3 py-1 text-sm shadow-sm transition-colors "
    "file:border-0 file:bg-transparent file:text-sm file:font-medium "
    "placeholder:text-[var(--color-text-muted)] focus-visible:outline-none "
    "focus-visible:ring-1 focus-visible:ring-[var(--color-primary)] "
    "disabled:cursor-not-allowed disabled:opacity-50"
)

_INPUT_SIZES = {
    "sm": ("h-8", "px-2.5 py-1"),
    "md": ("h-9", "px-3 py-1"),
    "lg": ("h-11", "px-4 py-2"),
}

_TEXTAREA_DEFAULT = (
    "flex min-h-[80px] w-full rounded-md border border-[var(--color-border)] "
    "bg-transparent px-3 py-2 text-sm shadow-sm "
    "placeholder:text-[var(--color-text-muted)] focus-visible:outline-none "
    "focus-visible:ring-1 focus-visible:ring-[var(--color-primary)] "
    "disabled:cursor-not-allowed disabled:opacity-50"
)

_SELECT_DEFAULT = (
    "flex h-9 w-full items-center justify-between rounded-md border "
    "border-[var(--color-border)] bg-transparent px-3 py-2 text-sm shadow-sm "
    "ring-offset-[var(--color-surface)] "
    "placeholder:text-[var(--color-text-muted)] focus:outline-none "
    "focus:ring-1 focus:ring-[var(--color-primary)] "
    "disabled:cursor-not-allowed disabled:opacity-50"
)

_LABEL_DEFAULT = (
    "block text-sm font-medium leading-none text-[var(--color-text)] "
    "peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
)

_CHECKBOX_DEFAULT = (
    "peer h-4 w-4 shrink-0 rounded-sm border border-[var(--color-border)] "
    "ring-offset-[var(--color-surface)] focus-visible:outline-none "
    "focus-visible:ring-2 focus-visible:ring-[var(--color-primary)] "
    "focus-visible:ring-offset-2 disabled:cursor-not-allowed "
    "disabled:opacity-50 data-[state=checked]:bg-[var(--color-primary)] "
    "data-[state=checked]:text-[var(--color-surface)]"
)

_RADIO_DEFAULT = (
    "aspect-square h-4 w-4 rounded-full border border-[var(--color-border)] "
    "text-[var(--color-primary)] ring-offset-[var(--color-surface)] "
    "focus:outline-none focus-visible:ring-2 "
    "focus-visible:ring-[var(--color-primary)] "
    "focus-visible:ring-offset-2 disabled:cursor-not-allowed "
    "disabled:opacity-50"
)

# ---------------------------------------------------------------------------
# Display — legacy defaults kept byte-identical
# ---------------------------------------------------------------------------

_BADGE_BASE = (
    "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold "
    "transition-colors focus:outline-none focus:ring-2 "
    "focus:ring-[var(--color-primary)]"
)

_BADGE_VARIANTS = {
    "default": (
        "bg-[var(--color-text)] text-[var(--color-surface)] "
        "hover:bg-[var(--color-text)]/80"
    ),
    "secondary": (
        "bg-[var(--color-surface)] text-[var(--color-text)] border "
        "border-[var(--color-border)] hover:bg-[var(--color-surface)]/80"
    ),
    "outline": "text-[var(--color-text)] border border-[var(--color-border)]",
    "success": "bg-[var(--color-success)] text-white",
    "warning": "bg-[var(--color-warning)] text-black",
    "danger": "bg-[var(--color-danger)] text-white",
}

_HEADING_LEVELS = {
    1: "text-4xl font-bold tracking-tight",
    2: "text-3xl font-semibold tracking-tight",
    3: "text-2xl font-semibold tracking-tight",
    4: "text-xl font-semibold tracking-tight",
}

_AVATAR_FALLBACK_DEFAULT = (
    "flex h-full w-full items-center justify-center rounded-full "
    "bg-[var(--color-surface)] border border-[var(--color-border)] "
    "text-[var(--color-text)] text-sm font-medium"
)

_DIALOG_DEFAULT = (
    "backdrop:bg-black/50 p-0 rounded-xl border border-[var(--color-border)] "
    "bg-[var(--color-surface)] shadow-2xl open:flex flex-col"
)

_DIVIDER_DEFAULT = "m-0 h-px w-full border-none bg-[var(--color-border)]"

_FLEX_DIRECTIONS = {
    "row": "flex-row",
    "col": "flex-col",
    "row-reverse": "flex-row-reverse",
    "col-reverse": "flex-col-reverse",
}
_FLEX_JUSTIFY = {"start", "end", "center", "between", "around", "evenly"}
_FLEX_ITEMS = {"start", "end", "center", "baseline", "stretch"}
_FLEX_WRAP = {
    "nowrap": "flex-nowrap",
    "wrap": "flex-wrap",
    "wrap-reverse": "flex-wrap-reverse",
}

_CONTAINER_SIZES = {
    "sm": "max-w-screen-sm",
    "md": "max-w-screen-md",
    "lg": "max-w-screen-lg",
    "xl": "max-w-screen-xl",
    "2xl": "max-w-screen-2xl",
    "full": "w-full",
}

_TABLE_HEAD = "bg-[var(--color-surface)] border-b border-[var(--color-border)]"
_TABLE_ROW = (
    "border-b border-[var(--color-border)] hover:bg-[var(--color-surface)] "
    "transition-colors"
)
_TABLE_HEADER_CELL = (
    "px-6 py-4 text-left text-xs font-medium text-[var(--color-text-muted)] "
    "uppercase tracking-wider"
)
_TABLE_CELL = "px-6 py-4 whitespace-nowrap text-sm text-[var(--color-text)]"


def _has_any(user: str, markers: tuple[str, ...]) -> bool:
    return any(marker in user for marker in markers)


# ---------------------------------------------------------------------------
# Style resolvers: (props, theme) -> framework class string
#
# Contract: with no semantic props, return the historical default string
# byte-for-byte. ``props["class_"]`` carries the developer-supplied classes
# and is appended by the renderer — resolvers never include it.
# ---------------------------------------------------------------------------


def _button(props: dict[str, Any], theme: Theme) -> str:
    variant = props.get("variant")
    if variant is None:
        return _BTN_DEFAULT
    size = props.get("size") or "md"
    classes = f"{_BTN_BASE} {_BTN_VARIANTS.get(variant, _BTN_VARIANTS['primary'])}"
    if size in _BTN_SIZES:
        classes = f"{classes} {_BTN_SIZES[size]}"
    return classes


def _input(props: dict[str, Any], theme: Theme) -> str:
    size = props.get("size")
    if size is None or size == "md":
        return _INPUT_DEFAULT
    height, padding = _INPUT_SIZES.get(size, _INPUT_SIZES["md"])
    return _INPUT_DEFAULT.replace("h-9", height).replace("px-3 py-1", padding)


def _textarea(props: dict[str, Any], theme: Theme) -> str:
    return _TEXTAREA_DEFAULT


def _select(props: dict[str, Any], theme: Theme) -> str:
    return _SELECT_DEFAULT


def _label(props: dict[str, Any], theme: Theme) -> str:
    return _LABEL_DEFAULT


def _checkbox(props: dict[str, Any], theme: Theme) -> str:
    return _CHECKBOX_DEFAULT


def _radio(props: dict[str, Any], theme: Theme) -> str:
    return _RADIO_DEFAULT


def _card(props: dict[str, Any], theme: Theme) -> str:
    user = str(props.get("class_") or "")
    parts: list[str] = []
    if "bg-" not in user:
        parts.append("bg-[var(--color-surface)]")
    if "border" not in user:
        parts.append("border border-[var(--color-border)]")
    parts.append("rounded-xl p-6 shadow-sm")
    return " ".join(parts)


def _heading(props: dict[str, Any], theme: Theme) -> str:
    user = str(props.get("class_") or "")
    if "text-" in user:
        return ""
    size = _HEADING_LEVELS.get(props.get("level"), "text-lg font-medium")
    return f"{size} text-[var(--color-text)]"


def _badge(props: dict[str, Any], theme: Theme) -> str:
    variant = props.get("variant") or "default"
    v_class = _BADGE_VARIANTS.get(variant, _BADGE_VARIANTS["default"])
    return f"{_BADGE_BASE} {v_class}"


def _avatar(props: dict[str, Any], theme: Theme) -> str:
    return "relative flex h-10 w-10 shrink-0 overflow-hidden rounded-full"


def _avatar_img(props: dict[str, Any], theme: Theme) -> str:
    return "aspect-square h-full w-full object-cover"


def _avatar_fallback(props: dict[str, Any], theme: Theme) -> str:
    return _AVATAR_FALLBACK_DEFAULT


def _divider(props: dict[str, Any], theme: Theme) -> str:
    return _DIVIDER_DEFAULT


def _dialog(props: dict[str, Any], theme: Theme) -> str:
    return _DIALOG_DEFAULT


def _modal(props: dict[str, Any], theme: Theme) -> str:
    return (
        "backdrop:bg-black/60 p-6 w-full max-w-lg rounded-2xl "
        "border border-[var(--color-border)] bg-[var(--color-surface)] "
        "shadow-2xl open:flex flex-col gap-4 text-[var(--color-text)] m-auto"
    )


def _list(props: dict[str, Any], theme: Theme) -> str:
    if props.get("unstyled"):
        return "list-none pl-0 space-y-1"
    marker = "list-decimal" if props.get("ordered") else "list-disc"
    return f"{marker} pl-6 space-y-1"


def _chatbox(props: dict[str, Any], theme: Theme) -> str:
    return "flex flex-col space-y-2 overflow-y-auto"


def _flex(props: dict[str, Any], theme: Theme) -> str:
    direction = _FLEX_DIRECTIONS.get(props.get("direction", "row"), "flex-row")
    justify = props.get("justify") or "start"
    justify = f"justify-{justify}" if justify in _FLEX_JUSTIFY else "justify-start"
    items = props.get("items") or "stretch"
    items = f"items-{items}" if items in _FLEX_ITEMS else "items-stretch"
    wrap = _FLEX_WRAP.get(props.get("wrap", "nowrap"), "flex-nowrap")
    gap = props.get("gap", "0")
    return f"flex {direction} {justify} {items} {wrap} gap-{gap}"


def _grid(props: dict[str, Any], theme: Theme) -> str:
    cols = props.get("cols", "1")
    gap = props.get("gap", "4")
    return f"grid grid-cols-{cols} gap-{gap}"


def _container(props: dict[str, Any], theme: Theme) -> str:
    size = _CONTAINER_SIZES.get(props.get("size", "xl"), "max-w-screen-xl")
    centered = " mx-auto" if props.get("centered", True) else ""
    return f"{size}{centered}".strip()


def _page(props: dict[str, Any], theme: Theme) -> str:
    size = _CONTAINER_SIZES.get(props.get("size", "lg"), "max-w-screen-lg")
    padding = " px-4 py-8" if props.get("pad", True) else ""
    return f"{size} mx-auto flex-1 w-full{padding}"


def _table_head(props: dict[str, Any], theme: Theme) -> str:
    return _TABLE_HEAD


def _table_row(props: dict[str, Any], theme: Theme) -> str:
    return _TABLE_ROW


def _table_header_cell(props: dict[str, Any], theme: Theme) -> str:
    return _TABLE_HEADER_CELL


def _table_cell(props: dict[str, Any], theme: Theme) -> str:
    return _TABLE_CELL


_STYLES: dict[str, Callable[[dict[str, Any], Theme], str]] = {
    "button": _button,
    "input": _input,
    "textarea": _textarea,
    "select": _select,
    "label": _label,
    "checkbox": _checkbox,
    "radio": _radio,
    "card": _card,
    "heading": _heading,
    "badge": _badge,
    "avatar": _avatar,
    "avatar.img": _avatar_img,
    "avatar.fallback": _avatar_fallback,
    "divider": _divider,
    "dialog": _dialog,
    "modal": _modal,
    "list": _list,
    "chatbox": _chatbox,
    "flex": _flex,
    "grid": _grid,
    "container": _container,
    "page": _page,
    "table.head": _table_head,
    "table.row": _table_row,
    "table.header_cell": _table_header_cell,
    "table.cell": _table_cell,
}

#: Styles whose historical default is suppressed when the developer already
#: supplied the relevant utility classes (legacy Button behaviour).
_SUPPRESS_RULES: dict[str, tuple[str, ...]] = {
    "button": _BTN_MARKERS,
}


class TailwindAdapter:
    """Default style adapter: semantic style keys → Tailwind utility classes."""

    def component_classes(
        self, component: str, props: dict[str, Any], theme: Theme
    ) -> str:
        resolver = _STYLES.get(component)
        if resolver is None:
            return ""
        user = str(props.get("class_") or "")
        markers = _SUPPRESS_RULES.get(component)
        if markers and _has_any(user, markers):
            return ""
        return resolver(props, theme)
