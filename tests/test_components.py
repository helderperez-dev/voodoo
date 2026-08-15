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
        == '<button id="btn-1" onclick="voodoo.sendEvent(\'my_action\', this.id, this.value)" class="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-primary)] disabled:pointer-events-none disabled:opacity-50 bg-[var(--color-text)] text-[var(--color-surface)] hover:bg-[var(--color-text)]/90 h-9 px-4 py-2">Click Me</button>'
    )


def test_input():
    inp = Input(id="inp-1", on_change="input_changed", type="text")
    html = inp.render()
    assert (
        html
        == '<input id="inp-1" type="text" onchange="voodoo.sendEvent(\'input_changed\', this.id, this.value)" class="flex h-9 w-full rounded-md border border-[var(--color-border)] bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-[var(--color-text-muted)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-primary)] disabled:cursor-not-allowed disabled:opacity-50" />'
    )


def test_card():
    card = Card("Card Content", id="card-1", className="extra-class")
    html = card.render()
    assert (
        html
        == '<div id="card-1" class="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-6 shadow-sm extra-class">Card Content</div>'
    )


def test_text():
    text = Text("Span Text", id="txt-1")
    assert text.render() == '<span id="txt-1">Span Text</span>'


def test_heading():
    h1 = Heading("H1 Title", id="h-1")
    assert (
        h1.render()
        == '<h1 id="h-1" class="text-4xl font-bold tracking-tight text-[var(--color-text)]">H1 Title</h1>'
    )

    h3 = Heading("H3 Title", id="h-3", level=3)
    assert (
        h3.render()
        == '<h3 id="h-3" class="text-2xl font-semibold tracking-tight text-[var(--color-text)]">H3 Title</h3>'
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
        '<th class="px-6 py-4 text-left text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">Name</th>'
        in html
    )
    assert (
        '<td class="px-6 py-4 whitespace-nowrap text-sm text-[var(--color-text)]">Alice</td>'
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
