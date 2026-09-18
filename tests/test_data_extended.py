"""Tests for Priority 5: Data-Heavy Interface components."""

import pytest

from voodoo.adapters import TailwindAdapter, VoodooCSSAdapter
from voodoo.ui import set_style_adapter
from voodoo.ui.data_extended import (
    ColumnDef,
    DataList,
    DataRow,
    DescriptionItem,
    DescriptionList,
    DescriptionSection,
    EnhancedDataTable,
    ListBox,
    ListOption,
    Stat,
    StatGroup,
)
from voodoo.ui.styles import current_adapter


@pytest.fixture(params=[VoodooCSSAdapter, TailwindAdapter])
def adapter(request):
    original = current_adapter()
    set_style_adapter(request.param())
    yield request.param
    set_style_adapter(original)


# ── Description List ────────────────────────────────────────────────────────


def test_description_list_vertical(adapter):
    html = DescriptionList(
        DescriptionItem("Name", "Alice"),
        DescriptionItem("Email", "alice@example.com"),
    ).render()
    assert "Name" in html
    assert "Alice" in html
    assert "Email" in html


def test_description_list_horizontal(adapter):
    html = DescriptionList(
        DescriptionItem("Host", "localhost"),
        orientation="horizontal",
    ).render()
    assert 'data-vd-orientation="horizontal"' in html
    assert "Host" in html


def test_description_item_with_link(adapter):
    html = DescriptionList(
        DescriptionItem(
            "Website",
            "voodoo.dev",
            href="https://voodoo.dev",
        ),
    ).render()
    assert "voodoo.dev" in html
    assert "https://voodoo.dev" in html


def test_description_section(adapter):
    html = DescriptionList(

            DescriptionItem("Name", "App"),
        ),
    ).render()
    assert "General" in html
    assert "Name" in html


# ── Data List ───────────────────────────────────────────────────────────────


def test_data_list_renders(adapter):
    html = DataList(
        DataRow("Status", "Active"),
        DataRow("Version", "2.7.0"),
    ).render()
    assert "Status" in html
    assert "Active" in html


def test_data_list_compact(adapter):
    html = DataList(
        DataRow("A", "1"),
        compact=True,
    ).render()



def test_data_list_striped(adapter):
    html = DataList(
        DataRow("A", "1"),
        DataRow("B", "2"),
        striped=True,
    ).render()



def test_data_row_highlight(adapter):
    html = DataRow("Status", "Critical", highlight=True)
    _, dd = html.render()
    rendered = dd.render()



def test_data_row_monospace(adapter):
    html = DataRow("Hash", "abc123", monospace=True)
    _, dd = html.render()
    rendered = dd.render()



# ── List Box ────────────────────────────────────────────────────────────────


def test_list_box_renders(adapter):
    html = ListBox(
        ListOption("Option A", value="a"),
        ListOption("Option B", value="b"),
    ).render()
    assert 'role="listbox"' in html
    assert "Option A" in html
    assert "Option B" in html


def test_list_box_multi(adapter):
    html = ListBox(
        ListOption("A", value="a"),
        multi=True,
    ).render()
    assert 'aria-multiselectable="true"' in html


def test_list_option_selected(adapter):
    html = ListBox(
        ListOption("Selected", value="s", selected=True),
    ).render()
    assert 'aria-selected="true"' in html


def test_list_option_with_description(adapter):
    html = ListBox(
        ListOption(
            "Pro",
            value="pro",
            description="$9/month",
        ),
    ).render()
    assert "Pro" in html
    assert "$9/month" in html


def test_list_box_with_event(adapter):
    html = ListBox(
        ListOption("A", value="a"),
        on_select=lambda v: v,
    ).render()
    assert "data-vd-event-click" in html


# ── Stat Group ──────────────────────────────────────────────────────────────


def test_stat_group_renders(adapter):
    html = StatGroup(
        Stat("Revenue", "$12,345", trend="up", change="+15%"),
        Stat("Users", "1,234", trend="down", change="-5%"),
    ).render()
    assert "Revenue" in html
    assert "$12,345" in html
    assert "Users" in html
    assert "+15%" in html


def test_stat_group_columns(adapter):
    html = StatGroup(
        Stat("A", "1"),
        Stat("B", "2"),
        Stat("C", "3"),
        columns=3,
    ).render()
    assert 'data-vd-columns="3"' in html


def test_stat_trend(adapter):
    html = StatGroup(
        Stat("X", "100", trend="up"),
    ).render()
    assert 'data-vd-trend="up"' in html


def test_stat_with_prefix_suffix(adapter):
    html = StatGroup(
        Stat("Price", "99", prefix="$", suffix="/mo"),
    ).render()
    assert "$" in html
    assert "/mo" in html


def test_stat_invert_trend(adapter):
    html = StatGroup(
        Stat("Errors", "5", change="-2", trend="down", invert_trend=True),
    ).render()
    # The change badge gets inverted trend (down → up)
    assert 'data-vd-trend="up"' in html


# ── Enhanced Data Table ─────────────────────────────────────────────────────


def test_enhanced_data_table_renders(adapter):
    columns = [
        ColumnDef("name", header="Name"),
        ColumnDef("age", header="Age", sortable=True),
    ]
    rows = [
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 25},
    ]
    html = EnhancedDataTable(columns=columns, rows=rows).render()
    assert "Name" in html
    assert "Age" in html
    assert "Alice" in html
    assert "Bob" in html


def test_enhanced_data_table_sortable(adapter):
    columns = [
        ColumnDef("name", header="Name", sortable=True),
    ]
    html = EnhancedDataTable(columns=columns, rows=[{"name": "X"}]).render()
    assert 'aria-sort="none"' in html


def test_enhanced_data_table_density(adapter):
    columns = [ColumnDef("a", header="A")]
    html = EnhancedDataTable(
        columns=columns,
        rows=[{"a": "1"}],
        density="compact",
    ).render()
    assert 'data-vd-density="compact"' in html


def test_enhanced_data_table_pinned_column(adapter):
    columns = [
        ColumnDef("name", header="Name", pinned="left"),
        ColumnDef("age", header="Age"),
    ]
    html = EnhancedDataTable(
        columns=columns,
        rows=[{"name": "A", "age": 1}],
    ).render()
    assert 'data-vd-pinned="left"' in html


def test_enhanced_data_table_row_click(adapter):
    columns = [ColumnDef("a", header="A")]
    html = EnhancedDataTable(
        columns=columns,
        rows=[{"a": "1"}],
        on_row_click=lambda r: r,
    ).render()
    assert "data-vd-event-click" in html


def test_enhanced_data_table_empty(adapter):
    columns = [ColumnDef("a", header="A")]
    html = EnhancedDataTable(columns=columns, rows=[]).render()
    assert "A" in html
