"""Priority 5 — Data-Heavy Interfaces.

Description list, data list, list box, stat group, and enhanced
data table features.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any
from uuid import uuid4

from voodoo.ui.component import Component
from voodoo.ui.events import bind_event

EventHandler = Callable[..., Any] | str


def _data_id(prefix: str) -> str:
    return f"vd-{prefix}-{uuid4().hex[:8]}"


# ── DescriptionList ──────────────────────────────────────────────────────────


class DescriptionList(Component):
    """Key-value pairs with optional sections.

    Renders a semantic ``<dl>`` for settings panels, detail views,
    and property sheets.

    Example::

        DescriptionList(
            DescriptionItem("Name", "Alice"),
            DescriptionItem("Email", "alice@example.com"),
            DescriptionItem("Role", "Admin"),
            DescriptionSection("Billing",
                DescriptionItem("Plan", "Pro"),
                DescriptionItem("Next invoice", "2026-04-01"),
            ),
            label="User details",
        )
    """

    style = "description-list"

    def __init__(
        self,
        *children: Component,
        orientation: str = "vertical",
        label: str | None = None,
        **kwargs: Any,
    ) -> None:
        if orientation not in {"vertical", "horizontal"}:


        attrs: dict[str, Any] = {
            "data_vd_description_list": True,
            "data_vd_orientation": orientation,
        }
        if label:
            attrs["aria_label"] = label

        # Flatten DescriptionItem children into (dt, dd) component pairs
        flattened: list[Any] = []
        for child in children:
            if isinstance(child, DescriptionItem):
                dt, dd = child.render()
                flattened.extend([dt, dd])
            else:
                flattened.append(child)

        super().__init__(*flattened, **attrs, **kwargs)
        self.props = {"orientation": orientation}


class DescriptionItem:
    """A single key-value pair in a :class:`DescriptionList`.

    Because ``<dl>`` requires ``<dt>``/``<dd>`` pairs, this returns a
    pair of components rather than a single component. Use with the
    ``DescriptionList`` which flattens these correctly.
    """

    def __init__(
        self,
        term: str,
        *values: Any,
        key: str | None = None,
        copyable: bool = False,
        href: str | None = None,
    ) -> None:
        self.term = term
        self.values = list(values)
        self.key = key
        self.copyable = copyable
        self.href = href

    def render(self) -> tuple[Component, Component]:
        term_attrs: dict[str, Any] = {}
        if self.key:
            term_attrs["data_vd_description_key"] = self.key
        term_el = _DescTerm(self.term, **term_attrs)

        value_children: list[Any] = []
        for v in self.values:
            if self.href:

            else:
                value_children.append(str(v))

        dd_attrs: dict[str, Any] = {}
        if self.copyable:
            dd_attrs["data_vd_copyable"] = True
        value_el = _DescValue(*value_children, **dd_attrs)

        return term_el, value_el


class _DescTerm(Component):
    tag = "dt"
    style = "description-list.term"
    auto_id = False


class _DescValue(Component):
    tag = "dd"
    style = "description-list.value"
    auto_id = False


class _DescLink(Component):
    tag = "a"
    style = "description-list.link"
    auto_id = False


class DescriptionSection(Component):
    """A grouped section within a :class:`DescriptionList`.

    Renders a heading followed by the description items.
    """

    style = "description-list.section"

    def __init__(
        self,
        title: str,
        *items: DescriptionItem,
        **kwargs: Any,
    ) -> None:
        heading = _DescSectionTitle(title)
        pairs: list[Any] = [heading]
        for item in items:
            dt, dd = item.render()
            pairs.extend([dt, dd])

        super().__init__(*pairs, data_vd_description_section=True, **kwargs)


class _DescSectionTitle(Component):
    tag = "dt"
    style = "description-list.section-title"
    auto_id = False


# ── DataList ─────────────────────────────────────────────────────────────────


class DataList(Component):
    """Tabular key-value data rendered as a semantic ``<dl>`` with structured rows.

    Unlike :class:`DescriptionList` (which is for settings/detail views),
    ``DataList`` is optimized for dense data display with sorting and
    filtering metadata.

    Example::

        DataList(
            DataRow("HTTP Method", "GET"),
            DataRow("Status", "200 OK", highlight=True),
            DataRow("Latency", "42ms"),
            DataRow("Timestamp", "2026-03-15T10:30:00Z"),
            label="Request metadata",
        )
    """

    style = "data-list"

    def __init__(
        self,
        *rows: DataRow,
        label: str | None = None,
        compact: bool = False,
        striped: bool = False,
        **kwargs: Any,
    ) -> None:
        rendered: list[Any] = []
        for row in rows:
            rendered.extend(row.render())

        attrs: dict[str, Any] = {
            "data_vd_data_list": True,
        }
        if compact:
            attrs["data_vd_compact"] = True
        if striped:
            attrs["data_vd_striped"] = True
        if label:
            attrs["aria_label"] = label

        super().__init__(*rendered, **attrs, **kwargs)
        self.props = {"compact": compact, "striped": striped}


class DataRow:
    """A single key-value row in a :class:`DataList`."""

    def __init__(
        self,
        label: str,
        value: Any,
        *,
        key: str | None = None,
        highlight: bool = False,
        monospace: bool = False,
        copyable: bool = False,
        href: str | None = None,
    ) -> None:
        self.label = label
        self.value = value
        self.key = key
        self.highlight = highlight
        self.monospace = monospace
        self.copyable = copyable
        self.href = href

    def render(self) -> tuple[Component, Component]:
        dt_attrs: dict[str, Any] = {}
        if self.key:
            dt_attrs["data_vd_key"] = self.key
        term = _DataTerm(self.label, **dt_attrs)

        dd_attrs: dict[str, Any] = {}
        if self.highlight:
            dd_attrs["data_vd_highlight"] = True
        if self.monospace:
            dd_attrs["data_vd_monospace"] = True
        if self.copyable:
            dd_attrs["data_vd_copyable"] = True

        if self.href:
            value_content: Any = _DataLink(str(self.value), href=self.href)
        else:
            value_content = str(self.value)

        value = _DataValue(value_content, **dd_attrs)
        return term, value


class _DataTerm(Component):
    tag = "dt"
    style = "data-list.term"
    auto_id = False


class _DataValue(Component):
    tag = "dd"
    style = "data-list.value"
    auto_id = False


class _DataLink(Component):
    tag = "a"
    style = "data-list.link"
    auto_id = False


# ── ListBox ──────────────────────────────────────────────────────────────────


class ListBox(Component):
    """Keyboard-navigable list of selectable options.

    Supports single and multi-select, with grouped items and
    optional icons and descriptions.

    Example::

        ListBox(
            ListOption("Python", selected=True, icon=Icon("python")),
            ListOption("TypeScript", icon=Icon("typescript")),
            ListOption("Rust", icon=Icon("rust")),
            ListOption("Go", icon=Icon("go")),
            label="Languages",
            on_select=change_language,
        )
    """

    style = "list-box"

    def __init__(
        self,
        *options: ListOption,
        label: str = "Options",
        multi: bool = False,
        on_select: EventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        if not options:
            raise ValueError("ListBox requires at least one ListOption")

        binding = bind_event(on_select) if on_select else None


        super().__init__(
            _ListBoxGroup(
                *rendered,
                role="listbox",
                aria_label=label,
                aria_multiselectable="true" if multi else None,
            ),
            data_vd_list_box=True,
            data_vd_multi=multi,
            **kwargs,
        )
        self.props = {"multi": multi}


class _ListBoxGroup(Component):
    style = "list-box.group"
    auto_id = False


class ListOption:
    """An option inside a :class:`ListBox`."""

    def __init__(
        self,
        label: str,
        *,
        value: str | None = None,
        description: str | None = None,
        icon: Component | None = None,
        selected: bool = False,
        disabled: bool = False,
    ) -> None:
        self.label = label
        self.value = value or label
        self.description = description
        self.icon = icon
        self.selected = selected
        self.disabled = disabled

    def render_option(self, binding: str | None, multi: bool) -> Component:
        content: list[Any] = []
        if self.icon:
            content.append(_ListOptionIcon(self.icon))
        copy: list[Any] = [_ListOptionLabel(self.label)]
        if self.description:
            copy.append(_ListOptionDescription(self.description))
        content.append(_ListOptionCopy(*copy))

        attrs: dict[str, Any] = {
            "type": "button",
            "role": "option",
            "aria_selected": "true" if self.selected else "false",
            "aria_disabled": "true" if self.disabled else None,
            "tabindex": "0" if self.selected else "-1",
            "data_vd_value": self.value,
        }
        if binding and not self.disabled:
            attrs["data_vd_event_click"] = binding

        return _ListOptionButton(*content, **attrs)


class _ListOptionButton(Component):
    tag = "button"
    style = "list-box.option"
    auto_id = False


class _ListOptionIcon(Component):
    tag = "span"
    style = "list-box.option-icon"
    auto_id = False


class _ListOptionCopy(Component):
    tag = "span"
    style = "list-box.option-copy"
    auto_id = False


class _ListOptionLabel(Component):
    tag = "span"
    style = "list-box.option-label"
    auto_id = False


class _ListOptionDescription(Component):
    tag = "span"
    style = "list-box.option-description"
    auto_id = False


# ── StatGroup ────────────────────────────────────────────────────────────────


class StatGroup(Component):
    """Dashboard-ready group of KPI / metric cards.

    Example::

        StatGroup(
            Stat("Revenue", "$48,200", change="+12%", trend="up"),
            Stat("Users", "2,847", change="+5%", trend="up"),
            Stat("Churn", "3.2%", change="-0.4%", trend="down", invert_trend=True),
            Stat("NPS", "72", change="0", trend="neutral"),
            columns=4,
            label="Key metrics",
        )
    """

    style = "stat-group"

    def __init__(
        self,
        *stats: Stat,
        columns: int = 4,
        label: str = "Statistics",
        **kwargs: Any,
    ) -> None:
        if not stats:
            raise ValueError("StatGroup requires at least one Stat")
        if columns < 1 or columns > 12:
            raise ValueError("StatGroup columns must be between 1 and 12")



        super().__init__(
            *rendered,
            role="region",
            aria_label=label,
            data_vd_stat_group=True,
            data_vd_columns=str(columns),
            **kwargs,
        )
        self.props = {"columns": columns}


class _StatSlot(Component):
    style = "stat-group.slot"
    auto_id = False


class Stat:
    """A single metric in a :class:`StatGroup`."""

    def __init__(
        self,
        label: str,
        value: Any,
        *,
        change: str | None = None,
        trend: str | None = None,
        invert_trend: bool = False,
        icon: Component | None = None,
        prefix: str | None = None,
        suffix: str | None = None,
        description: str | None = None,
    ) -> None:
        self.label = label
        self.value = value
        self.change = change
        self.trend = trend
        self.invert_trend = invert_trend
        self.icon = icon
        self.prefix = prefix
        self.suffix = suffix
        self.description = description

    def render_stat(self) -> Component:
        children: list[Any] = []

        if self.icon:
            children.append(_StatIcon(self.icon))

        children.append(_StatLabel(self.label))

        value_children: list[Any] = []
        if self.prefix:
            value_children.append(_StatPrefix(self.prefix))
        value_children.append(str(self.value))
        if self.suffix:
            value_children.append(_StatSuffix(self.suffix))
        children.append(_StatValue(*value_children))

        if self.change is not None:
            trend = self.trend or "neutral"
            effective_trend = trend
            if self.invert_trend and trend == "up":
                effective_trend = "down"
            elif self.invert_trend and trend == "down":
                effective_trend = "up"
            children.append(
                _StatChange(
                    self.change,
                    data_vd_trend=effective_trend,
                )
            )

        if self.description:
            children.append(_StatDescription(self.description))

        return _StatCard(
            *children,
            data_vd_stat=True,
            data_vd_trend=self.trend if self.trend else None,
        )


class _StatCard(Component):
    style = "stat-group.card"
    auto_id = False


class _StatIcon(Component):
    tag = "span"
    style = "stat-group.icon"
    auto_id = False


class _StatLabel(Component):
    tag = "span"
    style = "stat-group.label"
    auto_id = False


class _StatValue(Component):
    tag = "span"
    style = "stat-group.value"
    auto_id = False


class _StatPrefix(Component):
    tag = "span"
    style = "stat-group.prefix"
    auto_id = False


class _StatSuffix(Component):
    tag = "span"
    style = "stat-group.suffix"
    auto_id = False


class _StatChange(Component):
    tag = "span"
    style = "stat-group.change"
    auto_id = False


class _StatDescription(Component):
    tag = "span"
    style = "stat-group.description"
    auto_id = False


# ── Enhanced DataTable features ──────────────────────────────────────────────


class ColumnDef:
    """Column definition for :class:`EnhancedDataTable`.

    Provides rich column metadata including sort, filter, pin, and
    rendering configuration.

    Example::

        ColumnDef(
            key="name",
            header="Full Name",
            sortable=True,
            filterable=True,
            pinned="left",
            width="200px",
        )
    """

    def __init__(
        self,
        key: str,
        header: str,
        *,
        sortable: bool = False,
        filterable: bool = False,
        pinned: str | None = None,
        width: str | None = None,
        align: str = "left",
        truncate: bool = False,
        monospace: bool = False,
        format_type: str | None = None,
        description: str | None = None,
    ) -> None:
        if pinned and pinned not in {"left", "right"}:
            raise ValueError("ColumnDef pinned must be left or right")
        if align not in {"left", "center", "right"}:
            raise ValueError("ColumnDef align must be left, center, or right")
        self.key = key
        self.header = header
        self.sortable = sortable
        self.filterable = filterable
        self.pinned = pinned
        self.width = width
        self.align = align
        self.truncate = truncate
        self.monospace = monospace
        self.format_type = format_type
        self.description = description

    def render_header(self, binding: str | None) -> Component:
        attrs: dict[str, Any] = {
            "role": "columnheader",
            "aria_sort": "none",
            "data_vd_col": self.key,
        }
        if self.sortable and binding:
            attrs["data_vd_event_click"] = binding
            attrs["tabindex"] = "0"
        if self.pinned:
            attrs["data_vd_pinned"] = self.pinned
        if self.width:
            attrs["style"] = f"width:{self.width}"
        if self.align != "left":

        if self.truncate:
            attrs["data_vd_truncate"] = True
        if self.monospace:
            attrs["data_vd_monospace"] = True
        if self.format_type:
            attrs["data_vd_format"] = self.format_type

        children: list[Any] = [_ColHeaderText(self.header)]
        if self.sortable:
            children.append(_ColSortIcon(aria_hidden="true"))
        if self.description:
            attrs["title"] = self.description

        return _ColHeader(*children, **attrs)


class _ColHeader(Component):
    style = "data-table.col-header"
    auto_id = False


class _ColHeaderText(Component):
    tag = "span"
    style = "data-table.col-header-text"
    auto_id = False


class _ColSortIcon(Component):
    tag = "span"
    style = "data-table.col-sort-icon"
    auto_id = False


class EnhancedDataTable(Component):
    """Data table with column definitions, pinning, column visibility, and density.

    This extends the existing DataTable with structured column metadata,
    column pinning (sticky left/right), column visibility toggling,
    and density modes (compact / default / comfortable).

    Example::

        EnhancedDataTable(
            columns=[
                ColumnDef("name", "Name", sortable=True, pinned="left", width="200px"),
                ColumnDef("email", "Email", sortable=True, filterable=True),
                ColumnDef("role", "Role", filterable=True),
                ColumnDef("last_active", "Last Active", sortable=True, format_type="datetime"),
            ],
            rows=[
                {"name": "Alice", "email": "alice@example.com", "role": "Admin", "last_active": "2h ago"},
                {"name": "Bob", "email": "bob@example.com", "role": "Member", "last_active": "1d ago"},
            ],
            density="default",
            label="Team members",
            on_sort=sort_table,
        )
    """

    style = "enhanced-data-table"

    def __init__(
        self,
        *,
        columns: Sequence[ColumnDef],
        rows: Sequence[dict[str, Any]] = (),
        label: str = "Data table",
        density: str = "default",
        on_sort: EventHandler | None = None,
        on_row_click: EventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        if not columns:
            raise ValueError("EnhancedDataTable requires at least one ColumnDef")
        if density not in {"compact", "default", "comfortable"}:


        sort_binding = bind_event(on_sort) if on_sort else None
        row_binding = bind_event(on_row_click) if on_row_click else None

        # Build headers
        headers = tuple(col.render_header(sort_binding) for col in columns)
        thead = _EnhancedTableHead(_EnhancedTableRow(*headers, role="row"))

        # Build body
        body_rows: list[Component] = []
        for i, row_data in enumerate(rows):
            cells: list[Component] = []
            for col in columns:
                value = row_data.get(col.key, "")
                cell_attrs: dict[str, Any] = {
                    "data_vd_col": col.key,
                    "role": "cell",
                }
                if col.pinned:
                    cell_attrs["data_vd_pinned"] = col.pinned
                if col.truncate:
                    cell_attrs["data_vd_truncate"] = True
                if col.monospace:
                    cell_attrs["data_vd_monospace"] = True
                if col.format_type:
                    cell_attrs["data_vd_format"] = col.format_type


            row_attrs: dict[str, Any] = {
                "role": "row",
                "data_vd_row_index": str(i),
            }
            if row_binding:
                row_attrs["data_vd_event_click"] = row_binding
            body_rows.append(_EnhancedTableRow(*cells, **row_attrs))

        tbody = _EnhancedTableBody(*body_rows)

        super().__init__(
            _EnhancedTableContainer(
                _EnhancedTable(
                    thead,
                    tbody,
                    role="table",
                    aria_label=label,
                ),
            ),
            data_vd_enhanced_table=True,
            data_vd_density=density,
            **kwargs,
        )
        self.props = {
            "density": density,
            "column_count": len(columns),
            "row_count": len(rows),
        }


class _EnhancedTableContainer(Component):
    style = "enhanced-data-table.container"
    auto_id = False


class _EnhancedTable(Component):
    tag = "table"
    style = "enhanced-data-table.table"
    auto_id = False


class _EnhancedTableHead(Component):
    tag = "thead"
    style = "enhanced-data-table.head"
    auto_id = False


class _EnhancedTableBody(Component):
    tag = "tbody"
    style = "enhanced-data-table.body"
    auto_id = False


class _EnhancedTableRow(Component):
    tag = "tr"
    style = "enhanced-data-table.row"
    auto_id = False


class _EnhancedTableCell(Component):
    tag = "td"
    style = "enhanced-data-table.cell"
    auto_id = False
