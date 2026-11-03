"""Content-addressed static assets: delivery, caching and CSP compatibility."""

import re

import pytest
from starlette.testclient import TestClient

from tests.support import linked_asset_names, page_css, page_js
from voodoo import App, page
from voodoo.ui import Button, Text
from voodoo.ui import assets as assets_module
from voodoo.ui.assets import (
    ASSET_PREFIX,
    publish_asset,
    read_asset,
    reset_assets,
)
from voodoo.ui.rendering import render_page
from voodoo.ui.styles.theme import Theme, default_theme, set_theme


@pytest.fixture(autouse=True)
def _isolated_assets():
    reset_assets()
    yield
    reset_assets()


def test_publish_is_content_addressed_and_idempotent() -> None:
    first = publish_asset("body{color:red}", "css")
    again = publish_asset("body{color:red}", "css")
    other = publish_asset("body{color:blue}", "css")

    assert first is again
    assert first.name != other.name
    assert re.fullmatch(r"[0-9a-f]{16}\.css", first.name)
    assert first.url == f"{ASSET_PREFIX}{first.name}"
    assert read_asset(first.name) is first


def test_publish_rejects_unknown_kinds() -> None:
    with pytest.raises(ValueError, match="unsupported asset kind"):
        publish_asset("x", "exe")


def test_store_is_bounded_and_evicts_oldest_first(monkeypatch) -> None:
    monkeypatch.setattr(assets_module, "_MAX_ASSETS", 3)
    published = [publish_asset(f"a{i}", "js") for i in range(5)]

    assert read_asset(published[0].name) is None
    assert read_asset(published[1].name) is None
    assert all(read_asset(a.name) is a for a in published[2:])


def test_rendered_page_links_assets_instead_of_inlining() -> None:
    html = render_page(Button("Go", variant="primary"))

    assert "<style" not in html
    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>\s*\S", html.split("</head>")[1])
    names = linked_asset_names(html)
    assert any(n.endswith(".css") for n in names)
    assert any(n.endswith(".js") for n in names)
    assert 'rel="stylesheet"' in html
    assert " defer>" in html
    assert len(html) < 20_000
    assert ".vd-button" in page_css(html)
    assert "voodoo" in page_js(html)


def test_stylesheet_url_changes_when_the_theme_changes() -> None:
    original = default_theme
    try:
        before = linked_asset_names(render_page(Text("x")))
        themed = Theme()
        themed.colors.accent = "#0ea5e9"
        set_theme(themed)
        after = linked_asset_names(render_page(Text("x")))
    finally:
        set_theme(original)

    css_before = next(n for n in before if n.endswith(".css"))
    css_after = next(n for n in after if n.endswith(".css"))
    js_before = next(n for n in before if n.endswith(".js"))
    js_after = next(n for n in after if n.endswith(".js"))
    assert css_before != css_after
    assert js_before == js_after


def test_same_theme_renders_the_same_stylesheet_url() -> None:
    first = linked_asset_names(render_page(Text("a")))
    second = linked_asset_names(render_page(Text("b")))

    assert first == second


@pytest.fixture
def client(tmp_path):
    @page("/assets-demo")
    def demo():
        return Text("hello")

    with TestClient(App(app_dir=str(tmp_path))) as test_client:
        yield test_client


def test_asset_route_serves_immutable_cacheable_responses(client) -> None:
    html = client.get("/assets-demo").text
    css_name = next(n for n in linked_asset_names(html) if n.endswith(".css"))

    response = client.get(f"{ASSET_PREFIX}{css_name}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")
    assert response.headers["cache-control"] == ("public, max-age=31536000, immutable")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert ".vd-button" in response.text


def test_asset_route_supports_conditional_requests(client) -> None:
    html = client.get("/assets-demo").text
    js_name = next(n for n in linked_asset_names(html) if n.endswith(".js"))
    url = f"{ASSET_PREFIX}{js_name}"
    etag = client.get(url).headers["etag"]

    revalidated = client.get(url, headers={"If-None-Match": etag})

    assert revalidated.status_code == 304
    assert revalidated.content == b""
    assert revalidated.headers["etag"] == etag


def test_unknown_asset_returns_404(client) -> None:
    assert client.get(f"{ASSET_PREFIX}deadbeefdeadbeef.css").status_code == 404
    assert client.get(f"{ASSET_PREFIX}..%2fsecret.css").status_code == 404
