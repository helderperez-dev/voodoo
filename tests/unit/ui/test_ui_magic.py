from __future__ import annotations

from voodoo.ui import Button, Checkbox, Form, Input, Text, ThemeToggle
from voodoo.ui.events import UIEvent, bind_event, dispatch_ui_event
from voodoo.ui.state import StateRenderer, state


def test_callable_button_uses_opaque_binding_without_inline_js():
    async def save():
        pass

    html = Button("Save", on_click=save).render()

    assert "onclick=" not in html
    assert 'data-vd-event-click="vdui_' in html
    assert "save" not in html


def test_interactive_components_emit_semantic_event_bindings():
    def changed(value):
        return value

    assert "data-vd-event-change" in Input(on_change=changed).render()
    assert "onchange=" not in Input(on_change=changed).render()
    assert "data-vd-event-submit" in Form(on_submit=changed).render()
    checkbox = Checkbox(on_change=changed).render()
    assert "data-vd-event-change" in checkbox
    assert 'type="checkbox"' in checkbox


def test_theme_toggle_contains_no_inline_javascript():
    html = ThemeToggle().render()
    assert "onclick=" not in html
    assert 'data-vd-action="toggle-theme"' in html


async def test_zero_argument_callable_event_handler():
    calls = []

    async def run():
        calls.append("run")

    binding = bind_event(run)
    handled = await dispatch_ui_event(binding, event_type="click", value="ignored")

    assert handled is True
    assert calls == ["run"]


async def test_value_argument_callable_event_handler():
    values = []

    async def search(value):
        values.append(value)

    binding = bind_event(search)
    await dispatch_ui_event(binding, event_type="input", value="voodoo")

    assert values == ["voodoo"]


async def test_ui_event_annotation_opts_into_full_context():
    received = []

    async def inspect_event(event: UIEvent):
        received.append(event)

    binding = bind_event(inspect_event)
    await dispatch_ui_event(
        binding,
        event_type="change",
        element_id="device-mode",
        value="auto",
        meta={"source": "test"},
    )

    assert received[0].type == "change"
    assert received[0].value == "auto"
    assert received[0].element_id == "device-mode"
    assert received[0].meta["source"] == "test"


async def test_reactive_dependencies_are_rediscovered_after_rerender():
    branch = state(True)
    first = state("first")
    second = state("second")
    renderer = StateRenderer()

    def view():
        return Text(first.get() if branch.get() else second.get())

    renderer.bind("region", view, cells=[branch, first])
    branch.set(False)
    await renderer.rerender("region")

    _view, cells = renderer._bindings["region"]
    assert branch in cells
    assert second in cells
    assert first not in cells

    renderer.unbind("region")
