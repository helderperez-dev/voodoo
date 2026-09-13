from voodoo.adapters.voodoo_css import VoodooCSSAdapter
from voodoo.ui import (
    Button,
    Column,
    CommandBar,
    DataTable,
    EmptyState,
    EventRow,
    InspectorPanel,
    LogViewer,
    Metric,
    StatusBadge,
    Timeline,
)
from voodoo.ui.rendering import render_page
from voodoo.ui.styles import current_adapter, set_style_adapter


def _native():
    original = current_adapter()
    set_style_adapter(VoodooCSSAdapter())
    return original


def test_status_badge_exposes_state_with_non_color_label():
    original = _native()
    try:
        html = StatusBadge("degraded").render()
        assert 'data-status="degraded"' in html
        assert "Degraded" in html
        assert "vd-status-dot--warning" in html
    finally:
        set_style_adapter(original)


def test_metric_is_not_cardified_by_default():
    original = _native()
    try:
        html = Metric("Active devices", 42, change="+3", change_tone="success").render()
        assert "vd-metric" in html
        assert "Active devices" in html
        assert ">42<" in html
        assert "vd-card" not in html
    finally:
        set_style_adapter(original)


def test_empty_state_answers_next_action():
    original = _native()
    try:
        html = EmptyState(
            "No devices",
            "Enroll a device to start receiving observations.",
            action=Button("Enroll"),
            icon="plus",
        ).render()
        assert "No devices" in html
        assert "Enroll a device" in html
        assert "Enroll" in html
    finally:
        set_style_adapter(original)


def test_data_table_accepts_semantic_columns_and_callable_selection():
    original = _native()

    async def select_device(device_id):
        return device_id

    try:
        table = DataTable(
            [Column("name", "Device"), ("status", "Status")],
            [
                {"id": "dev-1", "name": "Edge One", "status": StatusBadge("online")},
                {"id": "dev-2", "name": "Edge Two", "status": StatusBadge("offline")},
            ],
            on_select=select_device,
        )
        html = table.render()
        assert "Edge One" in html
        assert "data-vd-event-click=" in html
        assert "data-vd-value=" in html
        assert 'role="button"' in html
        assert "onclick=" not in html
    finally:
        set_style_adapter(original)


def test_data_table_can_render_meaningful_empty_state():
    original = _native()
    try:
        table = DataTable(
            ["name"],
            [],
            empty=EmptyState("Nothing here", "Create the first resource."),
        )
        html = table.render()
        assert "Nothing here" in html
        assert "Create the first resource" in html
        assert "<table" not in html
    finally:
        set_style_adapter(original)


def test_timeline_preserves_chronological_semantics():
    original = _native()
    try:
        timeline = Timeline(
            EventRow("Execution started", timestamp="10:00", status="running"),
            EventRow("Execution completed", timestamp="10:01", status="completed"),
            label="Execution timeline",
        )
        html = timeline.render()
        assert 'role="list"' in html
        assert 'aria-label="Execution timeline"' in html
        assert html.count('role="listitem"') == 2
    finally:
        set_style_adapter(original)


def test_inspector_panel_preserves_context_with_native_dialog():
    original = _native()
    try:
        html = InspectorPanel(
            "Device edge-01",
            Metric("Battery", "82%"),
            description="Live device context",
            open=True,
        ).render()
        assert html.startswith("<dialog")
        assert "aria-labelledby=" in html
        assert "Live device context" in html
        assert "open" in html
    finally:
        set_style_adapter(original)


def test_log_viewer_has_live_log_semantics_and_empty_state():
    original = _native()
    try:
        html = LogViewer(["boot complete", "connected"]).render()
        assert 'role="log"' in html
        assert 'aria-live="polite"' in html
        assert "boot complete" in html
        empty = LogViewer([]).render()
        assert "No log entries yet" in empty
    finally:
        set_style_adapter(original)


def test_command_bar_binds_python_handler_without_inline_js():
    original = _native()

    async def run_command(value):
        return value

    try:
        html = CommandBar(on_submit=run_command).render()
        assert 'data-vd-command-bar="true"' in html
        assert "data-vd-command-binding=" in html
        assert "data-vd-command-submit=" in html
        assert "onclick=" not in html
        assert "Search or run a command" in html
    finally:
        set_style_adapter(original)


def test_product_css_is_included_in_native_rendering():
    original = _native()
    try:
        html = render_page(Metric("Executions", 12))
        assert "Voodoo Product Components" in html
        assert ".vd-data-table" in html
        assert ".vd-inspector-panel" in html
    finally:
        set_style_adapter(original)
