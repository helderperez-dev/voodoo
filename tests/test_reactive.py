"""Integration tests for the reactive rendering pipeline.

Tests the canonical counter app: state + @event → re-render → WS patch.
"""

import importlib
import json

import pytest
from starlette.testclient import TestClient

import voodoo.data
from voodoo import App, Button, Stack, Text, event, page, state
from voodoo.core.events import event_handlers
from voodoo.core.state import StateRenderer, state_renderer


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

        assert count.get() == 1

    state_renderer.unbind("root")


# ---------------------------------------------------------------------------
# Auto re-render (Phase 4 — State.set triggers bound rerender, zero JS)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_state_set_triggers_bound_rerender(monkeypatch):
    """Binding cells to a renderer makes State.set schedule a patch — the
    reactive loop without explicit rerender() calls in handlers."""
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

    # Simulate the event-loop context of a running handler.
    import asyncio

    count.set(42)
    # The subscription schedules create_task on the running loop; let it run.
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
    assert broadcasted == []  # unsubscribed — no patch
