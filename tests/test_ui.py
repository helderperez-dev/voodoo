"""UI component system tests — component contract, adapters, escaping, theme.

These pin the component contract: one render path, adapter-driven classes,
byte-compatible legacy defaults (under TailwindAdapter), semantic
variant/size props, HTML escaping, css={} prop, tone prop, and new
components (Stack, Box, Link).
"""

import pytest

from voodoo.adapters import TailwindAdapter, VoodooCSSAdapter
from voodoo.ui import (
    Box,
    Button,
    Card,
    Component,
    Div,
    Heading,
    Input,
    Link,
    Modal,
    NoopAdapter,
    Page,
    Select,
    Stack,
    Text,
    Textarea,
    set_style_adapter,
)
from voodoo.ui.component import Html, tone_to_color_var
from voodoo.ui.styles import current_adapter

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tailwind_adapter():
    """Use TailwindAdapter for byte-compat golden render tests."""
    original = current_adapter()
    set_style_adapter(TailwindAdapter())
    yield
    set_style_adapter(original)


@pytest.fixture
def voodoo_css_adapter():
    """Use VoodooCSSAdapter for VoodooCSS-specific tests."""
    original = current_adapter()
    set_style_adapter(VoodooCSSAdapter())
    yield
    set_style_adapter(original)


# ---------------------------------------------------------------------------
# Byte-compatible legacy golden renders (Tailwind adapter)
# ---------------------------------------------------------------------------


def test_button_default_matches_legacy(tailwind_adapter):
    btn = Button("Click Me", id="btn-1", on_click="my_action")
    assert btn.render() == (
        '<button id="btn-1" onclick="voodoo.sendEvent(\'my_action\', this.id, this.value)"'
        ' class="inline-flex items-center justify-center rounded-md text-sm font-medium'
        " transition-colors focus-visible:outline-none focus-visible:ring-1"
        " focus-visible:ring-[var(--vd-color-primary)] disabled:pointer-events-none"
        " disabled:opacity-50 bg-[var(--vd-color-text)] text-[var(--vd-color-surface)]"
        ' hover:bg-[var(--vd-color-text)]/90 h-9 px-4 py-2">Click Me</button>'
    )


def test_input_default_matches_legacy(tailwind_adapter):
    inp = Input(id="inp-1", on_change="input_changed", type="text")
    assert inp.render() == (
        '<input id="inp-1" type="text" '
        "onchange=\"voodoo.sendEvent('input_changed', this.id, this.value)\" "
        'class="flex h-9 w-full rounded-md border border-[var(--vd-color-border)] '
        "bg-transparent px-3 py-1 text-sm shadow-sm transition-colors "
        "file:border-0 file:bg-transparent file:text-sm file:font-medium "
        "placeholder:text-[var(--vd-color-text-muted)] focus-visible:outline-none "
        "focus-visible:ring-1 focus-visible:ring-[var(--vd-color-primary)] "
        'disabled:cursor-not-allowed disabled:opacity-50" />'
    )


def test_card_default_matches_legacy(tailwind_adapter):
    card = Card("Card Content", id="card-1", class_="extra-class")
    assert card.render() == (
        '<div id="card-1" class="bg-[var(--vd-color-surface)] border '
        'border-[var(--vd-color-border)] rounded-xl p-6 shadow-sm extra-class">'
        "Card Content</div>"
    )


def test_heading_default_matches_legacy(tailwind_adapter):
    h1 = Heading("H1 Title", id="h-1")
    assert h1.render() == (
        '<h1 id="h-1" class="text-4xl font-bold tracking-tight '
        'text-[var(--vd-color-text)]">H1 Title</h1>'
    )
    h3 = Heading("H3 Title", id="h-3", level=3)
    assert h3.render() == (
        '<h3 id="h-3" class="text-2xl font-semibold tracking-tight '
        'text-[var(--vd-color-text)]">H3 Title</h3>'
    )


def test_chatbox_default_matches_legacy(tailwind_adapter):
    from voodoo.ui import ChatBox

    box = ChatBox("Messages", id="chat-1")
    assert box.render() == (
        '<div id="chat-1" class="flex flex-col space-y-2 overflow-y-auto">'
        "Messages</div>"
    )


def test_table_default_matches_legacy(tailwind_adapter):
    from voodoo.ui import Table

    table = Table(
        headers=["Name", "Age"],
        rows=[["Alice", 30], ["Bob", 25]],
        id="tbl-1",
        class_="my-table",
    )
    html = table.render()
    assert html.startswith('<table id="tbl-1" class="my-table">')
    assert (
        '<th class="px-6 py-4 text-left text-xs font-medium '
        'text-[var(--vd-color-text-muted)] uppercase tracking-wider">Name</th>'
    ) in html
    assert (
        '<td class="px-6 py-4 whitespace-nowrap text-sm '
        'text-[var(--vd-color-text)]">Alice</td>'
    ) in html


def test_component_base_plain_div():
    comp = Component("Hello", id="test-1", class_="bg-red-500", data_custom="value")
    assert (
        comp.render()
        == '<div id="test-1" class="bg-red-500" data-custom="value">Hello</div>'
    )


def test_div_plain():
    div = Div("Content", id="d1")
    assert div.render() == '<div id="d1">Content</div>'


def test_text_plain():
    text = Text("Span Text", id="txt-1")
    assert text.render() == '<span id="txt-1">Span Text</span>'


# ---------------------------------------------------------------------------
# Semantic variant / size props (Tailwind adapter)
# ---------------------------------------------------------------------------


def test_button_variant_primary(tailwind_adapter):
    btn = Button("Save", variant="primary")
    rendered = btn.render()
    assert "bg-[var(--vd-color-primary)]" in rendered
    assert "text-[var(--vd-color-surface)]" in rendered
    assert "hover:bg-[var(--vd-color-primary-hover)]" in rendered
    assert "cursor-pointer" in rendered


def test_button_variant_danger(tailwind_adapter):
    btn = Button("Delete", variant="danger")
    rendered = btn.render()
    assert "bg-[var(--vd-color-danger)]" in rendered
    assert "text-white" in rendered


def test_button_size_sm(tailwind_adapter):
    btn = Button("Small", variant="primary", size="sm")
    rendered = btn.render()
    assert "h-8" in rendered
    assert "text-xs" in rendered


def test_input_size_sm(tailwind_adapter):
    inp = Input(size="sm")
    rendered = inp.render()
    assert "h-8" in rendered
    assert "px-2.5" in rendered


def test_input_hidden_has_no_style():
    inp = Input(type="hidden", name="csrf", value="abc")
    rendered = inp.render()
    assert 'type="hidden"' in rendered
    assert "rounded-md" not in rendered


def test_select_default(tailwind_adapter):
    sel = Select(id="s1")
    rendered = sel.render()
    assert "border-[var(--vd-color-border)]" in rendered
    assert "bg-transparent" in rendered


def test_textarea_default(tailwind_adapter):
    ta = Textarea(id="ta1")
    rendered = ta.render()
    assert "min-h-[80px]" in rendered
    assert "bg-transparent" in rendered


def test_page_component(tailwind_adapter):
    page = Page("Content", id="page-1")
    rendered = page.render()
    assert rendered.startswith("<main ")
    assert "max-w-screen-lg" in rendered
    assert "mx-auto" in rendered


def test_modal_component(tailwind_adapter):
    modal = Modal("Dialog content", id="m1", open=True)
    rendered = modal.render()
    assert rendered.startswith("<dialog ")
    assert 'aria-modal="true"' in rendered
    assert "open" in rendered
    assert "shadow-2xl" in rendered


def test_link_component(tailwind_adapter):
    link = Link("Click here", href="/about", id="lnk-1")
    rendered = link.render()
    assert rendered.startswith("<a ")
    assert 'href="/about"' in rendered
    assert "var(--vd-color-primary)" in rendered


# ---------------------------------------------------------------------------
# VoodooCSS adapter (default)
# ---------------------------------------------------------------------------


def test_voodoo_css_button_default(voodoo_css_adapter):
    btn = Button("Save", id="b1")
    rendered = btn.render()
    assert 'class="vd-button"' in rendered
    assert "Save" in rendered


def test_voodoo_css_button_variant(voodoo_css_adapter):
    btn = Button("Save", variant="primary", id="b1")
    rendered = btn.render()
    assert "vd-button" in rendered
    assert "vd-button--primary" in rendered


def test_voodoo_css_button_size(voodoo_css_adapter):
    btn = Button("Save", variant="primary", size="sm", id="b1")
    rendered = btn.render()
    assert "vd-button--sm" in rendered


def test_voodoo_css_card(voodoo_css_adapter):
    card = Card("Body", id="c1")
    rendered = card.render()
    assert 'class="vd-card"' in rendered


def test_voodoo_css_heading(voodoo_css_adapter):
    h = Heading("Title", level=2, id="h1")
    rendered = h.render()
    assert "vd-heading" in rendered
    assert "vd-heading--h2" in rendered


def test_voodoo_css_input(voodoo_css_adapter):
    inp = Input(id="i1", type="text")
    rendered = inp.render()
    assert "vd-input" in rendered


def test_voodoo_css_link(voodoo_css_adapter):
    link = Link("Go", href="/page", id="l1")
    rendered = link.render()
    assert "vd-link" in rendered


# ---------------------------------------------------------------------------
# Style adapter swap
# ---------------------------------------------------------------------------


def test_adapter_swap_to_noop():
    original = current_adapter()
    try:
        set_style_adapter(NoopAdapter())
        btn = Button("Click", id="b1")
        assert btn.render() == '<button id="b1">Click</button>'

        card = Card("Body", id="c1", class_="custom-card")
        assert card.render() == '<div id="c1" class="custom-card">Body</div>'
    finally:
        set_style_adapter(original)


def test_adapter_swap_to_tailwind():
    original = current_adapter()
    try:
        set_style_adapter(TailwindAdapter())
        btn = Button("Click", id="b1", variant="primary")
        rendered = btn.render()
        assert "inline-flex" in rendered
        assert "bg-[var(--vd-color-primary)]" in rendered
    finally:
        set_style_adapter(original)


# ---------------------------------------------------------------------------
# HTML escaping
# ---------------------------------------------------------------------------


def test_text_children_escaped():
    div = Div("<script>alert('xss')</script>", id="d1")
    rendered = div.render()
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered


def test_attribute_values_escaped():
    div = Div("ok", id="d1", title='"><img onerror=alert(1)>')
    rendered = div.render()
    assert "<img" not in rendered


def test_event_handler_not_escaped():
    btn = Button("Go", id="b1", on_click="my_action")
    rendered = btn.render()
    assert "voodoo.sendEvent('my_action', this.id, this.value)" in rendered


def test_html_escape_hatch():
    raw = Html("<b>bold</b>")
    assert raw.render() == "<b>bold</b>"


# ---------------------------------------------------------------------------
# css={} prop (inline styles)
# ---------------------------------------------------------------------------


def test_css_prop_renders_inline_style():
    btn = Component("Hi", id="c1", css={"margin_top": "2rem"})
    rendered = btn.render()
    assert 'style="margin-top: 2rem"' in rendered


def test_css_prop_multiple():
    div = Div("Hi", id="d1", css={"margin_top": "1rem", "padding": "0.5rem"})
    rendered = div.render()
    assert "margin-top: 1rem" in rendered
    assert "padding: 0.5rem" in rendered


def test_css_prop_underscore_to_hyphen():
    div = Div("Hi", id="d1", css={"border_radius": "8px"})
    rendered = div.render()
    assert "border-radius: 8px" in rendered


# ---------------------------------------------------------------------------
# tone prop (semantic colors)
# ---------------------------------------------------------------------------


def test_text_tone_muted():
    text = Text("Subtitle", tone="muted", id="t1")
    rendered = text.render()
    assert "color: var(--vd-color-text-muted)" in rendered


def test_text_tone_danger():
    text = Text("Error!", tone="danger", id="t1")
    rendered = text.render()
    assert "color: var(--vd-color-danger)" in rendered


def test_text_tone_primary():
    text = Text("Important", tone="primary", id="t1")
    rendered = text.render()
    assert "color: var(--vd-color-primary)" in rendered


def test_text_tone_default_no_style():
    text = Text("Plain", tone="default", id="t1")
    rendered = text.render()
    assert "style=" not in rendered


def test_heading_tone():
    h = Heading("Warning", tone="warning", id="h1")
    rendered = h.render()
    assert "color: var(--vd-color-warning)" in rendered


def test_heading_size():
    h = Heading("Big", size="display", id="h1")
    rendered = h.render()
    assert "font-size: var(--vd-text-display)" in rendered


def test_tone_to_color_var():
    assert tone_to_color_var("primary") == "var(--vd-color-primary)"
    assert tone_to_color_var("danger") == "var(--vd-color-danger)"
    assert tone_to_color_var("default") == ""


# ---------------------------------------------------------------------------
# New components (Stack, Box, Link)
# ---------------------------------------------------------------------------


def test_stack_renders_as_flex_col(tailwind_adapter):
    stack = Stack(Text("A"), Text("B"), gap="lg", id="s1")
    rendered = stack.render()
    assert "flex-col" in rendered
    assert "gap-lg" in rendered
    assert "A" in rendered
    assert "B" in rendered


def test_box_with_padding():
    box = Box(Text("Hello"), padding="lg", id="b1")
    rendered = box.render()
    assert "padding: var(--vd-space-lg)" in rendered
    assert "Hello" in rendered


def test_box_no_padding():
    box = Box(Text("Hello"), id="b1")
    rendered = box.render()
    assert "style=" not in rendered or "padding" not in rendered


def test_link_renders(tailwind_adapter):
    link = Link("Docs", href="/docs", id="l1")
    rendered = link.render()
    assert 'href="/docs"' in rendered
    assert "var(--vd-color-primary)" in rendered


# ---------------------------------------------------------------------------
# Theme semantic tokens
# ---------------------------------------------------------------------------


def test_theme_has_semantic_tokens():
    from voodoo.theme import ThemeColors

    colors = ThemeColors()
    assert colors.primary_hover == "#E4E4E7"
    assert colors.success == "#22C55E"
    assert colors.warning == "#F59E0B"
    assert colors.danger == "#EF4444"


def test_theme_css_variables_include_vd_prefix():
    from voodoo.theme import default_theme

    css = default_theme.to_css_variables()
    assert "--vd-color-primary:" in css
    assert "--vd-color-primary-hover:" in css
    assert "--vd-color-success:" in css
    assert "--vd-color-warning:" in css
    assert "--vd-color-danger:" in css
    assert "--vd-radius-md:" in css
    assert "--vd-space-md:" in css
    assert "--vd-shadow-sm:" in css
    assert "--vd-font-sans:" in css


def test_theme_tailwind_config_has_semantic_names():
    from voodoo.theme import default_theme

    config = default_theme.to_tailwind_config()
    assert '"primary-hover"' in config
    assert '"success"' in config
    assert '"danger"' in config


def test_create_theme_factory():
    from voodoo.theme import create_theme

    theme = create_theme(primary="#635BFF", font="Inter")
    assert theme.colors.primary == "#635BFF"
    assert "Inter" in theme.typography.font_family


def test_theme_spacing_tokens():
    from voodoo.theme import ThemeSpacing

    spacing = ThemeSpacing()
    assert spacing.xs == "0.25rem"
    assert spacing.lg == "1rem"
    assert spacing.xxl == "2rem"


def test_theme_shadows_tokens():
    from voodoo.theme import ThemeShadows

    shadows = ThemeShadows()
    assert "0 1px 2px" in shadows.sm


# ---------------------------------------------------------------------------
# Auth components (rebuilt via composition)
# ---------------------------------------------------------------------------


def test_login_form_composed():
    from voodoo.ui import LoginForm

    form = LoginForm(action="/login", csrf_token="csrf_123")
    rendered = form.render()
    assert 'action="/login"' in rendered
    assert 'name="csrf_token" value="csrf_123"' in rendered
    assert 'name="username"' in rendered
    assert 'name="password"' in rendered
    assert "Sign In" in rendered


def test_register_form_composed():
    from voodoo.ui import RegisterForm

    form = RegisterForm(action="/register", title="Join Us")
    rendered = form.render()
    assert 'action="/register"' in rendered
    assert "Join Us" in rendered
    assert 'name="email"' in rendered


def test_user_badge_anonymous():
    from voodoo.ui import UserBadge

    badge = UserBadge(user=None)
    assert "Sign In" in badge.render()


def test_user_badge_authenticated():
    from voodoo.auth import AuthUser
    from voodoo.ui import UserBadge

    user = AuthUser(
        id=1,
        email="admin@voodoo.dev",
        username="admin",
        role="admin",
        is_authenticated=True,
    )
    badge = UserBadge(user=user)
    rendered = badge.render()
    assert "admin" in rendered
    assert "AD" in rendered


def test_auth_guard_fallback():
    from voodoo.ui import AuthGuard

    guard = AuthGuard("Secret", user=None, fallback="Please Login")
    assert guard.render() == "Please Login"


def test_auth_guard_role_match():
    from voodoo.auth import AuthUser
    from voodoo.ui import AuthGuard

    user = AuthUser(id=1, email="a@b.c", role="admin", is_authenticated=True)
    guard = AuthGuard("Secret", user=user, required_roles=["admin"])
    assert "Secret" in guard.render()


def test_auth_guard_role_mismatch():
    from voodoo.auth import AuthUser
    from voodoo.ui import AuthGuard

    user = AuthUser(id=2, email="v@b.c", role="viewer", is_authenticated=True)
    guard = AuthGuard("Secret", user=user, required_roles=["admin"])
    assert "Access restricted" in guard.render()
