"""The Voodoo component library.

Components declare structure and semantics only — every class string comes
from the active StyleAdapter (see :mod:`voodoo.adapters.tailwind`). All
components render through the single :meth:`Component.render` path.
"""

from __future__ import annotations

import sys
from typing import Any

from voodoo.ui.component import Component

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
    tag = "span"


class Heading(Component):
    style = "heading"

    def __init__(self, *children: Any, level: int = 1, **kwargs: Any) -> None:
        super().__init__(*children, **kwargs)
        self.tag = f"h{level}"
        self.props = {"level": level}


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
# Forms
# ---------------------------------------------------------------------------


class Form(Component):
    tag = "form"

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
    style = "input"

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


class Header(Component):
    tag = "header"


class Footer(Component):
    tag = "footer"


class Main(Component):
    tag = "main"


class Section(Component):
    tag = "section"


class Article(Component):
    tag = "article"


class Aside(Component):
    tag = "aside"


class Figure(Component):
    tag = "figure"


class FigCaption(Component):
    tag = "figcaption"


class Address(Component):
    tag = "address"


class Paragraph(Component):
    tag = "p"


class Time(Component):
    tag = "time"

    def __init__(
        self, *children: Any, datetime: str | None = None, **kwargs: Any
    ) -> None:
        super().__init__(*children, **kwargs)
        if datetime:
            self.attrs["datetime"] = datetime


class Img(Component):
    tag = "img"

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
# Authentication & user UI (composed from the primitives above)
# ---------------------------------------------------------------------------


def _auth_field(label: str, control: Component) -> Component:
    return Div(Label(label), control, class_="space-y-2")


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
            class_="space-y-5",
        )
        header = Div(
            Heading(title, level=2),
            Text(subtitle),
            class_="text-center mb-6",
        )
        super().__init__(header, form, **kwargs)


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
            class_="space-y-5",
        )
        header = Div(
            Heading(title, level=2),
            Text(subtitle),
            class_="text-center mb-6",
        )
        super().__init__(header, form, **kwargs)


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
