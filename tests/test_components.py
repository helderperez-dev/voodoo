import pytest

from voodoo.adapters import TailwindAdapter
from voodoo.components import (
    Button,
    Card,
    ChatBox,
    Component,
    Div,
    Heading,
    Input,
    Table,
    Text,
)
from voodoo.ui.styles import current_adapter, set_style_adapter


@pytest.fixture(autouse=True)
def _use_tailwind_adapter():
    original = current_adapter()
    set_style_adapter(TailwindAdapter())
    yield
    set_style_adapter(original)


# ---------------------------------------------------------------------------
# New UI primitives (Phase 4 — less-code initiative)
# ---------------------------------------------------------------------------


class TestIcon:
    def test_renders_curated_svg(self):
        from voodoo.ui import Icon

        icon = Icon("send")
        html = icon.render()
        assert html.startswith("<svg")
        assert "currentColor" in html
        assert html.rstrip().endswith("</svg>")
        # The send glyph (paper plane) path is present.
        assert "M22 2 11 13" in html

    def test_unknown_icon_renders_placeholder(self):
        from voodoo.ui import Icon

        html = Icon("does-not-exist").render()
        assert "<circle" in html  # neutral dot, no raise

    def test_size_and_label(self):
        from voodoo.ui import Icon

        assert 'width="32"' in Icon("bot", size="xl").render()
        labeled = Icon("trash", label="Delete").render()
        assert 'role="img"' in labeled
        assert 'aria-label="Delete"' in labeled


class TestMarkdown:
    def test_headings_and_paragraph(self):
        from voodoo.ui import Markdown

        html = Markdown("# Title\n\nBody text").render()
        assert "<h1>Title</h1>" in html
        assert "<p>Body text</p>" in html

    def test_bold_italic_code(self):
        from voodoo.ui import Markdown

        html = Markdown("**b** *i* `c`").render()
        assert "<strong>b</strong>" in html
        assert "<em>i</em>" in html
        assert "<code>c</code>" in html

    def test_fenced_code_block_escapes_html(self):
        from voodoo.ui import Markdown

        html = Markdown("```python\n<div>x</div>\n```").render()
        assert "<pre><code" in html
        assert "&lt;div&gt;" in html

    def test_raw_html_is_escaped(self):
        from voodoo.ui import Markdown

        html = Markdown("<script>alert(1)</script>").render()
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_lists(self):
        from voodoo.ui import Markdown

        html = Markdown("- a\n- b\n\n1. one\n2. two").render()
        assert "<ul><li>a</li><li>b</li></ul>" in html
        assert "<ol><li>one</li><li>two</li></ol>" in html

    def test_links_only_http(self):
        from voodoo.ui import Markdown

        html = Markdown("[x](https://ok.dev)").render()
        assert '<a href="https://ok.dev"' in html
        bad = Markdown("[x](javascript:alert(1))").render()
        assert "<a href" not in bad


class TestChatPrimitives:
    def test_message_list_renders_children(self):
        from voodoo.ui import MessageList

        ml = MessageList("hello")
        html = ml.render()
        assert "hello" in html

    def test_chat_message_role_modifier(self):
        from voodoo.adapters.voodoo_css import VoodooCSSAdapter
        from voodoo.ui import ChatMessage
        from voodoo.ui.styles import set_style_adapter

        original = current_adapter()
        set_style_adapter(VoodooCSSAdapter())
        try:
            html = ChatMessage("hi", role="assistant").render()
            assert "vd-chat-message--assistant" in html
        finally:
            set_style_adapter(original)

    def test_streaming_text_caret(self):
        from voodoo.ui import StreamingText

        streaming = StreamingText("part").render()
        assert "vd-caret" in streaming
        done = StreamingText("full", done=True).render()
        assert "vd-caret" not in done

    def test_composer_wires_enter_send(self):
        from voodoo.ui import Composer

        html = Composer(on_send="send_message", placeholder="Ask…").render()
        assert 'data-vd-enter-send="send_message"' in html
        assert 'placeholder="Ask…"' in html
        assert 'data-vd-enter-send-trigger="send_message"' in html

    def test_sidebar_renders(self):
        from voodoo.ui import Sidebar

        html = Sidebar("Chats").render()
        assert "Chats" in html


def test_component_base():
    comp = Component("Hello", id="test-1", className="bg-red-500", data_custom="value")
    html = comp.render()
    assert html == '<div id="test-1" class="bg-red-500" data-custom="value">Hello</div>'


def test_div():
    div = Div("Content", id="d1")
    assert div.render() == '<div id="d1">Content</div>'


def test_button():
    btn = Button("Click Me", id="btn-1", on_click="my_action")
    html = btn.render()
    assert (
        html
        == '<button id="btn-1" onclick="voodoo.sendEvent(\'my_action\', this.id, this.value)" class="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--vd-color-primary)] disabled:pointer-events-none disabled:opacity-50 bg-[var(--vd-color-text)] text-[var(--vd-color-surface)] hover:bg-[var(--vd-color-text)]/90 h-9 px-4 py-2">Click Me</button>'
    )


def test_input():
    inp = Input(id="inp-1", on_change="input_changed", type="text")
    html = inp.render()
    assert (
        html
        == '<input id="inp-1" type="text" onchange="voodoo.sendEvent(\'input_changed\', this.id, this.value)" class="flex h-9 w-full rounded-md border border-[var(--vd-color-border)] bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-[var(--vd-color-text-muted)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--vd-color-primary)] disabled:cursor-not-allowed disabled:opacity-50" />'
    )


def test_card():
    card = Card("Card Content", id="card-1", className="extra-class")
    html = card.render()
    assert (
        html
        == '<div id="card-1" class="bg-[var(--vd-color-surface)] border border-[var(--vd-color-border)] rounded-xl p-6 shadow-sm extra-class">Card Content</div>'
    )


def test_text():
    text = Text("Span Text", id="txt-1")
    assert text.render() == '<span id="txt-1">Span Text</span>'


def test_heading():
    h1 = Heading("H1 Title", id="h-1")
    assert (
        h1.render()
        == '<h1 id="h-1" class="text-4xl font-bold tracking-tight text-[var(--vd-color-text)]">H1 Title</h1>'
    )

    h3 = Heading("H3 Title", id="h-3", level=3)
    assert (
        h3.render()
        == '<h3 id="h-3" class="text-2xl font-semibold tracking-tight text-[var(--vd-color-text)]">H3 Title</h3>'
    )


def test_chatbox():
    box = ChatBox("Messages", id="chat-1")
    assert (
        box.render()
        == '<div id="chat-1" class="flex flex-col space-y-2 overflow-y-auto">Messages</div>'
    )


def test_table():
    table = Table(
        headers=["Name", "Age"],
        rows=[["Alice", 30], ["Bob", 25]],
        id="tbl-1",
        className="my-table",
    )
    html = table.render()
    assert html.startswith('<table id="tbl-1" class="my-table">')
    assert (
        '<th class="px-6 py-4 text-left text-xs font-medium text-[var(--vd-color-text-muted)] uppercase tracking-wider">Name</th>'
        in html
    )
    assert (
        '<td class="px-6 py-4 whitespace-nowrap text-sm text-[var(--vd-color-text)]">Alice</td>'
        in html
    )


def test_auth_components():
    from voodoo.auth import AuthUser
    from voodoo.components import AuthGuard, LoginForm, RegisterForm, UserBadge

    # LoginForm
    login_form = LoginForm(action="/login", csrf_token="csrf_123")
    rendered_login = login_form.render()
    assert 'action="/login"' in rendered_login
    assert 'name="csrf_token" value="csrf_123"' in rendered_login
    assert 'name="username"' in rendered_login
    assert 'name="password"' in rendered_login

    # RegisterForm
    reg_form = RegisterForm(action="/register", title="Join Us")
    rendered_reg = reg_form.render()
    assert 'action="/register"' in rendered_reg
    assert "Join Us" in rendered_reg
    assert 'name="email"' in rendered_reg

    # UserBadge - unauthenticated
    badge_anon = UserBadge(user=None)
    assert "Sign In" in badge_anon.render()

    # UserBadge - authenticated
    user = AuthUser(
        id=1,
        email="admin@voodoo.dev",
        username="admin",
        role="admin",
        is_authenticated=True,
    )
    badge_auth = UserBadge(user=user)
    rendered_badge = badge_auth.render()
    assert "admin" in rendered_badge
    assert "AD" in rendered_badge

    # AuthGuard - unauthenticated
    guard_anon = AuthGuard("Secret Vault", user=None, fallback="Please Login")
    assert guard_anon.render() == "Please Login"

    # AuthGuard - authenticated with matching role
    guard_ok = AuthGuard("Secret Vault", user=user, required_roles=["admin"])
    assert "Secret Vault" in guard_ok.render()

    # AuthGuard - role mismatch
    user_viewer = AuthUser(
        id=2, email="viewer@voodoo.dev", role="viewer", is_authenticated=True
    )
    guard_fail = AuthGuard("Secret Vault", user=user_viewer, required_roles=["admin"])
    assert "Access restricted" in guard_fail.render()
