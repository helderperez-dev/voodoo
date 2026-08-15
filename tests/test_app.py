"""Tests for the App facade and the @page routing primitive."""

import pytest
from starlette.responses import RedirectResponse
from starlette.testclient import TestClient

import voodoo.data
from voodoo import App, Card, Heading, Text, config, page
from voodoo.core.errors import ConfigurationError, VoodooError
from voodoo.core.routing import page_registry
from voodoo.seo import SEO


@pytest.fixture
def make_app(monkeypatch, tmp_path):
    """Factory building App instances against a throwaway in-memory database.

    Register @page routes BEFORE entering the returned TestClient context —
    the Starlette app is assembled on first use.
    """

    real_init_db = voodoo.data.init_db

    async def memory_db(db_path=":memory:"):
        await real_init_db(":memory:")

    monkeypatch.setattr(config, "db_path", ":memory:")
    monkeypatch.setattr(voodoo.data, "init_db", memory_db)

    def _make() -> App:
        return App(app_dir=str(tmp_path / "no-such-app-dir"))

    return _make


def test_app_is_asgi_callable(make_app):
    with TestClient(make_app()) as client:
        assert client.get("/openapi.json").status_code == 200


def test_page_decorator_sync(make_app):
    @page("/")
    def home():
        return Text("Hello Voodoo")

    with TestClient(make_app()) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "Hello Voodoo" in response.text
    assert "<!DOCTYPE html>" in response.text


def test_page_decorator_async(make_app):
    @page("/async")
    async def async_page():
        return Card(Text("async works"))

    with TestClient(make_app()) as client:
        response = client.get("/async")
    assert response.status_code == 200
    assert "async works" in response.text


def test_page_path_param_type_coercion(make_app):
    seen = {}

    @page("/users/{id}")
    async def user(id: int):
        seen["id"] = id
        return Text(f"User {id}")

    with TestClient(make_app()) as client:
        response = client.get("/users/42")
    assert response.status_code == 200
    assert seen["id"] == 42
    assert isinstance(seen["id"], int)
    assert "User 42" in response.text


def test_page_seo_tuple(make_app):
    @page("/seo")
    def seo_page():
        return SEO(title="Custom Title"), Heading("SEO Page")

    with TestClient(make_app()) as client:
        response = client.get("/seo")
    assert response.status_code == 200
    assert "<title>Custom Title</title>" in response.text


def test_page_response_passthrough(make_app):
    @page("/redirect")
    def redirect_page():
        return RedirectResponse("/target", status_code=302)

    with TestClient(make_app()) as client:
        response = client.get("/redirect", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/target"


def test_page_returns_string(make_app):
    @page("/raw")
    def raw_page():
        return "<p>plain string</p>"

    with TestClient(make_app()) as client:
        response = client.get("/raw")
    assert response.status_code == 200
    assert "plain string" in response.text


def test_page_decorator_returns_function_unchanged():
    @page("/x")
    def handler():
        return Text("x")

    assert callable(handler)
    assert handler.voodoo_path == "/x"


def test_page_registry_tracks_routes():
    @page("/registry-check")
    def handler():
        return Text("x")

    assert page_registry.routes
    assert any(r.path == "/registry-check" for r in page_registry.routes)


def test_app_routes_property(make_app):
    app = make_app()
    routes = app.routes
    assert any(getattr(r, "path", None) == "/openapi.json" for r in routes)


def test_app_use_plugin(make_app):
    app = make_app()
    seen = []
    app.use(lambda a: seen.append(a))
    _ = app.routes  # trigger lazy build
    assert seen == [app]


def test_app_theme_applied():
    import voodoo.theme

    original = voodoo.theme.default_theme
    theme = voodoo.theme.Theme()
    try:
        App(theme=theme)
        assert voodoo.theme.default_theme is theme
    finally:
        voodoo.theme.set_theme(original)


def test_app_run_reload_requires_import_string(make_app):
    with pytest.raises(ConfigurationError, match="reload"):
        make_app().run(reload=True)


def test_auth_error_in_voodoo_tree():
    from voodoo.auth import AuthError
    from voodoo.core.errors import AuthError as CoreAuthError

    assert issubclass(AuthError, CoreAuthError)
    assert issubclass(AuthError, VoodooError)


def test_config_debug_flag(monkeypatch):
    from voodoo.config import _resolve_debug

    monkeypatch.setenv("VOODOO_ENV", "development")
    monkeypatch.setenv("VOODOO_DEBUG", "false")
    assert _resolve_debug() is False
    monkeypatch.setenv("VOODOO_DEBUG", "1")
    assert _resolve_debug() is True


def test_config_database_url(monkeypatch):
    from voodoo.config import _resolve_db_path

    monkeypatch.delenv("VOODOO_DB_PATH", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///tmp/foo.db")
    assert _resolve_db_path() == "tmp/foo.db"

    monkeypatch.setenv("DATABASE_URL", "postgres://user:pw@host/db")
    with pytest.raises(ConfigurationError, match="postgres"):
        _resolve_db_path()
