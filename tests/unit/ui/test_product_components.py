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


def test_status_badge_state_contract_exposes_metadata():
    original = _native()
    try:
        html = StatusBadge(
            "degraded",
            loading=True,
            error="Status unavailable",
        ).render()
        assert 'aria-busy="true"' in html
        assert 'aria-invalid="true"' in html
        assert 'data-vd-error="Status unavailable"' in html
        assert 'data-status="degraded"' in html
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


def test_empty_state_state_contract_suppresses_unavailable_action():
    original = _native()
    try:
        html = EmptyState(
            "Nothing here",
            "Try again later.",
            action=Button("Create"),
            loading=True,
            error="Unavailable",
        ).render()
        assert 'aria-busy="true"' in html
        assert 'aria-invalid="true"' in html
        assert 'data-vd-error="Unavailable"' in html
        assert "Create" not in html
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
        assert 'aria-label="Data table"' in html
    finally:
        set_style_adapter(original)


def test_data_table_caption_is_the_accessible_name():
    original = _native()
    try:
        html = DataTable(["name"], [{"name": "Edge One"}], caption="Devices").render()
        assert '<caption class="vd-data-table-caption">Devices</caption>' in html
        assert 'aria-label="Data table"' not in html
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


def test_data_table_state_contract_suppresses_row_selection():
    original = _native()
    try:
        html = DataTable(
            ["name"],
            [{"id": "dev-1", "name": "Edge One"}],
            on_select=lambda value: value,
            read_only=True,
            loading=True,
            error="Table unavailable",
        ).render()
        assert 'aria-disabled="true"' in html
        assert 'aria-readonly="true"' in html
        assert 'aria-busy="true"' in html
        assert 'aria-invalid="true"' in html
        assert 'data-vd-error="Table unavailable"' in html
        assert "data-vd-event-click" not in html
        assert 'data-vd-error-state="true"' in html
        assert "Table unavailable" in html
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


def test_command_bar_state_contract_suppresses_submit():
    original = _native()

    async def run_command(value):
        return value

    try:
        html = CommandBar(
            on_submit=run_command,
            read_only=True,
            loading=True,
            error="Command unavailable",
        ).render()
        assert 'aria-disabled="true"' in html
        assert 'aria-readonly="true"' in html
        assert 'aria-busy="true"' in html
        assert 'aria-invalid="true"' in html
        assert 'data-vd-error="Command unavailable"' in html
        assert "data-vd-command-binding" not in html
        assert "data-vd-command-submit" not in html
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


def test_data_table_loading_state_is_visible_and_semantic():
    original = _native()
    try:
        html = DataTable(["name", "status"], [], loading=True).render()
        assert 'data-vd-loading-state="true"' in html
        assert "Loading…" in html
        assert 'aria-live="polite"' in html
        assert 'colspan="2"' in html
    finally:
        set_style_adapter(original)


def test_data_table_default_empty_state_is_semantic():
    original = _native()
    try:
        html = DataTable(["name", "status"], []).render()
        assert 'data-vd-empty-state="true"' in html
        assert "No data available" in html
        assert 'aria-live="polite"' in html
        assert 'colspan="2"' in html
    finally:
        set_style_adapter(original)
