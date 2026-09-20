from __future__ import annotations

import importlib.util
import sys
from collections.abc import Generator
from pathlib import Path
from types import ModuleType

import pytest

import voodoo.ui.events as ui_events
from voodoo.routing.pages import page_registry


@pytest.fixture
def ui_magic_module() -> Generator[ModuleType, None, None]:
    """Load the example without leaking its routes or event bindings to tests."""
    routes_before = page_registry.routes
    handlers_before = dict(ui_events.event_handlers)
    bindings_before = dict(ui_events.event_bindings)
    callable_bindings_before = dict(ui_events._callable_bindings)

    module_name = "voodoo_ui_magic_acceptance"
    path = Path(__file__).parents[1] / "examples" / "web" / "ui_magic" / "main.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    try:
        yield module
    finally:
        sys.modules.pop(module_name, None)
        page_registry.clear()
        for route in routes_before:
            page_registry.add(route)
        ui_events.event_handlers.clear()
        ui_events.event_handlers.update(handlers_before)
        ui_events.event_bindings.clear()
        ui_events.event_bindings.update(bindings_before)
        ui_events._callable_bindings.clear()
        ui_events._callable_bindings.update(callable_bindings_before)


def test_acceptance_app_is_python_first_and_semantic(ui_magic_module: ModuleType):
    html = ui_magic_module.overview().render()

    assert "A calm view of a changing world" in html
    assert "vd-runtime-status" in html
    assert "vd-data-table" in html
    assert "vd-command-bar" in html
    assert "vd-switch" in html
    assert 'href="/activity"' in html

    assert "data-vd-event-click=" in html
    assert "data-vd-event-change=" in html
    assert "data-vd-event-submit=" in html
    assert 'type="submit"' in html
    assert "Enroll" in html

    assert "onclick=" not in html
    assert "onchange=" not in html
    assert "onsubmit=" not in html


@pytest.mark.asyncio
async def test_acceptance_app_state_changes_are_visible_in_render(
    ui_magic_module: ModuleType,
):
    await ui_magic_module.enroll_device({"name": "Field Node"})
    overview_html = ui_magic_module.overview().render()
    assert "Field Node" in overview_html
    assert "Field Node enrolled successfully." in overview_html

    await ui_magic_module.select_device("edge-04")
    inspector_html = ui_magic_module.overview().render()
    assert "vd-inspector-panel" in inspector_html
    assert "Projected World state" in inspector_html
    assert "battery.level" in inspector_html

    await ui_magic_module.set_live(False)
    paused_html = ui_magic_module.overview().render()
    assert "Live updates paused." in paused_html
    assert 'aria-checked="false"' in paused_html


@pytest.mark.asyncio
async def test_acceptance_app_async_command_flows_into_activity(
    ui_magic_module: ModuleType,
):
    await ui_magic_module.run_command("reconcile edge")
    html = ui_magic_module.activity().render()

    assert "Everything important stays inspectable" in html
    assert "Command completed" in html
    assert "reconcile edge" in html
    assert 'aria-label="Recent runtime activity"' in html
    assert 'data-vd-density="compact"' in html
