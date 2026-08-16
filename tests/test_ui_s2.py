"""Sprint 2 tests — UI component system, style adapter, escaping, theme tokens.

These pin the new component contract: one render path, adapter-driven
classes, byte-compatible legacy defaults, semantic variant/size props, and
HTML escaping.
"""

from voodoo.ui import (
    Button,
    Card,
    Component,
    Div,
    Heading,
    Input,
    Modal,
    NoopAdapter,
    Page,
    Select,
    Textarea,
    set_style_adapter,
)
from voodoo.ui.component import Html
from voodoo.ui.styles import current_adapter

# ---------------------------------------------------------------------------
# Byte-compatible legacy golden renders
# ---------------------------------------------------------------------------


def test_button_default_matches_legacy():
    btn = Button("Click Me", id="btn-1", on_click="my_action")
    assert btn.render() == (
        '<button id="btn-1" onclick="voodoo.sendEvent(\'my_action\', this.id, this.value)"'
        ' class="inline-flex items-center justify-center rounded-md text-sm font-medium'
        " transition-colors focus-visible:outline-none focus-visible:ring-1"
        " focus-visible:ring-[var(--color-primary)] disabled:pointer-events-none"
        " disabled:opacity-50 bg-[var(--color-text)] text-[var(--color-surface)]"
        ' hover:bg-[var(--color-text)]/90 h-9 px-4 py-2">Click Me</button>'
    )


def test_input_default_matches_legacy():
    inp = Input(id="inp-1", on_change="input_changed", type="text")
    assert inp.render() == (
        '<input id="inp-1" type="text" '
        "onchange=\"voodoo.sendEvent('input_changed', this.id, this.value)\" "
        'class="flex h-9 w-full rounded-md border border-[var(--color-border)] '
        "bg-transparent px-3 py-1 text-sm shadow-sm transition-colors "
        "file:border-0 file:bg-transparent file:text-sm file:font-medium "
        "placeholder:text-[var(--color-text-muted)] focus-visible:outline-none "
        "focus-visible:ring-1 focus-visible:ring-[var(--color-primary)] "
        'disabled:cursor-not-allowed disabled:opacity-50" />'
    )


def test_card_default_matches_legacy():
    card = Card("Card Content", id="card-1", class_="extra-class")
    assert card.render() == (
        '<div id="card-1" class="bg-[var(--color-surface)] border '
        'border-[var(--color-border)] rounded-xl p-6 shadow-sm extra-class">'
        "Card Content</div>"
    )


def test_heading_default_matches_legacy():
    h1 = Heading("H1 Title", id="h-1")
    assert h1.render() == (
        '<h1 id="h-1" class="text-4xl font-bold tracking-tight '
        'text-[var(--color-text)]">H1 Title</h1>'
    )
    h3 = Heading("H3 Title", id="h-3", level=3)
    assert h3.render() == (
        '<h3 id="h-3" class="text-2xl font-semibold tracking-tight '
        'text-[var(--color-text)]">H3 Title</h3>'
    )


def test_chatbox_default_matches_legacy():
    from voodoo.ui import ChatBox

    box = ChatBox("Messages", id="chat-1")
    assert box.render() == (
        '<div id="chat-1" class="flex flex-col space-y-2 overflow-y-auto">'
        "Messages</div>"
    )


def test_table_default_matches_legacy():
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
        'text-[var(--color-text-muted)] uppercase tracking-wider">Name</th>'
    ) in html
    assert (
        '<td class="px-6 py-4 whitespace-nowrap text-sm '
        'text-[var(--color-text)]">Alice</td>'
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
    from voodoo.ui import Text

    text = Text("Span Text", id="txt-1")
    assert text.render() == '<span id="txt-1">Span Text</span>'


# ---------------------------------------------------------------------------
# Semantic variant / size props (new in S2)
# ---------------------------------------------------------------------------


def test_button_variant_primary():
    btn = Button("Save", variant="primary")
    rendered = btn.render()
    assert "bg-[var(--color-primary)]" in rendered
    assert "text-white" in rendered
    assert "hover:bg-[var(--color-primary-hover)]" in rendered
    assert "cursor-pointer" in rendered


def test_button_variant_danger():
    btn = Button("Delete", variant="danger")
    rendered = btn.render()
    assert "bg-[var(--color-danger)]" in rendered
    assert "text-white" in rendered


def test_button_size_sm():
    btn = Button("Small", variant="primary", size="sm")
    rendered = btn.render()
    assert "h-8" in rendered
    assert "text-xs" in rendered


def test_input_size_sm():
    inp = Input(size="sm")
    rendered = inp.render()
    assert "h-8" in rendered
    assert "px-2.5" in rendered


def test_input_hidden_has_no_style():
    inp = Input(type="hidden", name="csrf", value="abc")
    rendered = inp.render()
    assert 'type="hidden"' in rendered
    # hidden inputs should NOT get the input style classes
    assert "rounded-md" not in rendered


def test_select_default():
    sel = Select(id="s1")
    rendered = sel.render()
    assert "border-[var(--color-border)]" in rendered
    assert "bg-transparent" in rendered


def test_textarea_default():
    ta = Textarea(id="ta1")
    rendered = ta.render()
    assert "min-h-[80px]" in rendered
    assert "bg-transparent" in rendered


def test_page_component():
    page = Page("Content", id="page-1")
    rendered = page.render()
    assert rendered.startswith("<main ")
    assert "max-w-screen-lg" in rendered
    assert "mx-auto" in rendered


def test_modal_component():
    modal = Modal("Dialog content", id="m1", open=True)
    rendered = modal.render()
    assert rendered.startswith("<dialog ")
    assert 'aria-modal="true"' in rendered
    assert "open" in rendered
    assert "shadow-2xl" in rendered


# ---------------------------------------------------------------------------
# Style adapter swap
# ---------------------------------------------------------------------------


def test_adapter_swap_to_noop():
    original = current_adapter()
    try:
        set_style_adapter(NoopAdapter())
        btn = Button("Click", id="b1")
        # NoopAdapter returns the user class (empty here) — no framework classes
        assert btn.render() == '<button id="b1">Click</button>'

        card = Card("Body", id="c1", class_="custom-card")
        assert card.render() == '<div id="c1" class="custom-card">Body</div>'
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
    # The raw <img> tag must not appear — it must be escaped
    assert "<img" not in rendered


def test_event_handler_not_escaped():
    btn = Button("Go", id="b1", on_click="my_action")
    rendered = btn.render()
    # Event handlers are framework-generated JS — emitted verbatim
    assert "voodoo.sendEvent('my_action', this.id, this.value)" in rendered


def test_html_escape_hatch():
    raw = Html("<b>bold</b>")
    assert raw.render() == "<b>bold</b>"


# ---------------------------------------------------------------------------
# Theme semantic tokens
# ---------------------------------------------------------------------------


def test_theme_has_semantic_tokens():
    from voodoo.theme import ThemeColors

    colors = ThemeColors()
    assert colors.primary_hover == "#0066D6"
    assert colors.success == "#22C55E"
    assert colors.warning == "#F59E0B"
    assert colors.danger == "#EF4444"


def test_theme_css_variables_include_new_tokens():
    from voodoo.theme import default_theme

    css = default_theme.to_css_variables()
    assert "--color-primary-hover:" in css
    assert "--color-success:" in css
    assert "--color-warning:" in css
    assert "--color-danger:" in css
    assert "--radius-md:" in css


def test_theme_tailwind_config_has_semantic_names():
    from voodoo.theme import default_theme

    config = default_theme.to_tailwind_config()
    assert '"primary-hover"' in config
    assert '"success"' in config
    assert '"danger"' in config


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
