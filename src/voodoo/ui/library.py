"""The Voodoo component library.

Components declare structure and semantics only — every class string comes
from the active StyleAdapter (see :mod:`voodoo.adapters.tailwind`). All
components render through the single :meth:`Component.render` path.
"""

from __future__ import annotations

import sys
from typing import Any

from voodoo.ui.component import Component, escape, tone_to_color_var

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


class Div(Component):
    """Bare block container."""


class Flex(Component):
    tag = "div"
    style = "flex"

    def __init__(
        self,
        *children: Any,
        direction: str = "row",
        justify: str = "start",
        items: str = "stretch",
        wrap: str = "nowrap",
        gap: str = "0",
        **kwargs: Any,
    ) -> None:
        super().__init__(*children, **kwargs)
        self.props = {
            "direction": direction,
            "justify": justify,
            "items": items,
            "wrap": wrap,
            "gap": gap,
        }


class Grid(Component):
    tag = "div"
    style = "grid"

    def __init__(
        self, *children: Any, cols: str = "1", gap: str = "4", **kwargs: Any
    ) -> None:
        super().__init__(*children, **kwargs)
        self.props = {"cols": cols, "gap": gap}


class Container(Component):
    tag = "div"
    style = "container"

    def __init__(
        self, *children: Any, size: str = "xl", centered: bool = True, **kwargs: Any
    ) -> None:
        super().__init__(*children, **kwargs)
        self.props = {"size": size, "centered": centered}


class Page(Component):
    """Semantic page shell: a centered, width-capped ``<main>``."""

    tag = "main"
    style = "page"

    def __init__(
        self, *children: Any, size: str = "lg", pad: bool = True, **kwargs: Any
    ) -> None:
        super().__init__(*children, **kwargs)
        self.props = {"size": size, "pad": pad}


class Stack(Flex):
    """Vertical flex layout with semantic gap — the most common layout.

    ::

        Stack(Heading("Title"), Text("Body"), Button("Go"), gap="lg")
    """

    def __init__(self, *children: Any, gap: str = "md", **kwargs: Any) -> None:
        kwargs.setdefault("direction", "col")
        super().__init__(*children, gap=gap, **kwargs)


class Box(Component):
    """Generic styled container with optional padding.

    ::

        Box(Text("Hello"), padding="lg")
    """

    tag = "div"

    _PADDING_MAP = {
        "xs": "var(--vd-space-xs)",
        "sm": "var(--vd-space-sm)",
        "md": "var(--vd-space-md)",
        "lg": "var(--vd-space-lg)",
        "xl": "var(--vd-space-xl)",
        "xxl": "var(--vd-space-xxl)",
        "none": "0",
    }

    def __init__(
        self, *children: Any, padding: str | None = None, **kwargs: Any
    ) -> None:
        super().__init__(*children, **kwargs)
        if padding and padding != "none":
            value = self._PADDING_MAP.get(padding, padding)
            css_str = f"padding: {value}"
            self._inline_css = (
                f"{self._inline_css}; {css_str}" if self._inline_css else css_str
            )


# ---------------------------------------------------------------------------
# Core elements
# ---------------------------------------------------------------------------


class A(Component):
    tag = "a"

    def __init__(
        self,
        *children: Any,
        href: str = "#",
        target: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*children, **kwargs)
        self.attrs["href"] = href
        if target:
            self.attrs["target"] = target


class Link(A):
    """Themed link — styled by the active adapter."""

    style = "link"


class Button(Component):
    tag = "button"
    style = "button"

    def __init__(
        self,
        *children: Any,
        on_click: str | None = None,
        variant: str | None = None,
        size: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*children, **kwargs)
        if on_click:
            self.attrs["onclick"] = (
                f"voodoo.sendEvent('{on_click}', this.id, this.value)"
            )
        self.props = {"variant": variant, "size": size}


class Card(Component):
    tag = "div"
    style = "card"


class Text(Component):
    """Inline text with optional semantic tone.

    ::

        Text("Subtitle", tone="muted")
        Text("Error!", tone="danger")
    """

    tag = "span"

    def __init__(self, *children: Any, tone: str | None = None, **kwargs: Any) -> None:
        super().__init__(*children, **kwargs)
        if tone and tone != "default":
            color = tone_to_color_var(tone)
            if color:
                css_str = f"color: {color}"
                self._inline_css = (
                    f"{self._inline_css}; {css_str}" if self._inline_css else css_str
                )


# Heading size → font-size token mapping
_HEADING_SIZES = {
    "sm": "var(--vd-text-lg)",
    "md": "var(--vd-text-xl)",
    "lg": "var(--vd-text-xxl)",
    "xl": "var(--vd-text-xxxl)",
    "display": "var(--vd-text-display)",
}


class Heading(Component):
    """Heading with ``level`` (HTML tag) and optional ``size``/``tone``.

    ::

        Heading("Page Title", level=1, size="xl")
        Heading("Error", tone="danger")
    """

    style = "heading"

    def __init__(
        self,
        *children: Any,
        level: int = 1,
        size: str | None = None,
        tone: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*children, **kwargs)
        self.tag = f"h{level}"
        self.props = {"level": level, "size": size}
        extra_css: list[str] = []
        if size and size in _HEADING_SIZES:
            extra_css.append(f"font-size: {_HEADING_SIZES[size]}")
        if tone and tone != "default":
            color = tone_to_color_var(tone)
            if color:
                extra_css.append(f"color: {color}")
        if extra_css:
            css_str = "; ".join(extra_css)
            self._inline_css = (
                f"{self._inline_css}; {css_str}" if self._inline_css else css_str
            )


class Badge(Component):
    tag = "div"
    style = "badge"

    def __init__(self, *children: Any, variant: str = "default", **kwargs: Any) -> None:
        super().__init__(*children, **kwargs)
        self.props = {"variant": variant}


class _AvatarImg(Component):
    tag = "img"
    style = "avatar.img"
    auto_id = False


class _AvatarFallback(Component):
    tag = "span"
    style = "avatar.fallback"
    auto_id = False


class Avatar(Component):
    tag = "div"
    style = "avatar"

    def __init__(
        self,
        *children: Any,
        src: str | None = None,
        alt: str = "",
        fallback: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(*children, **kwargs)
        if not self.children:
            if src:
                self.children = (_AvatarImg(src=src, alt=alt),)
            else:
                self.children = (_AvatarFallback(fallback),)


class Divider(Component):
    tag = "hr"
    style = "divider"


class Dialog(Component):
    tag = "dialog"
    style = "dialog"

    def __init__(self, *children: Any, open: bool = False, **kwargs: Any) -> None:
        super().__init__(*children, **kwargs)
        if open:
            self.attrs["open"] = True


class Modal(Component):
    """Accessible modal built on the native ``<dialog>`` element."""

    tag = "dialog"
    style = "modal"

    def __init__(
        self,
        *children: Any,
        open: bool = False,
        labelled_by: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*children, **kwargs)
        self.attrs["role"] = "dialog"
        self.attrs["aria-modal"] = "true"
        if labelled_by:
            self.attrs["aria-labelledby"] = labelled_by
        if open:
            self.attrs["open"] = True


class List(Component):
    style = "list"

    def __init__(
        self,
        *children: Any,
        ordered: bool = False,
        unstyled: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(*children, **kwargs)
        self.tag = "ol" if ordered else "ul"
        self.props = {"ordered": ordered, "unstyled": unstyled}


class ListItem(Component):
    tag = "li"


class ChatBox(Component):
    style = "chatbox"


# ---------------------------------------------------------------------------
# Icons (curated SVG set — stroke-based, currentColor, 24x24 viewBox)
# ---------------------------------------------------------------------------

#: Curated icon paths (stroke style, 24x24 viewBox, rendered with currentColor).
#: Values are inner-SVG markup; the Icon component wraps them in an <svg>.
_ICONS: dict[str, str] = {
    "send": '<path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4Z"/>',
    "user": '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "bot": '<rect x="4" y="8" width="16" height="12" rx="2"/><path d="M12 8V4"/><circle cx="12" cy="3" r="1"/><path d="M9 13h.01M15 13h.01"/>',
    "plus": '<path d="M5 12h14M12 5v14"/>',
    "trash": '<path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "x": '<path d="M18 6 6 18M6 6l12 12"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.35-4.35"/>',
    "menu": '<path d="M4 6h16M4 12h16M4 18h16"/>',
    "sidebar": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h.01a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51h.01a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v.01a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z"/>',
    "refresh": '<path d="M21 12a9 9 0 1 1-2.64-6.36L21 8"/><path d="M21 3v5h-5"/>',
    "copy": '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    "edit": '<path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/>',
    "chevron-right": '<path d="m9 18 6-6-6-6"/>',
    "chevron-left": '<path d="m15 18-6-6 6-6"/>',
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    "arrow-right": '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    "loader": '<path d="M21 12a9 9 0 1 1-6.219-8.56"/>',
    "sparkles": '<path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/>',
    "message": '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    "paperclip": '<path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"/>',
    "stop": '<rect x="6" y="6" width="12" height="12" rx="2"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32 1.41 1.41M2 12h2m16 0h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>',
    "moon": '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    "eye": '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
}


class Icon(Component):
    """Curated SVG icon (stroke, currentColor, 24x24) — no icon-font needed.

    ::

        Icon("send", size="lg")
        Icon("trash", label="Delete conversation")
    """

    tag = "svg"
    auto_id = False

    _SIZES = {"sm": "16", "md": "20", "lg": "24", "xl": "32"}

    def __init__(
        self,
        name: str,
        *,
        size: str = "md",
        label: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.icon_name = name
        self.icon_markup = _ICONS.get(name)
        if self.icon_markup is None:
            # Unknown names render a neutral placeholder dot rather than
            # raising mid-render — resilience over strictness for UI polish.
            self.icon_markup = "<circle cx='12' cy='12' r='4'/>"
        self.attrs["width"] = self._SIZES.get(size, "20")
        self.attrs["height"] = self.attrs["width"]
        self.attrs["viewBox"] = "0 0 24 24"
        self.attrs["fill"] = "none"
        self.attrs["stroke"] = "currentColor"
        self.attrs["stroke-width"] = "2"
        self.attrs["stroke-linecap"] = "round"
        self.attrs["stroke-linejoin"] = "round"
        self.attrs["aria-hidden"] = "true"
        if label:
            self.attrs["role"] = "img"
            self.attrs["aria-label"] = label
            self.attrs.pop("aria-hidden", None)
        self.attrs["class_"] = (self.attrs.get("class_") or "") + " vd-icon"

    def render(self) -> str:
        attrs = self._render_attrs()
        return f"<svg{attrs}>{self.icon_markup}</svg>"


# ---------------------------------------------------------------------------
# Markdown (safe minimal renderer)
# ---------------------------------------------------------------------------


class Markdown(Component):
    """Render a safe subset of Markdown to HTML (no third-party dependency).

    Supports: headings (#..######), bold/italic/inline code, fenced code
    blocks, unordered/ordered lists, blockquotes, links, paragraphs, and
    hard line breaks. All raw HTML in the source is escaped.

    ::

        Markdown(agent_output)
    """

    auto_id = False

    _ESCAPE_HTML = True

    def __init__(self, source: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.source = source

    def render(self) -> str:
        from voodoo.ui.markdown import render_markdown

        return render_markdown(self.source)


# ---------------------------------------------------------------------------
# Chat primitives
# ---------------------------------------------------------------------------


class MessageList(Component):
    """Scrollable transcript of chat messages (auto-scrolls on append).

    ::

        MessageList([
            ChatMessage(role="user", content="Hi"),
            ChatMessage(role="assistant", content=Markdown(reply)),
        ])
    """

    style = "message-list"

    def __init__(self, *children: Any, **kwargs: Any) -> None:
        super().__init__(*children, **kwargs)
        self.attrs["data-vd-auto-scroll"] = "bottom"


class ChatMessage(Component):
    """A single chat bubble (``role``: user | assistant | system | tool)."""

    style = "chat-message"

    def __init__(
        self,
        *children: Any,
        role: str = "user",
        **kwargs: Any,
    ) -> None:
        super().__init__(*children, **kwargs)
        self.props = {"role": role}


class StreamingText(Component):
    """Live-streaming assistant text with an animated caret.

    Renders ``content`` plus a blinking caret; patches cheaply because the
    id stays stable across broadcasts.
    """

    style = "streaming-text"

    def __init__(self, content: str = "", *, done: bool = False, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.props = {"done": done}
        self._stream_content = content

    def render(self) -> str:
        caret = "" if self.props.get("done") else '<span class="vd-caret"></span>'
        return f"<div{self._render_attrs()}>{escape(self._stream_content)}{caret}</div>"


class Composer(Component):
    """Chat input bar: textarea + send button, wired to a ``@event`` handler.

    Enter sends (Shift+Enter newlines); ``on_send`` is the event name the
    ``@event``-decorated handler receives as ``(element_id, {value})``. All
    wiring lives in the framework's client SDK — zero hand-written JS.
    """

    style = "composer"

    def __init__(
        self,
        *,
        on_send: str,
        placeholder: str = "Type a message…",
        disabled: bool = False,
        **kwargs: Any,
    ) -> None:
        self._on_send = on_send
        self._placeholder = placeholder
        self._disabled = disabled
        super().__init__(**kwargs)

    def render(self) -> str:
        disabled_attr = " disabled" if self._disabled else ""
        return (
            f"<div{self._render_attrs()}>"
            f'<textarea class="vd-composer-input" rows="1" '
            f'placeholder="{escape(self._placeholder)}" '
            f'data-vd-enter-send="{escape(self._on_send)}"{disabled_attr}></textarea>'
            f'<button type="button" class="vd-composer-send" '
            f'data-vd-enter-send-trigger="{escape(self._on_send)}"{disabled_attr}>'
            f"{Icon('send').render()}</button>"
            f"</div>"
        )


class Sidebar(Component):
    """App sidebar shell (title, nav children, optional new-action button).

    ::

        Sidebar(heading="Chats", Nav(...), new_event="new_chat")
    """

    style = "sidebar"


# ---------------------------------------------------------------------------
# Forms
# ---------------------------------------------------------------------------


class Form(Component):
    tag = "form"
    style = "form"

    def __init__(
        self, *children: Any, on_submit: str | None = None, **kwargs: Any
    ) -> None:
        super().__init__(*children, **kwargs)
        if on_submit:
            self.attrs["onsubmit"] = (
                f"event.preventDefault(); voodoo.sendEvent('{on_submit}', "
                "this.id, new FormData(this))"
            )


class Label(Component):
    tag = "label"
    style = "label"


class Input(Component):
    tag = "input"
    style: str | None = "input"

    def __init__(
        self,
        *children: Any,
        on_change: str | None = None,
        size: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*children, **kwargs)
        if on_change:
            self.attrs["onchange"] = (
                f"voodoo.sendEvent('{on_change}', this.id, this.value)"
            )
        if "type" not in self.attrs:
            self.attrs["type"] = "text"
        if self.attrs["type"] in ("checkbox", "radio", "hidden"):
            self.style = None
        self.props = {"size": size}


class Textarea(Component):
    tag = "textarea"
    style = "textarea"

    def __init__(
        self, *children: Any, on_change: str | None = None, **kwargs: Any
    ) -> None:
        super().__init__(*children, **kwargs)
        if on_change:
            self.attrs["onchange"] = (
                f"voodoo.sendEvent('{on_change}', this.id, this.value)"
            )


class Select(Component):
    tag = "select"
    style = "select"

    def __init__(
        self, *children: Any, on_change: str | None = None, **kwargs: Any
    ) -> None:
        super().__init__(*children, **kwargs)
        if on_change:
            self.attrs["onchange"] = (
                f"voodoo.sendEvent('{on_change}', this.id, this.value)"
            )


class Option(Component):
    tag = "option"


class Checkbox(Input):
    def __init__(
        self, *children: Any, on_change: str | None = None, **kwargs: Any
    ) -> None:
        kwargs["type"] = "checkbox"
        if on_change:
            kwargs["onchange"] = (
                f"voodoo.sendEvent('{on_change}', this.id, this.checked)"
            )
        super().__init__(*children, **kwargs)
        self.style = "checkbox"


class Radio(Input):
    def __init__(
        self, *children: Any, on_change: str | None = None, **kwargs: Any
    ) -> None:
        kwargs["type"] = "radio"
        if on_change:
            kwargs["onchange"] = (
                f"voodoo.sendEvent('{on_change}', this.id, this.checked)"
            )
        super().__init__(*children, **kwargs)
        self.style = "radio"


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------


class _Cell(Component):
    """Internal table node — renders without an auto-generated id."""

    auto_id = False

    def __init__(
        self, tag: str, *children: Any, style: str | None = None, **kwargs: Any
    ) -> None:
        super().__init__(*children, **kwargs)
        self.tag = tag
        if style is not None:
            self.style = style


class Table(Component):
    tag = "table"

    def __init__(
        self, headers: list[str], rows: list[list[Any]], **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)

        head_cells = [
            _Cell("th", header, style="table.header_cell") for header in headers
        ]
        head_row = _Cell("tr", *head_cells, style="table.row")
        thead = _Cell("thead", head_row, style="table.head")

        body_rows = [
            _Cell(
                "tr",
                *[_Cell("td", value, style="table.cell") for value in row],
                style="table.row",
            )
            for row in rows
        ]
        tbody = _Cell("tbody", *body_rows)

        self.children = (thead, tbody)


# ---------------------------------------------------------------------------
# Semantic HTML
# ---------------------------------------------------------------------------


class Nav(Component):
    tag = "nav"
    style = "nav"


class Header(Component):
    tag = "header"
    style = "header"


class Footer(Component):
    tag = "footer"
    style = "footer"


class Main(Component):
    tag = "main"
    style = "main"


class Section(Component):
    tag = "section"
    style = "section"


class Article(Component):
    tag = "article"
    style = "article"


class Aside(Component):
    tag = "aside"
    style = "aside"


class Figure(Component):
    tag = "figure"
    style = "figure"


class FigCaption(Component):
    tag = "figcaption"
    style = "figcaption"


class Address(Component):
    tag = "address"
    style = "address"


class Paragraph(Component):
    tag = "p"
    style = "paragraph"


class Time(Component):
    tag = "time"
    style = "time"

    def __init__(
        self, *children: Any, datetime: str | None = None, **kwargs: Any
    ) -> None:
        super().__init__(*children, **kwargs)
        if datetime:
            self.attrs["datetime"] = datetime


class Img(Component):
    tag = "img"
    style = "img"

    def __init__(
        self,
        *children: Any,
        src: str = "",
        alt: str | None = None,
        crossorigin: str | None = None,
        loading: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*children, **kwargs)
        self.attrs["src"] = src
        if alt is None:
            print(
                "[Voodoo SEO Warning] <Img> is missing an 'alt' attribute. "
                "This hurts accessibility and SEO.",
                file=sys.stderr,
            )
            self.attrs["alt"] = ""
        else:
            self.attrs["alt"] = alt
        if crossorigin is not None:
            self.attrs["crossorigin"] = crossorigin
        if loading is not None:
            self.attrs["loading"] = loading


# ---------------------------------------------------------------------------
# Chrome — page-level composite primitives (nav, hero, code, stats, CTA)
# ---------------------------------------------------------------------------


class Navbar(Component):
    """Top navigation bar — a sticky, backdrop-blurred ``<nav>``."""

    tag = "nav"
    style = "navbar"

    def __init__(self, *children: Any, sticky: bool = True, **kwargs: Any) -> None:
        super().__init__(*children, **kwargs)
        self.props = {"sticky": sticky}


class NavLink(Component):
    """Navigation link with an ``active`` state."""

    tag = "a"
    style = "nav-link"

    def __init__(
        self,
        *children: Any,
        href: str = "#",
        active: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(*children, **kwargs)
        self.attrs["href"] = href
        self.props = {"active": active}


class Brand(Component):
    """Wordmark / logo link rendered in the display typeface."""

    tag = "a"
    style = "brand"

    def __init__(self, *children: Any, href: str = "/", **kwargs: Any) -> None:
        super().__init__(*children, **kwargs)
        self.attrs["href"] = href


class ThemeToggle(Component):
    """Button that flips the ``.dark`` class and persists the choice in a cookie."""

    tag = "button"
    style = "theme-toggle"

    def __init__(self, label: str = "Toggle theme", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.attrs["type"] = "button"
        self.attrs["aria-label"] = label
        self.attrs["onclick"] = (
            "var r=document.documentElement;"
            "var d=r.classList.toggle('dark');"
            "document.cookie='voodoo_theme='+(d?'dark':'light')"
            "+';path=/;max-age=31536000';"
        )
        self.children = (
            Text("☀", class_="vd-theme-toggle-sun"),
            Text("☾", class_="vd-theme-toggle-moon"),
        )


class Hero(Component):
    """Full-width hero section for landing pages."""

    tag = "section"
    style = "hero"


class PageHero(Component):
    """Compact hero for interior pages (title + subtitle band)."""

    tag = "section"
    style = "page-hero"


class Eyebrow(Component):
    """Small uppercase accent label that introduces a heading."""

    tag = "span"
    style = "eyebrow"


class Chip(Component):
    """Compact pill for tags, status, or meta information."""

    tag = "span"
    style = "chip"


class CodeBlock(Component):
    """Syntax-aware code block (plain text, escapes HTML).

    ::

        CodeBlock("print('hello')", language="python")
    """

    tag = "pre"
    style = "code-block"

    def __init__(
        self, *children: Any, language: str | None = None, **kwargs: Any
    ) -> None:
        super().__init__(*children, **kwargs)
        self.language = language

    def render(self) -> str:
        attrs = self._render_attrs()
        inner = self._render_children()
        lang = f' data-language="{escape(self.language)}"' if self.language else ""
        return f"<pre{attrs}><code{lang}>{inner}</code></pre>"


class _StatValue(Component):
    tag = "div"
    style = "stat.value"
    auto_id = False


class _StatLabel(Component):
    tag = "div"
    style = "stat.label"
    auto_id = False


class Stats(Component):
    """Responsive row of :class:`Stat` cells."""

    tag = "div"
    style = "stats"

    def __init__(self, *children: Any, cols: int = 3, **kwargs: Any) -> None:
        super().__init__(*children, **kwargs)
        self.props = {"cols": cols}


class Stat(Component):
    """Single metric — big display value with a muted label.

    ::

        Stat("99.99%", "Uptime")
    """

    tag = "div"
    style = "stat"

    def __init__(self, value: str = "", label: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.children = (_StatValue(value), _StatLabel(label))


class CTABand(Component):
    """Full-width call-to-action band."""

    tag = "section"
    style = "cta-band"


class BackLink(Component):
    """Muted link with a leading arrow, used to return to a parent page."""

    tag = "a"
    style = "back-link"

    def __init__(self, *children: Any, href: str = "/", **kwargs: Any) -> None:
        super().__init__(*children, **kwargs)
        self.attrs["href"] = href


class FeatureCard(Component):
    """Elevated card that lifts and highlights on hover."""

    tag = "div"
    style = "feature-card"


class LinkArrow(Component):
    """Accent link with an animated trailing arrow."""

    tag = "a"
    style = "link-arrow"

    def __init__(self, *children: Any, href: str = "#", **kwargs: Any) -> None:
        super().__init__(*children, **kwargs)
        self.attrs["href"] = href


# ---------------------------------------------------------------------------
# Authentication & user UI (composed from the primitives above)
# ---------------------------------------------------------------------------


def _auth_field(label: str, control: Component) -> Component:
    return Stack(Label(label), control, gap="sm")


class LoginForm(Component):
    """Ready-to-use login form composed from library primitives."""

    tag = "div"
    style = "card"

    def __init__(
        self,
        action: str = "/api/auth/login",
        method: str = "POST",
        title: str = "Welcome Back",
        subtitle: str = "Sign in to your account",
        submit_text: str = "Sign In",
        redirect_url: str = "/dashboard",
        csrf_token: str | None = None,
        username_field: str = "username",
        **kwargs: Any,
    ) -> None:
        hidden: list[Component] = []
        if csrf_token:
            hidden.append(Input(type="hidden", name="csrf_token", value=csrf_token))
        if redirect_url:
            hidden.append(Input(type="hidden", name="redirect", value=redirect_url))

        form = Form(
            hidden,
            _auth_field(
                "Email or Username",
                Input(
                    type="text",
                    name=username_field,
                    required=True,
                    autocomplete="username",
                    placeholder="you@example.com",
                ),
            ),
            _auth_field(
                "Password",
                Input(
                    type="password",
                    name="password",
                    required=True,
                    autocomplete="current-password",
                    placeholder="••••••••",
                ),
            ),
            Button(submit_text, type="submit", variant="primary"),
            action=action,
            method=method,
        )
        header = Stack(
            Heading(title, level=2),
            Text(subtitle),
            gap="xs",
            items="center",
        )
        super().__init__(Stack(header, form, gap="lg"), **kwargs)


class RegisterForm(Component):
    """Ready-to-use registration form composed from library primitives."""

    tag = "div"
    style = "card"

    def __init__(
        self,
        action: str = "/api/auth/register",
        method: str = "POST",
        title: str = "Create an Account",
        subtitle: str = "Get started in seconds",
        submit_text: str = "Create Account",
        csrf_token: str | None = None,
        **kwargs: Any,
    ) -> None:
        hidden: list[Component] = []
        if csrf_token:
            hidden.append(Input(type="hidden", name="csrf_token", value=csrf_token))

        form = Form(
            hidden,
            _auth_field(
                "Email Address",
                Input(
                    type="email",
                    name="email",
                    required=True,
                    autocomplete="email",
                    placeholder="you@example.com",
                ),
            ),
            _auth_field(
                "Username",
                Input(
                    type="text",
                    name="username",
                    required=True,
                    autocomplete="username",
                    placeholder="johndoe",
                ),
            ),
            _auth_field(
                "Password",
                Input(
                    type="password",
                    name="password",
                    required=True,
                    autocomplete="new-password",
                    minlength="8",
                    placeholder="Min. 8 characters",
                ),
            ),
            Button(submit_text, type="submit", variant="primary"),
            action=action,
            method=method,
        )
        header = Stack(
            Heading(title, level=2),
            Text(subtitle),
            gap="xs",
            items="center",
        )
        super().__init__(Stack(header, form, gap="lg"), **kwargs)


class UserBadge(Component):
    """Current-user pill with role, initials and logout link."""

    tag = "div"

    def __init__(
        self,
        user: Any | None = None,
        logout_url: str = "/api/auth/logout",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.user = user
        self.logout_url = logout_url

        if not user or not getattr(user, "is_authenticated", False):
            self.attrs["class_"] = "inline-flex items-center gap-2"
            self.children = (
                A(
                    "Sign In",
                    href="/login",
                    class_="text-xs font-semibold text-[var(--color-primary)] hover:underline",
                ),
            )
            return

        display_name = getattr(user, "username", None) or getattr(user, "email", "User")
        initials = display_name[:2].upper() if display_name else "U"
        role = getattr(user, "role", "user")

        self.attrs["class_"] = (
            "inline-flex items-center gap-3 px-3 py-1.5 rounded-full "
            "bg-[var(--color-surface)] border border-[var(--color-border)] "
            "shadow-sm"
        )
        self.children = (
            Div(
                initials,
                class_="w-7 h-7 rounded-full bg-[var(--color-primary)] "
                "text-white text-xs font-bold flex items-center justify-center",
            ),
            Div(
                Text(
                    display_name,
                    class_="text-xs font-medium text-[var(--color-text)] leading-tight",
                ),
                Text(
                    role,
                    class_="text-[10px] text-[var(--color-text-muted)] "
                    "uppercase tracking-wider font-semibold",
                ),
                class_="flex flex-col text-left",
            ),
            A(
                "✕",
                href=logout_url,
                title="Log out",
                class_="text-[var(--color-text-muted)] "
                "hover:text-[var(--color-danger)] ml-1 text-xs "
                "transition-colors",
            ),
        )


class AuthGuard(Component):
    """Renders children only for authenticated users matching the roles."""

    def __init__(
        self,
        *children: Any,
        user: Any | None = None,
        required_roles: list[str] | None = None,
        fallback: Any | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*children, **kwargs)
        self.user = user
        self.required_roles = required_roles or []
        self.fallback = fallback

    def render(self) -> str:
        if not self.user or not getattr(self.user, "is_authenticated", False):
            return self._fallback(
                '<div class="p-4 text-center text-sm '
                'text-[var(--color-text-muted)]">Authentication required '
                "to view this content.</div>"
            )
        if self.required_roles and not any(
            r in getattr(self.user, "roles", [])
            or r == getattr(self.user, "role", None)
            for r in self.required_roles
        ):
            return self._fallback(
                '<div class="p-4 text-center text-sm '
                'text-[var(--color-danger)] font-medium">Access restricted: '
                "insufficient permissions.</div>"
            )
        return super().render()

    def _fallback(self, default: str) -> str:
        if self.fallback is None:
            return default
        if isinstance(self.fallback, Component):
            return self.fallback.render()
        return str(self.fallback)
