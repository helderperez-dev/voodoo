import uuid
from typing import Any


class Component:
    tag = "div"

    def __init__(self, *children, id=None, **kwargs):
        self.id = id or f"vd-{uuid.uuid4().hex[:8]}"
        self.children = children
        self.attributes = kwargs

    def render(self) -> str:
        attrs = [f'id="{self.id}"']
        for k, v in self.attributes.items():
            k = k.replace("_", "-")
            if k == "className":
                k = "class"
            if v is not None and v is not False:
                if v is True:
                    attrs.append(f"{k}")
                else:
                    attrs.append(f'{k}="{v}"')

        attr_str = " " + " ".join(attrs) if attrs else ""

        rendered_children = ""
        for child in self.children:
            if isinstance(child, Component):
                rendered_children += child.render()
            else:
                rendered_children += str(child)

        # Self closing tags
        if self.tag in ["input", "img", "br", "hr"]:
            return f"<{self.tag}{attr_str} />"

        return f"<{self.tag}{attr_str}>{rendered_children}</{self.tag}>"


# --- Layout Primitives ---


class Div(Component):
    tag = "div"


class Flex(Component):
    tag = "div"

    def __init__(
        self,
        *children,
        direction="row",
        justify="start",
        items="stretch",
        wrap="nowrap",
        gap="0",
        **kwargs,
    ):
        classes = kwargs.get("className", "")
        direction_map = {
            "row": "flex-row",
            "col": "flex-col",
            "row-reverse": "flex-row-reverse",
            "col-reverse": "flex-col-reverse",
        }
        justify_map = {
            "start": "justify-start",
            "end": "justify-end",
            "center": "justify-center",
            "between": "justify-between",
            "around": "justify-around",
            "evenly": "justify-evenly",
        }
        items_map = {
            "start": "items-start",
            "end": "items-end",
            "center": "items-center",
            "baseline": "items-baseline",
            "stretch": "items-stretch",
        }
        wrap_map = {
            "nowrap": "flex-nowrap",
            "wrap": "flex-wrap",
            "wrap-reverse": "flex-wrap-reverse",
        }

        base_classes = f"flex {direction_map.get(direction, 'flex-row')} {justify_map.get(justify, 'justify-start')} {items_map.get(items, 'items-stretch')} {wrap_map.get(wrap, 'flex-nowrap')} gap-{gap}"
        kwargs["className"] = f"{base_classes} {classes}".strip()
        super().__init__(*children, **kwargs)


class Grid(Component):
    tag = "div"

    def __init__(self, *children, cols="1", gap="4", **kwargs):
        classes = kwargs.get("className", "")
        base_classes = f"grid grid-cols-{cols} gap-{gap}"
        kwargs["className"] = f"{base_classes} {classes}".strip()
        super().__init__(*children, **kwargs)


class Container(Component):
    tag = "div"

    def __init__(self, *children, size="xl", centered=True, **kwargs):
        classes = kwargs.get("className", "")
        size_map = {
            "sm": "max-w-screen-sm",
            "md": "max-w-screen-md",
            "lg": "max-w-screen-lg",
            "xl": "max-w-screen-xl",
            "2xl": "max-w-screen-2xl",
            "full": "w-full",
        }
        base_classes = size_map.get(size, "max-w-screen-xl")
        if centered:
            base_classes += " mx-auto"
        kwargs["className"] = f"{base_classes} {classes}".strip()
        super().__init__(*children, **kwargs)


# --- Base UI Elements ---


class A(Component):
    tag = "a"

    def __init__(self, *children, href="#", target=None, **kwargs):
        kwargs["href"] = href
        if target:
            kwargs["target"] = target
        classes = kwargs.get("className", "")
        kwargs["className"] = classes
        super().__init__(*children, **kwargs)


class Button(Component):
    tag = "button"

    def __init__(self, *children, on_click=None, **kwargs):
        if on_click:
            kwargs["onclick"] = f"voodoo.sendEvent('{on_click}', this.id, this.value)"

        # We can add minimal robust default styling if desired, but we keep it unopinionated if not provided
        classes = kwargs.get("className", "")
        if "bg-" not in classes and "border" not in classes and "hover:" not in classes:
            # Very minimal neutral styling by default
            kwargs["className"] = (
                f"inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-primary)] disabled:pointer-events-none disabled:opacity-50 bg-[var(--color-text)] text-[var(--color-surface)] hover:bg-[var(--color-text)]/90 h-9 px-4 py-2 {classes}".strip()
            )
        else:
            kwargs["className"] = classes

        super().__init__(*children, **kwargs)


class Card(Component):
    tag = "div"

    def __init__(self, *children, **kwargs):
        classes = kwargs.get("className", "")
        default_bg = "bg-[var(--color-surface)]" if "bg-" not in classes else ""
        default_border = (
            "border border-[var(--color-border)]" if "border" not in classes else ""
        )
        kwargs["className"] = (
            f"{default_bg} {default_border} rounded-xl p-6 shadow-sm {classes}".strip()
        )
        super().__init__(*children, **kwargs)


class Text(Component):
    tag = "span"


class Heading(Component):
    tag = "h1"

    def __init__(self, *children, level=1, **kwargs):
        self.tag = f"h{level}"
        classes = kwargs.get("className", "")
        # Minimalist heading styles based on level
        if "text-" not in classes:
            sizes = {
                1: "text-4xl font-bold tracking-tight",
                2: "text-3xl font-semibold tracking-tight",
                3: "text-2xl font-semibold tracking-tight",
                4: "text-xl font-semibold tracking-tight",
            }
            kwargs["className"] = (
                f"{sizes.get(level, 'text-lg font-medium')} text-[var(--color-text)] {classes}".strip()
            )
        super().__init__(*children, **kwargs)


class Badge(Component):
    tag = "div"

    def __init__(self, *children, variant="default", **kwargs):
        classes = kwargs.get("className", "")
        base_classes = "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"

        variant_map = {
            "default": "bg-[var(--color-text)] text-[var(--color-surface)] hover:bg-[var(--color-text)]/80",
            "secondary": "bg-[var(--color-surface)] text-[var(--color-text)] border border-[var(--color-border)] hover:bg-[var(--color-surface)]/80",
            "outline": "text-[var(--color-text)] border border-[var(--color-border)]",
        }
        v_class = variant_map.get(variant, variant_map["default"])
        kwargs["className"] = f"{base_classes} {v_class} {classes}".strip()
        super().__init__(*children, **kwargs)


class Avatar(Component):
    tag = "div"

    def __init__(self, *children, src=None, alt="", fallback="", **kwargs):
        classes = kwargs.get("className", "")
        kwargs["className"] = (
            f"relative flex h-10 w-10 shrink-0 overflow-hidden rounded-full {classes}".strip()
        )

        if not children:
            if src:
                children = (
                    Component(
                        tag="img",
                        src=src,
                        alt=alt,
                        className="aspect-square h-full w-full object-cover",
                    ),
                )
            else:
                children = (
                    Component(
                        *[fallback],
                        tag="span",
                        className="flex h-full w-full items-center justify-center rounded-full bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text)] text-sm font-medium",
                    ),
                )

        super().__init__(*children, **kwargs)


class Divider(Component):
    tag = "hr"

    def __init__(self, **kwargs):
        classes = kwargs.get("className", "")
        kwargs["className"] = (
            f"m-0 h-px w-full border-none bg-[var(--color-border)] {classes}".strip()
        )
        super().__init__(**kwargs)


class Dialog(Component):
    tag = "dialog"

    def __init__(self, *children, open=False, **kwargs):
        classes = kwargs.get("className", "")
        kwargs["className"] = (
            f"backdrop:bg-black/50 p-0 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-2xl open:flex flex-col {classes}".strip()
        )
        if open:
            kwargs["open"] = True
        super().__init__(*children, **kwargs)


class List(Component):
    tag = "ul"

    def __init__(self, *children, ordered=False, unstyled=False, **kwargs):
        self.tag = "ol" if ordered else "ul"
        classes = kwargs.get("className", "")

        if unstyled:
            base_classes = "list-none pl-0"
        else:
            base_classes = "list-decimal pl-6" if ordered else "list-disc pl-6"

        kwargs["className"] = f"{base_classes} space-y-1 {classes}".strip()
        super().__init__(*children, **kwargs)


class ListItem(Component):
    tag = "li"


# --- Form Elements ---


class Form(Component):
    tag = "form"

    def __init__(self, *children, on_submit=None, **kwargs):
        if on_submit:
            kwargs["onsubmit"] = (
                f"event.preventDefault(); voodoo.sendEvent('{on_submit}', this.id, new FormData(this))"
            )
        super().__init__(*children, **kwargs)


class Label(Component):
    tag = "label"

    def __init__(self, *children, **kwargs):
        classes = kwargs.get("className", "")
        kwargs["className"] = (
            f"block text-sm font-medium leading-none text-[var(--color-text)] peer-disabled:cursor-not-allowed peer-disabled:opacity-70 {classes}".strip()
        )
        super().__init__(*children, **kwargs)


class Input(Component):
    tag = "input"

    def __init__(self, *children, on_change=None, **kwargs):
        if on_change:
            kwargs["onchange"] = f"voodoo.sendEvent('{on_change}', this.id, this.value)"

        classes = kwargs.get("className", "")
        if "type" not in kwargs:
            kwargs["type"] = "text"

        if kwargs.get("type") not in ["checkbox", "radio"]:
            default_classes = "flex h-9 w-full rounded-md border border-[var(--color-border)] bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-[var(--color-text-muted)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-primary)] disabled:cursor-not-allowed disabled:opacity-50"
            kwargs["className"] = f"{default_classes} {classes}".strip()
        else:
            kwargs["className"] = classes

        super().__init__(*children, **kwargs)


class Textarea(Component):
    tag = "textarea"

    def __init__(self, *children, on_change=None, **kwargs):
        if on_change:
            kwargs["onchange"] = f"voodoo.sendEvent('{on_change}', this.id, this.value)"
        classes = kwargs.get("className", "")
        kwargs["className"] = (
            f"flex min-h-[80px] w-full rounded-md border border-[var(--color-border)] bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-[var(--color-text-muted)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-primary)] disabled:cursor-not-allowed disabled:opacity-50 {classes}".strip()
        )
        super().__init__(*children, **kwargs)


class Select(Component):
    tag = "select"

    def __init__(self, *children, on_change=None, **kwargs):
        if on_change:
            kwargs["onchange"] = f"voodoo.sendEvent('{on_change}', this.id, this.value)"
        classes = kwargs.get("className", "")
        kwargs["className"] = (
            f"flex h-9 w-full items-center justify-between rounded-md border border-[var(--color-border)] bg-transparent px-3 py-2 text-sm shadow-sm ring-offset-[var(--color-surface)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)] disabled:cursor-not-allowed disabled:opacity-50 {classes}".strip()
        )
        super().__init__(*children, **kwargs)


class Option(Component):
    tag = "option"


class Checkbox(Component):
    tag = "input"

    def __init__(self, *children, on_change=None, **kwargs):
        kwargs["type"] = "checkbox"
        if on_change:
            kwargs["onchange"] = (
                f"voodoo.sendEvent('{on_change}', this.id, this.checked)"
            )
        classes = kwargs.get("className", "")
        kwargs["className"] = (
            f"peer h-4 w-4 shrink-0 rounded-sm border border-[var(--color-border)] ring-offset-[var(--color-surface)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)] focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-[var(--color-primary)] data-[state=checked]:text-[var(--color-surface)] {classes}".strip()
        )
        super().__init__(*children, **kwargs)


class Radio(Component):
    tag = "input"

    def __init__(self, *children, on_change=None, **kwargs):
        kwargs["type"] = "radio"
        if on_change:
            kwargs["onchange"] = (
                f"voodoo.sendEvent('{on_change}', this.id, this.checked)"
            )
        classes = kwargs.get("className", "")
        kwargs["className"] = (
            f"aspect-square h-4 w-4 rounded-full border border-[var(--color-border)] text-[var(--color-primary)] ring-offset-[var(--color-surface)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)] focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 {classes}".strip()
        )
        super().__init__(*children, **kwargs)


# --- Complex / Composite Components ---


class ChatBox(Component):
    tag = "div"

    def __init__(self, *children, **kwargs):
        classes = kwargs.get("className", "")
        kwargs["className"] = (
            f"flex flex-col space-y-2 overflow-y-auto {classes}".strip()
        )
        super().__init__(*children, **kwargs)


class Table(Component):
    tag = "table"

    def __init__(self, headers: list[str], rows: list[list[Any]], **kwargs):
        super().__init__(**kwargs)
        self.headers = headers
        self.rows = rows

    def render(self) -> str:
        th_cells = "".join(
            f'<th class="px-6 py-4 text-left text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">{h}</th>'
            for h in self.headers
        )
        thead = f"<thead class='bg-[var(--color-surface)] border-b border-[var(--color-border)]'><tr>{th_cells}</tr></thead>"
        tbody_rows = []
        for row in self.rows:
            tds = "".join(
                f'<td class="px-6 py-4 whitespace-nowrap text-sm text-[var(--color-text)]">{cell}</td>'
                for cell in row
            )
            tbody_rows.append(
                f"<tr class='border-b border-[var(--color-border)] hover:bg-[var(--color-surface)] transition-colors'>{tds}</tr>"
            )
        tbody = f"<tbody>{''.join(tbody_rows)}</tbody>"

        attrs = [f'id="{self.id}"']
        for k, v in self.attributes.items():
            if k == "className":
                k = "class"
            attrs.append(f'{k}="{v}"')

        attr_str = " " + " ".join(attrs) if attrs else ""
        return f"<table{attr_str}>{thead}{tbody}</table>"


# --- Semantic HTML Components (SEO & Accessibility) ---


class Nav(Component):
    """Semantic <nav> element for navigation sections."""

    tag = "nav"


class Header(Component):
    """Semantic <header> element for page or section headers."""

    tag = "header"


class Footer(Component):
    """Semantic <footer> element for page or section footers."""

    tag = "footer"


class Main(Component):
    """Semantic <main> element — the dominant content of the page."""

    tag = "main"


class Section(Component):
    """Semantic <section> element for thematic grouping of content."""

    tag = "section"


class Article(Component):
    """Semantic <article> element for self-contained compositions."""

    tag = "article"


class Aside(Component):
    """Semantic <aside> element for tangentially related content."""

    tag = "aside"


class Figure(Component):
    """Semantic <figure> element for self-contained media with optional caption."""

    tag = "figure"


class FigCaption(Component):
    """Semantic <figcaption> element — caption for a <figure>."""

    tag = "figcaption"


class Time(Component):
    """Semantic <time> element with machine-readable datetime attribute."""

    tag = "time"

    def __init__(self, *children, datetime=None, **kwargs):
        if datetime:
            kwargs["datetime"] = datetime
        super().__init__(*children, **kwargs)


class Address(Component):
    """Semantic <address> element for contact information."""

    tag = "address"


class Img(Component):
    """
    Image element with SEO best practices.

    Renders a warning to stderr if no `alt` attribute is provided,
    since alt text is critical for accessibility and SEO.
    """

    tag = "img"

    def __init__(self, *children, src="", alt=None, **kwargs):
        kwargs["src"] = src
        if alt is not None:
            kwargs["alt"] = alt
        else:
            import sys

            print(
                f'[Voodoo SEO Warning] Img(src="{src}") is missing an `alt` attribute. '
                f"Alt text is critical for accessibility and SEO.",
                file=sys.stderr,
            )
            kwargs["alt"] = ""
        super().__init__(*children, **kwargs)


class Paragraph(Component):
    """Semantic <p> element for paragraph text."""

    tag = "p"


# =========================================================================
# Authentication & User UI Components
# =========================================================================


class LoginForm(Component):
    """
    Ready-to-use modern Login Form component with CSRF and error handling.
    """

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
    ):
        super().__init__(**kwargs)
        self.action = action
        self.method = method
        self.title = title
        self.subtitle = subtitle
        self.submit_text = submit_text
        self.redirect_url = redirect_url
        self.csrf_token = csrf_token
        self.username_field = username_field

    def render(self) -> str:
        csrf_input = (
            f'<input type="hidden" name="csrf_token" value="{self.csrf_token}">'
            if self.csrf_token
            else ""
        )
        redirect_input = (
            f'<input type="hidden" name="redirect" value="{self.redirect_url}">'
            if self.redirect_url
            else ""
        )

        return f"""
        <div class="w-full max-w-md mx-auto p-8 rounded-2xl bg-surface border border-border shadow-xl">
            <div class="text-center mb-8">
                <h2 class="text-2xl font-bold tracking-tight text-text">{self.title}</h2>
                <p class="text-sm text-text-muted mt-2">{self.subtitle}</p>
            </div>
            <form action="{self.action}" method="{self.method}" class="space-y-5">
                {csrf_input}
                {redirect_input}
                <div>
                    <label class="block text-xs font-semibold uppercase tracking-wider text-text-muted mb-2">Email or Username</label>
                    <input type="text" name="{self.username_field}" required autocomplete="username"
                        class="w-full px-4 py-2.5 rounded-lg bg-background border border-border text-text placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                        placeholder="you@example.com" />
                </div>
                <div>
                    <label class="block text-xs font-semibold uppercase tracking-wider text-text-muted mb-2">Password</label>
                    <input type="password" name="password" required autocomplete="current-password"
                        class="w-full px-4 py-2.5 rounded-lg bg-background border border-border text-text placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                        placeholder="••••••••" />
                </div>
                <button type="submit"
                    class="w-full py-3 px-4 rounded-lg bg-primary hover:bg-primary-hover text-white font-medium shadow-md hover:shadow-lg transition-all duration-200 cursor-pointer">
                    {self.submit_text}
                </button>
            </form>
        </div>
        """


class RegisterForm(Component):
    """
    Ready-to-use modern Registration Form component.
    """

    def __init__(
        self,
        action: str = "/api/auth/register",
        method: str = "POST",
        title: str = "Create an Account",
        subtitle: str = "Get started in seconds",
        submit_text: str = "Create Account",
        csrf_token: str | None = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.action = action
        self.method = method
        self.title = title
        self.subtitle = subtitle
        self.submit_text = submit_text
        self.csrf_token = csrf_token

    def render(self) -> str:
        csrf_input = (
            f'<input type="hidden" name="csrf_token" value="{self.csrf_token}">'
            if self.csrf_token
            else ""
        )

        return f"""
        <div class="w-full max-w-md mx-auto p-8 rounded-2xl bg-surface border border-border shadow-xl">
            <div class="text-center mb-8">
                <h2 class="text-2xl font-bold tracking-tight text-text">{self.title}</h2>
                <p class="text-sm text-text-muted mt-2">{self.subtitle}</p>
            </div>
            <form action="{self.action}" method="{self.method}" class="space-y-5">
                {csrf_input}
                <div>
                    <label class="block text-xs font-semibold uppercase tracking-wider text-text-muted mb-2">Email Address</label>
                    <input type="email" name="email" required autocomplete="email"
                        class="w-full px-4 py-2.5 rounded-lg bg-background border border-border text-text placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                        placeholder="you@example.com" />
                </div>
                <div>
                    <label class="block text-xs font-semibold uppercase tracking-wider text-text-muted mb-2">Username</label>
                    <input type="text" name="username" required autocomplete="username"
                        class="w-full px-4 py-2.5 rounded-lg bg-background border border-border text-text placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                        placeholder="johndoe" />
                </div>
                <div>
                    <label class="block text-xs font-semibold uppercase tracking-wider text-text-muted mb-2">Password</label>
                    <input type="password" name="password" required autocomplete="new-password" minlength="8"
                        class="w-full px-4 py-2.5 rounded-lg bg-background border border-border text-text placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                        placeholder="Min. 8 characters" />
                </div>
                <button type="submit"
                    class="w-full py-3 px-4 rounded-lg bg-primary hover:bg-primary-hover text-white font-medium shadow-md hover:shadow-lg transition-all duration-200 cursor-pointer">
                    {self.submit_text}
                </button>
            </form>
        </div>
        """


class UserBadge(Component):
    """
    Renders current user profile pill with role and avatar.
    """

    def __init__(
        self,
        user: Any | None = None,
        logout_url: str = "/api/auth/logout",
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self.user = user
        self.logout_url = logout_url

    def render(self) -> str:
        if not self.user or not getattr(self.user, "is_authenticated", False):
            return """
            <div class="inline-flex items-center gap-2">
                <a href="/login" class="text-xs font-semibold text-primary hover:underline">Sign In</a>
            </div>
            """

        display_name = getattr(self.user, "username", None) or getattr(
            self.user, "email", "User"
        )
        initials = display_name[:2].upper() if display_name else "U"
        role = getattr(self.user, "role", "user")

        return f"""
        <div class="inline-flex items-center gap-3 px-3 py-1.5 rounded-full bg-surface border border-border shadow-sm">
            <div class="w-7 h-7 rounded-full bg-primary text-white text-xs font-bold flex items-center justify-center">
                {initials}
            </div>
            <div class="flex flex-col text-left">
                <span class="text-xs font-medium text-text leading-tight">{display_name}</span>
                <span class="text-[10px] text-text-muted uppercase tracking-wider font-semibold">{role}</span>
            </div>
            <a href="{self.logout_url}" title="Log out" class="text-text-muted hover:text-danger ml-1 text-xs transition-colors">
                ✕
            </a>
        </div>
        """


class AuthGuard(Component):
    """
    Renders inner content only when user is authenticated and meets role requirements.
    Otherwise renders fallback component / html.
    """

    def __init__(
        self,
        *children: Any,
        user: Any | None = None,
        required_roles: list[str] | None = None,
        fallback: Any | None = None,
        **kwargs: Any,
    ):
        super().__init__(*children, **kwargs)
        self.user = user
        self.required_roles = required_roles or []
        self.fallback = fallback

    def render(self) -> str:
        if not self.user or not getattr(self.user, "is_authenticated", False):
            if self.fallback:
                return (
                    self.fallback.render()
                    if isinstance(self.fallback, Component)
                    else str(self.fallback)
                )
            return '<div class="p-4 text-center text-sm text-text-muted">Authentication required to view this content.</div>'

        if self.required_roles and not any(
            r in getattr(self.user, "roles", [])
            or r == getattr(self.user, "role", None)
            for r in self.required_roles
        ):
            if self.fallback:
                return (
                    self.fallback.render()
                    if isinstance(self.fallback, Component)
                    else str(self.fallback)
                )
            return '<div class="p-4 text-center text-sm text-danger font-medium">Access restricted: insufficient permissions.</div>'

        return super().render()
