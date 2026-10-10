"""Integration tests for the reactive rendering pipeline.

Tests the canonical counter app: state + @event → re-render → WS patch.
"""

from __future__ import annotations

import importlib
import json
import re
from pathlib import Path

import pytest
from starlette.testclient import TestClient

import voodoo.data
from voodoo import App, page, state
from voodoo.core.events import event, event_handlers
from voodoo.core.state import StateRenderer, state_renderer
from voodoo.seo import SEO
from voodoo.ui import Button, Stack, Text


@pytest.fixture(autouse=True)
def _clean_event_handlers():
    """Remove test event handlers after each test to avoid registry pollution."""
    yield
    to_remove = [k for k in event_handlers if k.startswith("reactive_")]
    for k in to_remove:
        del event_handlers[k]


@pytest.fixture
def make_app(monkeypatch, tmp_path):
    real_init_db = voodoo.data.init_db

    async def memory_db(db_path=":memory:"):
        await real_init_db(":memory:")

    monkeypatch.setattr(voodoo.data, "init_db", memory_db)

    def _make() -> App:
        return App(app_dir=str(tmp_path / "no-such-app-dir"))

    return _make


def test_counter_app_state_and_event(make_app):
    """The canonical counter example: state + Button → live updates."""
    count = state(0)

    @event
    async def reactive_increment(element_id, value):
        count.set(count.get() + 1)

    @page("/")
    def home():
        return Stack(
            Text(f"Count: {count.get()}", id="count-display"),
            Button("Increment", on_click="reactive_increment"),
        )

    with TestClient(make_app()) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "Count: 0" in response.text


def test_state_renderer_renders_component(make_app):
    """StateRenderer can re-render a page function and return HTML."""
    count = state(5)

    def home():
        return Text(f"Count: {count.get()}", id="count-display")

    renderer = StateRenderer()
    renderer.bind("root", home)
    html = renderer._render_component(home())
    assert "Count: 5" in html


def test_state_renderer_renders_seo_tuple():
    """A (SEO, Component) result renders the component, not the tuple repr."""
    count = state(5)

    def home():
        return (
            SEO(title="Home"),
            Text(f"Count: {count.get()}", id="count-display"),
        )

    renderer = StateRenderer()
    renderer.bind("root", home)
    html = renderer._render_component(home())
    assert "Count: 5" in html
    assert "SEO(" not in html
    assert not html.strip().startswith("(")


@pytest.mark.asyncio
async def test_state_renderer_rerender_unwraps_seo_tuple(monkeypatch):
    """rerender on a (SEO, Component) page patches the body, not a tuple repr."""
    count = state(3)

    def home():
        return SEO(title="Home"), Text(f"Count: {count.get()}")

    renderer = StateRenderer()
    renderer.bind("root", home)

    broadcasted = []

    async def mock_broadcast(element_id, html):
        broadcasted.append((element_id, html))

    state_mod = importlib.import_module("voodoo.core.state")
    monkeypatch.setattr(
        state_mod.StateRenderer, "_broadcast_patch", staticmethod(mock_broadcast)
    )

    result = await renderer.rerender("root")
    assert result is not None
    assert "Count: 3" in result
    assert "SEO(" not in result
    assert len(broadcasted) == 1
    assert "Count: 3" in broadcasted[0][1]
    assert "SEO(" not in broadcasted[0][1]


@pytest.mark.asyncio
async def test_state_renderer_rerender_broadcasts_patch(monkeypatch):
    """StateRenderer.rerender re-runs the page function and broadcasts a patch."""
    count = state(3)

    def home():
        return Text(f"Count: {count.get()}")

    renderer = StateRenderer()
    renderer.bind("root", home)

    broadcasted = []

    async def mock_broadcast(element_id, html):
        broadcasted.append((element_id, html))

    state_mod = importlib.import_module("voodoo.core.state")
    monkeypatch.setattr(
        state_mod.StateRenderer, "_broadcast_patch", staticmethod(mock_broadcast)
    )

    result = await renderer.rerender("root")
    assert result is not None
    assert "Count: 3" in result
    assert len(broadcasted) == 1
    assert broadcasted[0][0] == "root"
    assert "Count: 3" in broadcasted[0][1]


@pytest.mark.asyncio
async def test_state_renderer_rerender_no_binding():
    """rerender returns None when no binding exists for the element_id."""
    renderer = StateRenderer()
    result = await renderer.rerender("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_state_renderer_rerender_async_page(monkeypatch):
    """StateRenderer handles async page functions."""
    count = state(7)

    async def home():
        return Text(f"Count: {count.get()}")

    renderer = StateRenderer()
    renderer.bind("root", home)

    async def mock_broadcast(element_id, html):
        pass

    state_mod = importlib.import_module("voodoo.core.state")
    monkeypatch.setattr(
        state_mod.StateRenderer, "_broadcast_patch", staticmethod(mock_broadcast)
    )

    result = await renderer.rerender("root")
    assert result is not None
    assert "Count: 7" in result


def test_counter_app_full_flow_via_websocket(make_app):
    """End-to-end: WS event → @event handler → state change → broadcast patch."""
    count = state(0)

    @event
    async def reactive_ws_increment(element_id, value):
        count.set(count.get() + 1)
        await state_renderer.rerender("root")

    @page("/")
    def home():
        return Stack(
            Text(f"Count: {count.get()}", id="count-display"),
            Button("Increment", on_click="reactive_ws_increment"),
        )

    with TestClient(make_app()) as client:
        response = client.get("/")
        assert "Count: 0" in response.text

        state_renderer.bind("root", home)

        with client.websocket_connect("/_voodoo_ws") as ws:
            ws.send_text(
                json.dumps(
                    {
                        "type": "event",
                        "event": "reactive_ws_increment",
                        "id": "btn-1",
                        "value": "",
                    }
                )
            )

            msg = json.loads(ws.receive_text())
            assert msg["type"] == "patch"
            assert "Count: 1" in msg["html"]

        from voodoo.ui.events import activate_ui_session

        with activate_ui_session(response.cookies["voodoo_ui_session"]):
            assert count.get() == 1

    state_renderer.unbind("root")


def test_two_browser_sessions_isolate_bindings_state_and_patches(make_app):
    """One browser cannot invoke or receive another session's UI work."""
    count = state(0)

    @page("/")
    def isolated_home():
        async def increment():
            count.set(count.get() + 1)

        return Stack(
            Text(f"Count: {count.get()}", id="count-display"),
            Button("Increment", on_click=increment),
        )

    with TestClient(make_app()) as client:
        response_a = client.get("/")
        session_a = response_a.cookies["voodoo_ui_session"]
        binding_a = re.search(r'data-vd-event-click="([^"]+)"', response_a.text)
        assert binding_a is not None

        client.cookies.clear()
        response_b = client.get("/")
        session_b = response_b.cookies["voodoo_ui_session"]
        binding_b = re.search(r'data-vd-event-click="([^"]+)"', response_b.text)
        assert binding_b is not None
        assert session_a != session_b
        assert binding_a.group(1) != binding_b.group(1)

        client.cookies.clear()
        client.cookies.set("voodoo_ui_session", session_a)
        with client.websocket_connect("/_voodoo_ws") as ws_a:
            client.cookies.clear()
            client.cookies.set("voodoo_ui_session", session_b)
            with client.websocket_connect("/_voodoo_ws") as ws_b:
                ws_a.send_json(
                    {
                        "type": "event",
                        "binding": binding_a.group(1),
                        "event_type": "click",
                    }
                )
                patch_a = ws_a.receive_json()
                assert patch_a["type"] == "patch"
                assert "Count: 1" in patch_a["html"]

                # If patches were still broadcast globally, this read would
                # receive A's patch instead of B's authorization-safe error.
                ws_b.send_json(
                    {
                        "type": "event",
                        "binding": binding_a.group(1),
                        "event_type": "click",
                    }
                )
                error_b = ws_b.receive_json()
                assert error_b == {"type": "error", "code": "unknown_binding"}

                ws_b.send_json(
                    {
                        "type": "event",
                        "binding": binding_b.group(1),
                        "event_type": "click",
                    }
                )
                patch_b = ws_b.receive_json()
                assert patch_b["type"] == "patch"
                assert "Count: 1" in patch_b["html"]


def test_application_state_is_shared_only_when_explicit():
    from voodoo.ui.events import activate_ui_session

    session_state = state(0)
    shared_state = state(0, scope="application")

    with activate_ui_session("session-a-with-a-valid-length-0001"):
        session_state.set(7)
        shared_state.set(9)
    with activate_ui_session("session-b-with-a-valid-length-0002"):
        assert session_state.get() == 0
        assert shared_state.get() == 9


@pytest.mark.asyncio
async def test_destroyed_ui_session_discards_bindings_and_state(make_app):
    """Session teardown must remove all server-owned reactive state."""
    count = state(0)

    @page("/")
    def teardown_home():
        async def increment():
            count.set(count.get() + 1)

        return Stack(Text(f"Count: {count.get()}"), Button("Increment", on_click=increment))

    from voodoo.ui.events import dispatch_ui_event, ws_manager

    with TestClient(make_app()) as client:
        response = client.get("/")
        session_id = response.cookies["voodoo_ui_session"]
        binding = re.search(r'data-vd-event-click="([^"]+)"', response.text)
        assert binding is not None
        session = ws_manager.get_session(session_id)
        assert session is not None
        assert binding.group(1) in session.event_bindings
        assert session.state_cells

        ws_manager.destroy_session(session_id)
        assert ws_manager.get_session(session_id) is None
        assert await dispatch_ui_event(
            binding.group(1), event_type="click", session_id=session_id
        ) is False

    assert count.get() == 0


# ---------------------------------------------------------------------------
# Auto re-render (Phase 4 — State.set triggers bound rerender, zero JS)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_page_render_auto_binds_state(make_app):
    """Serving a page that reads State auto-binds it to the renderer.

    The event handler only mutates State. It does not call ``rerender``. The
    browser receives the resulting patch automatically, proving the complete
    zero-manual-rerender loop in isolation from other tests.
    """
    count = state(0)

    @event
    async def reactive_auto_increment(element_id, value):
        count.set(count.get() + 1)

    @page("/")
    def reactive_auto_home():
        return Text(f"Count: {count.get()}", id="count-display")

    with TestClient(make_app()) as client:
        response = client.get("/")
        assert "Count: 0" in response.text

        with client.websocket_connect("/_voodoo_ws") as ws:
            ws.send_text(
                json.dumps(
                    {
                        "type": "event",
                        "event": "reactive_auto_increment",
                        "id": "btn-1",
                    }
                )
            )
            msg = json.loads(ws.receive_text())
            assert msg["type"] == "patch"
            assert msg["id"] == "root"
            assert msg["html"].startswith('<div id="root">')
            assert "Count: 1" in msg["html"]

    state_renderer.unbind("root")


def test_websocket_event_without_id_and_value(make_app):
    """Legacy ``vd.event('name')`` messages without id/value stay tolerated."""

    marker = state("initial")

    @event
    async def reactive_no_id(element_id, value):
        marker.set("updated")

    @page("/")
    def reactive_no_id_home():
        return Stack(
            Text(marker.get(), id="marker"),
            Button("Go", onclick="vd.event('reactive_no_id')"),
        )

    with TestClient(make_app()) as client:
        response = client.get("/")
        assert "initial" in response.text

        with client.websocket_connect("/_voodoo_ws") as ws:
            ws.send_text(json.dumps({"type": "event", "event": "reactive_no_id"}))
            msg = json.loads(ws.receive_text())
            assert msg["type"] == "patch"
            assert "updated" in msg["html"]

    state_renderer.unbind("root")


def test_client_js_exposes_vd_facade():
    """The legacy window.vd facade remains available during migration."""
    import voodoo

    client_js_path = Path(voodoo.__file__).parent / "static" / "client.js"
    src = client_js_path.read_text(encoding="utf-8")
    assert "window.vd" in src
    assert "event:" in src
    assert "window.voodoo" in src
    assert "sendEvent" in src


@pytest.mark.asyncio
async def test_state_set_triggers_bound_rerender(monkeypatch):
    """State.set schedules a patch without explicit rerender calls."""
    from voodoo.ui.state import StateRenderer
    from voodoo.ui.state import state as ui_state

    count = ui_state(0)

    def home():
        return Text(f"Count: {count.get()}", id="count-display")

    renderer = StateRenderer()
    renderer.bind("root", home, cells=[count])

    broadcasted = []

    async def mock_broadcast(element_id, html):
        broadcasted.append((element_id, html))

    state_mod = importlib.import_module("voodoo.ui.state")
    monkeypatch.setattr(
        state_mod.StateRenderer, "_broadcast_patch", staticmethod(mock_broadcast)
    )

    import asyncio

    count.set(42)
    await asyncio.sleep(0)

    assert count.get() == 42
    assert len(broadcasted) == 1
    assert broadcasted[0][0] == "root"
    assert "Count: 42" in broadcasted[0][1]


@pytest.mark.asyncio
async def test_state_unbind_stops_rerender(monkeypatch):
    from voodoo.ui.state import StateRenderer
    from voodoo.ui.state import state as ui_state

    count = ui_state(0)

    def home():
        return Text(f"Count: {count.get()}")

    renderer = StateRenderer()
    renderer.bind("root", home, cells=[count])
    renderer.unbind("root")

    broadcasted = []

    async def mock_broadcast(element_id, html):
        broadcasted.append((element_id, html))

    state_mod = importlib.import_module("voodoo.ui.state")
    monkeypatch.setattr(
        state_mod.StateRenderer, "_broadcast_patch", staticmethod(mock_broadcast)
    )

    import asyncio

    count.set(99)
    await asyncio.sleep(0)
    assert broadcasted == []
