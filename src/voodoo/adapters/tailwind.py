"""The default Tailwind adapter.

This module is the ONLY place in the framework that knows Tailwind class
syntax. Components declare semantic style keys; this adapter maps them to
concrete utility classes, reproducing the historical default look
byte-for-byte while adding themed ``variant``/``size`` props.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from voodoo.ui.styles.theme import Theme

# ---------------------------------------------------------------------------
# Buttons — legacy default kept byte-identical; semantic variants opt-in
# ---------------------------------------------------------------------------

_BTN_DEFAULT = (
    "inline-flex items-center justify-center rounded-md text-sm font-medium "
    "transition-colors focus-visible:outline-none focus-visible:ring-1 "
    "focus-visible:ring-[var(--vd-color-primary)] disabled:pointer-events-none "
    "disabled:opacity-50 bg-[var(--vd-color-text)] text-[var(--vd-color-surface)] "
    "hover:bg-[var(--vd-color-text)]/90 h-9 px-4 py-2"
)

_BTN_BASE = (
    "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md "
    "text-sm font-medium transition-colors focus-visible:outline-none "
    "focus-visible:ring-1 focus-visible:ring-[var(--vd-color-primary)] "
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
        "bg-[var(--vd-color-primary)] text-[var(--vd-color-surface)] "
        "hover:bg-[var(--vd-color-primary-hover)] cursor-pointer"
    ),
    "secondary": (
        "bg-[var(--vd-color-secondary)] text-white hover:opacity-90 cursor-pointer"
    ),
    "outline": (
        "border border-[var(--vd-color-border)] bg-transparent "
        "text-[var(--vd-color-text)] hover:bg-[var(--vd-color-surface)] cursor-pointer"
    ),
    "ghost": (
        "bg-transparent text-[var(--vd-color-text-muted)] "
        "hover:bg-[var(--vd-color-surface)] hover:text-[var(--vd-color-text)] "
        "cursor-pointer"
    ),
    "danger": (
        "bg-[var(--vd-color-danger)] text-white hover:opacity-90 cursor-pointer"
    ),
}

# Legacy "already styled" heuristic: if the developer supplied background /
# border / hover classes, the framework stays out of the way.
_BTN_MARKERS = ("bg-", "border", "hover:")

# ---------------------------------------------------------------------------
# Forms — legacy defaults kept byte-identical
# ---------------------------------------------------------------------------

_INPUT_DEFAULT = (
    "flex h-9 w-full rounded-md border border-[var(--vd-color-border)] "
    "bg-transparent px-3 py-1 text-sm shadow-sm transition-colors "
    "file:border-0 file:bg-transparent file:text-sm file:font-medium "
    "placeholder:text-[var(--vd-color-text-muted)] focus-visible:outline-none "
    "focus-visible:ring-1 focus-visible:ring-[var(--vd-color-primary)] "
    "disabled:cursor-not-allowed disabled:opacity-50"
)

_INPUT_SIZES = {
    "sm": ("h-8", "px-2.5 py-1"),
    "md": ("h-9", "px-3 py-1"),
    "lg": ("h-11", "px-4 py-2"),
}

_TEXTAREA_DEFAULT = (
    "flex min-h-[80px] w-full rounded-md border border-[var(--vd-color-border)] "
    "bg-transparent px-3 py-2 text-sm shadow-sm "
    "placeholder:text-[var(--vd-color-text-muted)] focus-visible:outline-none "
    "focus-visible:ring-1 focus-visible:ring-[var(--vd-color-primary)] "
    "disabled:cursor-not-allowed disabled:opacity-50"
)

_SELECT_DEFAULT = (
    "flex h-9 w-full items-center justify-between rounded-md border "
    "border-[var(--vd-color-border)] bg-transparent px-3 py-2 text-sm shadow-sm "
    "ring-offset-[var(--vd-color-surface)] "
    "placeholder:text-[var(--vd-color-text-muted)] focus:outline-none "
    "focus:ring-1 focus:ring-[var(--vd-color-primary)] "
    "disabled:cursor-not-allowed disabled:opacity-50"
)

_LABEL_DEFAULT = (
    "block text-sm font-medium leading-none text-[var(--vd-color-text)] "
    "peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
)

_CHECKBOX_DEFAULT = (
    "peer h-4 w-4 shrink-0 rounded-sm border border-[var(--vd-color-border)] "
    "ring-offset-[var(--vd-color-surface)] focus-visible:outline-none "
    "focus-visible:ring-2 focus-visible:ring-[var(--vd-color-primary)] "
    "focus-visible:ring-offset-2 disabled:cursor-not-allowed "
    "disabled:opacity-50 data-[state=checked]:bg-[var(--vd-color-primary)] "
    "data-[state=checked]:text-[var(--vd-color-surface)]"
)

_RADIO_DEFAULT = (
    "aspect-square h-4 w-4 rounded-full border border-[var(--vd-color-border)] "
    "text-[var(--vd-color-primary)] ring-offset-[var(--vd-color-surface)] "
    "focus:outline-none focus-visible:ring-2 "
    "focus-visible:ring-[var(--vd-color-primary)] "
    "focus-visible:ring-offset-2 disabled:cursor-not-allowed "
    "disabled:opacity-50"
)

# ---------------------------------------------------------------------------
# Display — legacy defaults kept byte-identical
# ---------------------------------------------------------------------------

_BADGE_BASE = (
    "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold "
    "transition-colors focus:outline-none focus:ring-2 "
    "focus:ring-[var(--vd-color-primary)]"
)

_BADGE_VARIANTS = {
    "default": (
        "bg-[var(--vd-color-text)] text-[var(--vd-color-surface)] "
        "hover:bg-[var(--vd-color-text)]/80"
    ),
    "secondary": (
        "bg-[var(--vd-color-surface)] text-[var(--vd-color-text)] border "
        "border-[var(--vd-color-border)] hover:bg-[var(--vd-color-surface)]/80"
    ),
    "outline": "text-[var(--vd-color-text)] border border-[var(--vd-color-border)]",
    "success": "bg-[var(--vd-color-success)] text-white",
    "warning": "bg-[var(--vd-color-warning)] text-black",
    "danger": "bg-[var(--vd-color-danger)] text-white",
}

_HEADING_LEVELS = {
    1: "text-4xl font-bold tracking-tight",
    2: "text-3xl font-semibold tracking-tight",
    3: "text-2xl font-semibold tracking-tight",
    4: "text-xl font-semibold tracking-tight",
}

_AVATAR_FALLBACK_DEFAULT = (
    "flex h-full w-full items-center justify-center rounded-full "
    "bg-[var(--vd-color-surface)] border border-[var(--vd-color-border)] "
    "text-[var(--vd-color-text)] text-sm font-medium"
)

_DIALOG_DEFAULT = (
    "backdrop:bg-black/50 p-0 rounded-xl border border-[var(--vd-color-border)] "
    "bg-[var(--vd-color-surface)] shadow-2xl open:flex flex-col"
)

_DIVIDER_DEFAULT = "m-0 h-px w-full border-none bg-[var(--vd-color-border)]"

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

_TABLE_HEAD = "bg-[var(--vd-color-surface)] border-b border-[var(--vd-color-border)]"
_TABLE_ROW = (
    "border-b border-[var(--vd-color-border)] hover:bg-[var(--vd-color-surface)] "
    "transition-colors"
)
_TABLE_HEADER_CELL = (
    "px-6 py-4 text-left text-xs font-medium text-[var(--vd-color-text-muted)] "
    "uppercase tracking-wider"
)
_TABLE_CELL = "px-6 py-4 whitespace-nowrap text-sm text-[var(--vd-color-text)]"


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
    variant = props.get("variant") or "default"
    padding = props.get("padding", "lg")
    parts: list[str] = []
    shadow = "shadow-sm"
    if variant == "ghost":
        if "bg-" not in user:
            parts.append("bg-transparent")
        if "border" not in user:
            parts.append("border border-transparent")
        shadow = "shadow-none"
    elif variant == "outline":
        if "bg-" not in user:
            parts.append("bg-transparent")
        if "border" not in user:
            parts.append("border border-[var(--vd-color-border)]")
        shadow = "shadow-none"
    else:
        if "bg-" not in user:
            surface = (
                "bg-[var(--vd-color-surface-raised)]"
                if variant == "elevated"
                else "bg-[var(--vd-color-surface)]"
            )
            parts.append(surface)
        if "border" not in user:
            parts.append("border border-[var(--vd-color-border)]")
        shadow = "shadow-md" if variant == "elevated" else "shadow-sm"
    if variant == "interactive" or props.get("interactive"):
        parts.append(
            "cursor-pointer transition-all hover:-translate-y-0.5 hover:shadow-md"
        )
    padding_class = {
        "none": "p-0",
        "sm": "p-2",
        "md": "p-4",
        "lg": "p-6",
        "xl": "p-8",
    }.get(padding, "p-6")
    parts.extend(("rounded-xl", padding_class, shadow))
    return " ".join(parts)


def _heading(props: dict[str, Any], theme: Theme) -> str:
    user = str(props.get("class_") or "")
    if "text-" in user:
        return ""
    size = _HEADING_LEVELS.get(props.get("level"), "text-lg font-medium")
    return f"{size} text-[var(--vd-color-text)]"


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
        "border border-[var(--vd-color-border)] bg-[var(--vd-color-surface)] "
        "shadow-2xl open:flex flex-col gap-4 text-[var(--vd-color-text)] m-auto"
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


def _form(props: dict[str, Any], theme: Theme) -> str:
    return "flex flex-col gap-md"


def _table_head(props: dict[str, Any], theme: Theme) -> str:
    return _TABLE_HEAD


def _table_row(props: dict[str, Any], theme: Theme) -> str:
    return _TABLE_ROW


def _table_header_cell(props: dict[str, Any], theme: Theme) -> str:
    return _TABLE_HEADER_CELL


def _table_cell(props: dict[str, Any], theme: Theme) -> str:
    return _TABLE_CELL


_LINK_DEFAULT = (
    "text-[var(--vd-color-primary)] underline-offset-4 hover:underline "
    "cursor-pointer transition-colors"
)


def _link(props: dict[str, Any], theme: Theme) -> str:
    return _LINK_DEFAULT


def _alert(props: dict[str, Any], theme: Theme) -> str:
    tone = props.get("tone", "info")
    variant = props.get("variant", "soft")
    color = f"var(--vd-color-{tone})"
    base = "grid gap-1 rounded-lg border px-4 py-3 text-sm"
    if variant == "solid":
        foreground = "text-black" if tone == "warning" else "text-white"
        return f"{base} {foreground} bg-[{color}] border-[{color}]"
    background = (
        "bg-transparent"
        if variant == "outline"
        else f"bg-[color-mix(in_srgb,{color}_8%,transparent)]"
    )
    return f"{base} {background} border-[color-mix(in_srgb,{color}_28%,transparent)]"


def _progress(props: dict[str, Any], theme: Theme) -> str:
    tone = props.get("tone", "primary")
    size = {"sm": "h-1", "md": "h-2", "lg": "h-3"}.get(props.get("size", "md"), "h-2")
    return (
        f"block w-full {size} appearance-none overflow-hidden rounded-full "
        "bg-[var(--vd-color-surface-raised)] "
        "[&::-webkit-progress-bar]:bg-[var(--vd-color-surface-raised)] "
        f"[&::-webkit-progress-value]:bg-[var(--vd-color-{tone})] "
        f"[&::-moz-progress-bar]:bg-[var(--vd-color-{tone})]"
    )


def _spinner(props: dict[str, Any], theme: Theme) -> str:
    glyph_size = {
        "sm": "[&>span:first-child]:size-3.5",
        "md": "[&>span:first-child]:size-[1.125rem]",
        "lg": "[&>span:first-child]:size-6",
    }.get(props.get("size", "md"), "[&>span:first-child]:size-[1.125rem]")
    return f"inline-flex items-center justify-center align-middle {glyph_size}"


def _spinner_glyph(props: dict[str, Any], theme: Theme) -> str:
    return (
        "block size-[1.125rem] rounded-full border-2 border-current/20 "
        "border-t-current animate-spin"
    )


def _visually_hidden(props: dict[str, Any], theme: Theme) -> str:
    return "sr-only"


def _breadcrumb(props: dict[str, Any], theme: Theme) -> str:
    return "min-w-0"


def _breadcrumb_list(props: dict[str, Any], theme: Theme) -> str:
    return (
        "flex list-none flex-wrap items-center gap-1.5 text-sm "
        "text-[var(--vd-color-text-muted)]"
    )


def _breadcrumb_item(props: dict[str, Any], theme: Theme) -> str:
    return (
        "inline-flex items-center gap-1.5 "
        "[&:not(:last-child)::after]:content-['/'] "
        "[&:not(:last-child)::after]:text-[var(--vd-color-text-muted)]"
    )


def _breadcrumb_link(props: dict[str, Any], theme: Theme) -> str:
    return (
        "text-inherit no-underline transition-colors hover:text-[var(--vd-color-text)]"
    )


def _breadcrumb_current(props: dict[str, Any], theme: Theme) -> str:
    return "font-medium text-[var(--vd-color-text)]"


def _button_group(props: dict[str, Any], theme: Theme) -> str:
    vertical = props.get("orientation") == "vertical"
    direction = "flex-col" if vertical else "flex-row"
    if not props.get("attached", True):
        return f"inline-flex items-stretch gap-2 {direction}"
    if vertical:
        geometry = (
            "[&>button]:rounded-none [&>button+button]:-mt-px "
            "[&>button:first-child]:rounded-t-md "
            "[&>button:last-child]:rounded-b-md"
        )
    else:
        geometry = (
            "[&>button]:rounded-none [&>button+button]:-ml-px "
            "[&>button:first-child]:rounded-l-md "
            "[&>button:last-child]:rounded-r-md"
        )
    return f"inline-flex items-stretch {direction} {geometry}"


def _accordion(props: dict[str, Any], theme: Theme) -> str:
    variant = props.get("variant", "separated")
    if variant == "contained":
        return (
            "grid gap-0 overflow-hidden rounded-lg border "
            "border-[var(--vd-color-border)] "
            "[&>details]:rounded-none [&>details]:border-0 "
            "[&>details+details]:border-t"
        )
    if variant == "ghost":
        return "grid gap-2 [&>details]:border-transparent [&>details]:bg-transparent"
    return "grid gap-2"


def _accordion_item(props: dict[str, Any], theme: Theme) -> str:
    return (
        "rounded-lg border border-[var(--vd-color-border)] bg-[var(--vd-color-surface)]"
    )


def _accordion_summary(props: dict[str, Any], theme: Theme) -> str:
    return (
        "flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 "
        "text-sm font-medium after:text-lg after:text-[var(--vd-color-text-muted)] "
        "after:content-['+']"
    )


def _accordion_content(props: dict[str, Any], theme: Theme) -> str:
    return "px-4 pb-4 text-sm leading-relaxed text-[var(--vd-color-text-muted)]"


def _kbd(props: dict[str, Any], theme: Theme) -> str:
    return (
        "inline-flex min-h-6 min-w-6 items-center justify-center rounded border "
        "border-[var(--vd-color-border)] border-b-2 "
        "bg-[var(--vd-color-surface-raised)] px-1.5 font-mono text-xs leading-none "
        "text-[var(--vd-color-text)] shadow-sm"
    )


def _aspect_ratio(props: dict[str, Any], theme: Theme) -> str:
    return "relative w-full overflow-hidden [&>*]:size-full [&>*]:object-cover"


def _sidebar(props: dict[str, Any], theme: Theme) -> str:
    mode = props.get("mode", "expanded")
    mode_class = {
        "expanded": "w-64",
        "rail": "w-[4.5rem] px-2 [&_[data-vd-sidebar-label]]:hidden",
        "hidden": "w-0 -translate-x-full overflow-hidden border-0 px-0 opacity-0 pointer-events-none",
    }.get(mode, "w-64")
    return (
        "relative flex shrink-0 flex-col gap-2 overflow-x-hidden overflow-y-auto border-r "
        "border-[var(--vd-color-border)] bg-[var(--vd-color-surface)] p-3 "
        "text-[var(--vd-color-text)] transition-all duration-200 "
        "max-md:fixed max-md:inset-y-0 max-md:left-0 max-md:z-[90] "
        "max-md:h-dvh max-md:shadow-2xl "
        "[&[data-vd-sidebar-mode=expanded]]:visible [&[data-vd-sidebar-mode=expanded]]:w-64 "
        "[&[data-vd-sidebar-mode=rail]]:visible [&[data-vd-sidebar-mode=rail]]:w-[4.5rem] "
        "[&[data-vd-sidebar-mode=rail]]:px-2 [&[data-vd-sidebar-mode=rail]]:pb-16 "
        "max-md:[&[data-vd-sidebar-mode=rail]]:relative "
        "max-md:[&[data-vd-sidebar-mode=rail]]:inset-auto "
        "max-md:[&[data-vd-sidebar-mode=rail]]:shadow-none "
        "[&[data-vd-sidebar-mode=rail]_[data-vd-sidebar-label]]:hidden "
        "[&[data-vd-sidebar-mode=rail]_[data-vd-sidebar-brand]]:gap-0 "
        "[&[data-vd-sidebar-mode=rail]_[data-vd-sidebar-item]]:gap-0 "
        "[&[data-vd-sidebar-mode=hidden]]:invisible [&[data-vd-sidebar-mode=hidden]]:w-0 "
        "[&[data-vd-sidebar-mode=hidden]]:-translate-x-full "
        "[&[data-vd-sidebar-mode=hidden]]:border-0 "
        "[&[data-vd-sidebar-mode=hidden]]:px-0 "
        "[&[data-vd-sidebar-mode=hidden]]:opacity-0 "
        "[&[data-vd-sidebar-mode=hidden]]:pointer-events-none "
        f"{mode_class}"
    )


def _bottom_nav_item(props: dict[str, Any], theme: Theme) -> str:
    state = (
        "text-[var(--vd-color-secondary)]"
        if props.get("active")
        else "text-[var(--vd-color-text-muted)]"
    )
    return (
        "flex min-h-[3.25rem] min-w-0 flex-1 flex-col items-center justify-center "
        f"gap-0.5 rounded-md text-xs no-underline {state}"
    )


def _sidebar_item(props: dict[str, Any], theme: Theme) -> str:
    active = props.get("active")
    state = (
        "bg-[var(--vd-color-secondary-soft)] text-[var(--vd-color-secondary)]"
        if active
        else "text-[var(--vd-color-text-muted)] hover:bg-[var(--vd-color-surface-raised)] hover:text-[var(--vd-color-text)]"
    )
    return (
        "flex min-h-10 w-full items-center gap-2 rounded-md border-0 bg-transparent "
        f"p-2 text-sm no-underline transition-colors disabled:pointer-events-none "
        f"disabled:opacity-50 {state}"
    )


def _sidebar_toggle(props: dict[str, Any], theme: Theme) -> str:
    placement = props.get("placement", "standalone")
    placement_class = {
        "inside": "shrink-0",
        "launcher": (
            "fixed left-[max(0.75rem,env(safe-area-inset-left))] "
            "top-[max(0.75rem,env(safe-area-inset-top))] hidden shadow-sm "
            "[&[data-vd-sidebar-current-mode=hidden]]:inline-flex"
        ),
    }.get(placement, "")
    return (
        "relative z-[95] inline-flex size-10 items-center justify-center rounded-md border "
        "border-[var(--vd-color-border)] bg-[var(--vd-color-surface)] "
        "[&[data-vd-sidebar-placement=inside]_[data-vd-sidebar-toggle-glyph]]:size-2 "
        "[&[data-vd-sidebar-placement=inside]_[data-vd-sidebar-toggle-glyph]]:rotate-[135deg] "
        "[&[data-vd-sidebar-placement=inside]_[data-vd-sidebar-toggle-glyph]]:border-0 "
        "[&[data-vd-sidebar-placement=inside]_[data-vd-sidebar-toggle-glyph]]:border-r "
        "[&[data-vd-sidebar-placement=inside]_[data-vd-sidebar-toggle-glyph]]:border-b "
        "[&[data-vd-sidebar-placement=inside]_[data-vd-sidebar-toggle-glyph]]:after:hidden "
        "[&[data-vd-sidebar-placement=inside][data-vd-sidebar-current-mode=rail]_[data-vd-sidebar-toggle-glyph]]:-rotate-45 "
        f"{placement_class}"
    )


def _app_shell_content(props: dict[str, Any], theme: Theme) -> str:
    padding = {
        "none": "p-0",
        "sm": "p-3",
        "md": "p-3 sm:p-4",
        "lg": "p-4 sm:p-6",
        "xl": "p-6 sm:p-8",
    }.get(props.get("padding", "lg"), "p-4 sm:p-6")
    return f"min-h-0 min-w-0 flex-1 overflow-auto {padding}"


def _drawer(props: dict[str, Any], theme: Theme) -> str:
    side = props.get("side", "left")
    size = props.get("size", "md")
    if side in {"left", "right"}:
        dimension = {
            "sm": "h-dvh w-[min(20rem,calc(100vw-1rem))]",
            "md": "h-dvh w-[min(24rem,calc(100vw-1rem))]",
            "lg": "h-dvh w-[min(32rem,calc(100vw-1rem))]",
            "full": "h-dvh w-screen",
        }.get(size, "h-dvh w-[min(24rem,calc(100vw-1rem))]")
    else:
        dimension = {
            "sm": "w-screen h-[min(16rem,calc(100dvh-1rem))]",
            "md": "w-screen h-[min(28rem,calc(100dvh-1rem))]",
            "lg": "w-screen h-[min(36rem,calc(100dvh-1rem))]",
            "full": "h-dvh w-screen",
        }.get(size, "w-screen h-[min(28rem,calc(100dvh-1rem))]")
    position = {
        "left": "inset-y-0 left-0",
        "right": "inset-y-0 right-0",
        "top": "inset-x-0 top-0",
        "bottom": "inset-x-0 bottom-0 rounded-t-xl",
    }.get(side, "inset-y-0 left-0")
    return (
        "m-0 max-h-none max-w-none overflow-hidden border-0 "
        "bg-[var(--vd-color-surface)] p-0 text-[var(--vd-color-text)] shadow-2xl "
        "backdrop:bg-black/50 open:flex open:flex-col "
        f"{dimension} {position}"
    )


def _dropdown_menu(props: dict[str, Any], theme: Theme) -> str:
    return (
        "fixed left-[var(--vd-anchor-x,0)] top-[var(--vd-anchor-y,0)] z-[100] "
        "m-0 min-w-48 max-w-[calc(100vw-1rem)] rounded-lg border "
        "border-[var(--vd-color-border)] bg-[var(--vd-color-surface)] p-1 "
        "text-[var(--vd-color-text)] shadow-xl"
    )


def _menu_item(props: dict[str, Any], theme: Theme) -> str:
    tone = (
        "text-[var(--vd-color-danger)]"
        if props.get("destructive")
        else "text-[var(--vd-color-text)]"
    )
    return (
        "flex min-h-9 w-full items-center justify-between gap-4 rounded-md border-0 "
        "bg-transparent p-2 text-left text-sm no-underline outline-none "
        "hover:bg-[var(--vd-color-surface-raised)] "
        "focus:bg-[var(--vd-color-surface-raised)] disabled:opacity-50 "
        f"{tone}"
    )


def _tabs(props: dict[str, Any], theme: Theme) -> str:
    if props.get("orientation") == "vertical":
        return (
            "flex min-w-0 flex-row gap-4 "
            "[&>.vd-tabs-list]:flex-col [&>.vd-tabs-list]:items-stretch "
            "[&>.vd-tabs-list]:border-b-0 [&>.vd-tabs-list]:border-r"
        )
    return "flex min-w-0 flex-col gap-4"


def _toast_region(props: dict[str, Any], theme: Theme) -> str:
    position = {
        "top-left": "left-4 top-4",
        "top-right": "right-4 top-4",
        "bottom-left": "bottom-4 left-4",
        "bottom-right": "bottom-4 right-4",
    }.get(props.get("position", "bottom-right"), "bottom-4 right-4")
    return (
        "pointer-events-none fixed z-[120] flex w-[min(24rem,calc(100vw-2rem))] "
        f"flex-col gap-2 {position}"
    )


def _toast(props: dict[str, Any], theme: Theme) -> str:
    tone = props.get("tone", "default")
    accent = "secondary" if tone == "default" else tone
    return (
        "pointer-events-auto flex w-full items-center gap-3 rounded-lg border "
        "border-[var(--vd-color-border)] border-l-[3px] "
        f"border-l-[var(--vd-color-{accent})] "
        "bg-[var(--vd-color-surface-raised)] p-3 text-[var(--vd-color-text)] shadow-xl"
    )


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
    "form": _form,
    "link": _link,
    "table.head": _table_head,
    "table.row": _table_row,
    "table.header_cell": _table_header_cell,
    "table.cell": _table_cell,
    "alert": _alert,
    "alert.title": lambda props, theme: "font-semibold",
    "alert.content": lambda props, theme: "leading-relaxed opacity-90",
    "progress": _progress,
    "spinner": _spinner,
    "spinner.glyph": _spinner_glyph,
    "visually-hidden": _visually_hidden,
    "breadcrumb": _breadcrumb,
    "breadcrumb.list": _breadcrumb_list,
    "breadcrumb.item": _breadcrumb_item,
    "breadcrumb.link": _breadcrumb_link,
    "breadcrumb.current": _breadcrumb_current,
    "button-group": _button_group,
    "accordion": _accordion,
    "accordion.item": _accordion_item,
    "accordion.summary": _accordion_summary,
    "accordion.content": _accordion_content,
    "kbd": _kbd,
    "aspect-ratio": _aspect_ratio,
    "sidebar": _sidebar,
    "app-shell": lambda props, theme: "flex h-dvh w-full items-stretch overflow-hidden",
    "app-shell.content": _app_shell_content,
    "bottom-nav": lambda props, theme: (
        "fixed inset-x-0 bottom-0 z-[80] flex min-h-[3.75rem] items-stretch "
        "justify-around border-t border-[var(--vd-color-border)] "
        "bg-[var(--vd-color-surface)] px-2 pb-[env(safe-area-inset-bottom)] md:hidden"
    ),
    "bottom-nav-item": _bottom_nav_item,
    "bottom-nav-item.icon": lambda props, theme: (
        "inline-flex size-6 items-center justify-center"
    ),
    "bottom-nav-item.label": lambda props, theme: "max-w-full truncate",
    "sidebar-item": _sidebar_item,
    "sidebar-item.icon": lambda props, theme: (
        "inline-flex size-6 shrink-0 items-center justify-center"
    ),
    "sidebar-item.label": lambda props, theme: "min-w-0 truncate",
    "sidebar-item.badge": lambda props, theme: (
        "ml-auto text-xs text-[var(--vd-color-text-muted)]"
    ),
    "sidebar-header": lambda props, theme: (
        "flex min-h-10 shrink-0 items-center justify-between gap-2 "
        "[aside[data-vd-sidebar-mode=rail]_&]:flex-col "
        "[aside[data-vd-sidebar-mode=rail]_&]:justify-start"
    ),
    "sidebar-brand": lambda props, theme: (
        "flex min-w-0 items-center gap-2 text-[var(--vd-color-text)] no-underline "
        "[aside[data-vd-sidebar-mode=rail]_&]:justify-center"
    ),
    "sidebar-brand.mark": lambda props, theme: (
        "inline-flex size-8 shrink-0 items-center justify-center rounded-md border "
        "border-[var(--vd-color-border)] bg-[var(--vd-color-surface-raised)] "
        "text-sm font-bold tracking-tight"
    ),
    "sidebar-brand.text": lambda props, theme: (
        "min-w-0 truncate text-sm font-semibold tracking-tight"
    ),
    "sidebar-controls": lambda props, theme: (
        "flex min-h-10 shrink-0 items-center justify-end "
        "[aside[data-vd-sidebar-mode=rail]_&]:absolute "
        "[aside[data-vd-sidebar-mode=rail]_&]:inset-x-2 "
        "[aside[data-vd-sidebar-mode=rail]_&]:bottom-3 "
        "[aside[data-vd-sidebar-mode=rail]_&]:justify-center"
    ),
    "sidebar-toggle": _sidebar_toggle,
    "sidebar-toggle.glyph": lambda props, theme: (
        "relative block h-3 w-4 border-y border-current "
        "transition-transform "
        "after:absolute after:inset-x-0 after:top-1/2 after:border-t after:border-current"
    ),
    "drawer-shell": lambda props, theme: "contents",
    "drawer": _drawer,
    "drawer.header": lambda props, theme: (
        "grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1 "
        "border-b border-[var(--vd-color-border)] p-4"
    ),
    "drawer.title": lambda props, theme: "text-lg font-semibold",
    "drawer.description": lambda props, theme: (
        "text-sm text-[var(--vd-color-text-muted)]"
    ),
    "drawer.body": lambda props, theme: "min-h-0 flex-1 overflow-y-auto p-4",
    "dropdown-shell": lambda props, theme: "contents",
    "dropdown-menu": _dropdown_menu,
    "menu-item": _menu_item,
    "menu-item.label": lambda props, theme: "min-w-0 flex-1",
    "menu-shortcut": lambda props, theme: (
        "ml-auto text-xs text-[var(--vd-color-text-muted)]"
    ),
    "menu-separator": lambda props, theme: (
        "my-1 h-px border-0 bg-[var(--vd-color-border)]"
    ),
    "tabs": _tabs,
    "tabs.list": lambda props, theme: (
        "flex items-center gap-1 border-b border-[var(--vd-color-border)]"
    ),
    "tabs.trigger": lambda props, theme: (
        "relative min-h-10 border-0 bg-transparent px-3 py-2 text-sm font-medium "
        "text-[var(--vd-color-text-muted)] aria-selected:text-[var(--vd-color-text)] "
        "disabled:opacity-50"
    ),
    "tabs.panel": lambda props, theme: "min-w-0 py-4",
    "toast-region": _toast_region,
    "toast": _toast,
    "toast.content": lambda props, theme: "min-w-0 flex-1",
    "toast.title": lambda props, theme: "text-sm font-semibold",
    "toast.message": lambda props, theme: "text-sm text-[var(--vd-color-text-muted)]",
    "toast.actions": lambda props, theme: "flex items-center gap-1",
    "toast.dismiss": lambda props, theme: (
        "min-h-8 rounded border-0 bg-transparent px-2 text-sm "
        "text-[var(--vd-color-text-muted)] hover:bg-[var(--vd-color-surface)]"
    ),
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
