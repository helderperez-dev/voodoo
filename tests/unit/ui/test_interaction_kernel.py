"""Tests for Priority 1: Interaction Kernel components."""

import pytest

from voodoo.adapters import TailwindAdapter, VoodooCSSAdapter
from voodoo.ui import set_style_adapter
from voodoo.ui.interaction_kernel import (
    AlertDialog,
    AlertDialogTrigger,
    Command,
    CommandGroup,
    CommandPalette,
    ContextMenu,
    DismissLayer,
    LayerManager,
    MenuCheckboxItem,
    MenuGroup,
    MenuRadioItem,
    Portal,
    Segment,
    SegmentedControl,
    SubMenu,
    ToggleGroup,
    ToggleItem,
)
from voodoo.ui.interactions import MenuItem
from voodoo.ui.styles import current_adapter


@pytest.fixture(params=[VoodooCSSAdapter, TailwindAdapter])
def adapter(request):
    original = current_adapter()
    set_style_adapter(request.param())
    yield request.param
    set_style_adapter(original)


# ── Alert Dialog ────────────────────────────────────────────────────────────


def test_alert_dialog_renders_with_content(adapter):
    dialog = AlertDialog(
        "This action cannot be undone.",
        title="Confirm Deletion",
    )
    html = dialog.render()
    assert 'role="alertdialog"' in html
    assert 'aria-modal="true"' in html
    assert "Confirm Deletion" in html
    assert "This action cannot be undone." in html


def test_alert_dialog_trigger_opens_dialog(adapter):
    dialog = AlertDialog("Body", title="T", id="my-dlg")
    html = AlertDialogTrigger("Delete", target=dialog).render()
    assert 'data-vd-dialog-open="my-dlg"' in html
    assert 'aria-haspopup="dialog"' in html
    assert "Delete" in html


def test_alert_dialog_trigger_state_contract_blocks_opening(adapter):
    dialog = AlertDialog("Body", title="T", id="danger")
    html = AlertDialogTrigger(
        "Delete",
        target=dialog,
        read_only=True,
        loading=True,
        error="Dialog unavailable",
    ).render()
    assert 'aria-disabled="true"' in html
    assert 'aria-readonly="true"' in html
    assert 'aria-busy="true"' in html
    assert 'data-vd-error="Dialog unavailable"' in html
    assert "data-vd-dialog-open" not in html


def test_alert_dialog_accepts_custom_cancel_and_confirm(adapter):
    html = AlertDialog(
        "Proceed?",
        title="Warning",
        cancel_label="No",
        confirm_label="Yes",
    ).render()
    assert "No" in html
    assert "Yes" in html


def test_alert_dialog_confirm_has_event_binding(adapter):
    html = AlertDialog(
        "Body",
        title="T",
        on_confirm=lambda: None,
    ).render()
    assert "data-vd-event-click" in html


def test_alert_dialog_state_contract_blocks_destructive_actions(adapter):
    html = AlertDialog(
        "Body",
        title="T",
        open=True,
        read_only=True,
        loading=True,
        error="Unavailable",
        on_confirm=lambda: None,
        on_cancel=lambda: None,
    ).render()
    assert 'aria-disabled="true"' in html
    assert 'aria-busy="true"' in html
    assert 'aria-invalid="true"' in html
    assert 'data-vd-error="Unavailable"' in html
    assert 'open="open"' not in html
    assert "data-vd-event-click" not in html


def test_alert_dialog_custom_id(adapter):
    html = AlertDialog("Body", title="T", id="my-dialog").render()
    assert 'id="my-dialog"' in html


def test_alert_dialog_rejects_invalid_tone():
    with pytest.raises(ValueError, match="tone"):
        AlertDialog("X", title="T", tone="invalid")


# ── Toggle Group ────────────────────────────────────────────────────────────


def test_toggle_group_renders_with_items(adapter):
    html = ToggleGroup(
        ToggleItem(value="bold", label="Bold"),
        ToggleItem(value="italic", label="Italic"),
        ToggleItem(value="underline", label="Underline"),
    ).render()
    assert 'role="group"' in html
    assert "Bold" in html
    assert "Italic" in html
    assert "Underline" in html


def test_toggle_group_multiple_mode(adapter):
    html = ToggleGroup(
        ToggleItem(value="a", label="A"),
        ToggleItem(value="b", label="B"),
        type="multiple",
    ).render()
    assert 'data-vd-toggle-type="multiple"' in html


def test_toggle_group_vertical(adapter):
    html = ToggleGroup(
        ToggleItem(value="a", label="A"),
        orientation="vertical",
    ).render()
    assert "vd-toggle-group" in html


def test_toggle_item_has_pressed_state(adapter):
    item = ToggleItem(value="bold", label="Bold")
    html = item.render_toggled(True, False).render()
    assert 'aria-pressed="true"' in html
    assert "Bold" in html


def test_toggle_group_with_event(adapter):
    html = ToggleGroup(
        ToggleItem(value="x", label="X"),
        on_change=lambda v: v,
    ).render()
    assert "data-vd-event-change" in html


def test_toggle_group_disabled(adapter):
    html = ToggleGroup(
        ToggleItem(value="a", label="A"),
        disabled=True,
    ).render()
    assert "disabled" in html


def test_toggle_item_state_contract_propagates_unavailable_state(adapter):
    html = ToggleItem(
        value="a",
        label="A",
        read_only=True,
        loading=True,
        error="Unavailable",
    ).render_toggled(False, False).render()
    assert 'aria-disabled="true"' in html
    assert 'aria-busy="true"' in html
    assert 'aria-invalid="true"' in html
    assert 'data-vd-error="Unavailable"' in html


def test_toggle_group_state_contract_suppresses_unavailable_changes(adapter):
    html = ToggleGroup(
        ToggleItem(value="a", label="A"),
        ToggleItem(value="b", label="B"),
        on_change=lambda value: value,
        read_only=True,
        loading=True,
        error="Unavailable",
    ).render()
    assert 'aria-disabled="true"' in html
    assert 'aria-busy="true"' in html
    assert 'aria-invalid="true"' in html
    assert 'data-vd-error="Unavailable"' in html
    assert "data-vd-event-change" not in html


def test_toggle_group_rejects_empty():
    with pytest.raises(ValueError, match="at least one"):
        ToggleGroup()


def test_toggle_group_rejects_invalid_type():
    with pytest.raises(ValueError, match="type"):
        ToggleGroup(ToggleItem(value="a", label="A"), type="triple")


# ── Segmented Control ───────────────────────────────────────────────────────


def test_segmented_control_renders(adapter):
    html = SegmentedControl(
        Segment("day", label="Day"),
        Segment("week", label="Week"),
        Segment("month", label="Month"),
    ).render()
    assert 'role="tablist"' in html
    assert "Day" in html
    assert "Week" in html
    assert "Month" in html


def test_segment_has_tab_role(adapter):
    seg = Segment("tab", label="Tab")
    html = seg.render_selected(False, False).render()
    assert 'role="tab"' in html
    assert 'aria-selected="false"' in html


def test_segment_state_contract_propagates_unavailable_state(adapter):
    html = Segment(
        "tab",
        label="Tab",
        read_only=True,
        loading=True,
        error="Unavailable",
    ).render_selected(False, False).render()
    assert 'aria-disabled="true"' in html
    assert 'aria-busy="true"' in html
    assert 'aria-invalid="true"' in html
    assert 'data-vd-error="Unavailable"' in html


def test_segmented_control_default_value(adapter):
    html = SegmentedControl(
        Segment("a", label="A"),
        Segment("b", label="B"),
        value="b",
    ).render()
    assert 'aria-selected="true"' in html


def test_segmented_control_state_contract_suppresses_events(adapter):
    html = SegmentedControl(
        Segment("a", label="A"),
        Segment("b", label="B"),
        on_change=lambda value: value,
        read_only=True,
        loading=True,
        error="Choose a view",
    ).render()
    assert 'aria-disabled="true"' in html
    assert 'aria-busy="true"' in html
    assert 'aria-invalid="true"' in html
    assert "data-vd-event-change" not in html
    assert 'data-vd-error="Choose a view"' in html


def test_segmented_control_rejects_empty():
    with pytest.raises(ValueError, match="at least one"):
        SegmentedControl()


# ── Context Menu ────────────────────────────────────────────────────────────


def test_context_menu_renders(adapter):
    from voodoo.ui import Text

    target = Text("Right-click me")
    html = ContextMenu(
        target,
        MenuGroup(
            MenuItem("Cut"),
            MenuItem("Copy"),
            MenuItem("Paste"),
            label="Actions",
        ),
    ).render()
    assert 'role="menu"' in html
    assert "Cut" in html
    assert "Copy" in html
    assert "Paste" in html


def test_context_menu_with_submenu(adapter):
    from voodoo.ui import Text

    html = ContextMenu(
        Text("Target"),
        MenuItem("Open"),
        SubMenu("Share", MenuItem("Email"), MenuItem("Link")),
    ).render()
    assert "Share" in html
    assert "Email" in html


def test_submenu_state_contract_blocks_unavailable_nested_actions(adapter):
    html = SubMenu(
        "Share",
        MenuItem("Email", on_select=lambda: None),
        read_only=True,
        loading=True,
        error="Unavailable",
    ).render()
    assert 'aria-disabled="true"' in html
    assert 'aria-busy="true"' in html
    assert 'aria-invalid="true"' in html
    assert 'data-vd-error="Unavailable"' in html
    assert "data-vd-event-click" not in html


def test_context_menu_checkbox_item(adapter):
    from voodoo.ui import Text

    html = ContextMenu(
        Text("T"),
        MenuCheckboxItem("Show Grid", checked=True),
    ).render()
    assert 'aria-checked="true"' in html
    assert "Show Grid" in html


def test_context_menu_radio_item(adapter):
    from voodoo.ui import Text

    html = ContextMenu(
        Text("T"),
        MenuRadioItem("Small", value="sm", checked=True),
        MenuRadioItem("Large", value="lg"),
    ).render()
    assert 'aria-checked="true"' in html
    assert 'aria-checked="false"' in html


def test_menu_choice_items_state_contract_suppresses_selection(adapter):
    checkbox = MenuCheckboxItem(
        "Grid",
        on_select=lambda: None,
        read_only=True,
        loading=True,
        error="Unavailable",
    ).render()
    radio = MenuRadioItem(
        "Large",
        value="large",
        on_select=lambda: None,
        read_only=True,
        loading=True,
        error="Unavailable",
    ).render()
    for html in (checkbox, radio):
        assert 'aria-disabled="true"' in html
        assert 'aria-busy="true"' in html
        assert 'aria-invalid="true"' in html
        assert 'data-vd-error="Unavailable"' in html
        assert "data-vd-event-click" not in html


def test_context_menu_state_contract_blocks_unavailable_actions(adapter):
    from voodoo.ui import Text

    html = ContextMenu(
        Text("Target"),
        MenuItem("Delete", on_select=lambda: None),
        read_only=True,
        loading=True,
        error="Unavailable",
    ).render()
    assert 'aria-disabled="true"' in html
    assert 'aria-busy="true"' in html
    assert 'aria-invalid="true"' in html
    assert 'data-vd-error="Unavailable"' in html
    assert "data-vd-context-menu=\"" not in html
    assert "data-vd-event-click" not in html


def test_context_menu_rejects_empty():
    from voodoo.ui import Text

    with pytest.raises(ValueError, match="at least one"):
        ContextMenu(Text("T"))


# ── Command Palette ─────────────────────────────────────────────────────────


def test_command_palette_renders(adapter):
    html = CommandPalette(
        CommandGroup(
            "Recent",
            Command("Open File"),
            Command("Save"),
        ),
        placeholder="Type a command…",
    ).render()
    assert 'role="dialog"' in html
    assert 'aria-modal="true"' in html
    assert 'aria-label="Command palette"' in html
    assert "Type a command…" in html
    assert "Open File" in html
    assert "Save" in html


def test_command_palette_custom_label(adapter):
    html = CommandPalette(
        CommandGroup("G", Command("A")),
        label="Quick Actions",
    ).render()
    assert 'aria-label="Quick Actions"' in html


def test_command_with_shortcut(adapter):
    html = CommandPalette(
        CommandGroup("G", Command("Save", shortcut="⌘S")),
    ).render()
    assert "⌘S" in html


def test_command_palette_state_contract_disables_commands(adapter):
    html = CommandPalette(
        CommandGroup("G", Command("Save", on_select=lambda: None)),
        open=True,
        read_only=True,
        loading=True,
        error="Unavailable",
    ).render()
    assert 'aria-disabled="true"' in html
    assert 'aria-busy="true"' in html
    assert 'aria-invalid="true"' in html
    assert 'data-vd-error="Unavailable"' in html
    assert 'data-vd-event-click' not in html
    assert 'open="open"' not in html


@pytest.mark.parametrize(
    "state, expected",
    [
        ({"disabled": True}, 'aria-disabled="true"'),
        ({"read_only": True}, 'aria-readonly="true"'),
        ({"loading": True}, 'aria-busy="true"'),
        ({"error": "command unavailable"}, 'data-vd-error="command unavailable"'),
    ],
)
def test_command_unavailable_states_suppress_selection(adapter, state, expected):
    html = CommandPalette(
        CommandGroup("G", Command("Open", on_select=lambda: None, **state)),
    ).render()
    assert expected in html
    assert "data-vd-event-click" not in html


def test_command_palette_rejects_empty():
    with pytest.raises(ValueError, match="at least one"):
        CommandPalette()


# ── Layer Manager / Portal / Dismiss Layer ──────────────────────────────────


def test_portal_renders_children(adapter):
    html = Portal("Hello").render()
    assert "Hello" in html


def test_layer_manager_renders(adapter):
    html = LayerManager("Layer content").render()
    assert "Layer content" in html


def test_dismiss_layer_has_button(adapter):
    html = DismissLayer().render()
    assert 'aria-hidden="true"' in html
    assert "vd-dismiss-layer" in html
