"""Product-level Voodoo UI components.

These components encode recurring software patterns so applications can stay
small without sacrificing hierarchy, accessibility or operational clarity.
They do not own application state; they render the state supplied by callers.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from voodoo.ui.component import Component, escape
from voodoo.ui.events import bind_event
from voodoo.ui.interactive import Button, Input
from voodoo.ui.library import Heading, Icon, Stack, Text

EventHandler = Callable[..., Any] | str


_STATUS_TONES = {
    "online": "success",
    "healthy": "success",
    "success": "success",
    "completed": "success",
    "active": "success",
    "running": "info",
    "executing": "info",
    "info": "info",
    "waiting": "warning",
    "pending": "warning",
    "degraded": "warning",
    "warning": "warning",
    "blocked": "danger",
    "failed": "danger",
    "error": "danger",
    "offline": "muted",
    "unknown": "muted",
    "idle": "muted",
}


class StatusBadge(Component):
    """Compact semantic state indicator with a non-color cue."""

    style = "status-badge"

    def __init__(
        self,
        status: str,
        label: str | None = None,
        *,
        pulse: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        normalized = status.strip().lower()
        tone = _STATUS_TONES.get(normalized, "default")
        self.props = {"status": normalized, "tone": tone, "pulse": pulse}
        self.attrs["data-status"] = normalized
        self.attrs["data-tone"] = tone
        if pulse:
            self.attrs["data-pulse"] = "true"
        display = label or normalized.replace("_", " ").title()
        self.children = (
            _StatusDot(tone=tone),
            Text(display, class_="vd-status-badge-label"),
        )


class _StatusDot(Component):
    tag = "span"
    auto_id = False

    def __init__(self, *, tone: str) -> None:
        super().__init__(class_=f"vd-status-dot vd-status-dot--{tone}", aria_hidden="true")


class Metric(Component):
    """A high-signal metric without forcing a card around it."""

    style = "metric"

    def __init__(
        self,
        label: str,
        value: Any,
        *,
        description: str | None = None,
        change: str | None = None,
        change_tone: str = "muted",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        children: list[Any] = [
            Text(label, class_="vd-metric-label"),
            Text(value, class_="vd-metric-value"),
        ]
        if change:
            children.append(
                Text(
                    change,
                    class_=f"vd-metric-change vd-metric-change--{change_tone}",
                )
            )
        if description:
            children.append(Text(description, class_="vd-metric-description"))
        self.children = tuple(children)


class EmptyState(Component):
    """Useful empty state: what this is, why empty, and what to do next."""

    style = "empty-state"

    def __init__(
        self,
        title: str,
        description: str,
        *,
        action: Component | None = None,
        icon: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        children: list[Any] = []
        if icon:
            children.append(Icon(icon, size="lg", class_="vd-empty-state-icon"))
        children.extend(
            [
                Heading(title, level=3, size="md", class_="vd-empty-state-title"),
                Text(description, class_="vd-empty-state-description"),
            ]
        )
        if action is not None:
            children.append(_ActionSlot(action))
        self.children = tuple(children)


class _ActionSlot(Component):
    auto_id = False

    def __init__(self, child: Component) -> None:
        super().__init__(child, class_="vd-empty-state-action")


@dataclass(frozen=True, slots=True)
class Column:
    key: str
    label: str
    align: str = "start"
    width: str | None = None


class DataTable(Component):
    """Accessible, scan-friendly table for operational and product data.

    ``rows`` can be mappings or ordinary objects. When ``on_select`` is
    supplied, a stable row value is sent to the Python callable. Use
    ``row_key`` to choose that value.
    """

    style = "data-table"

    def __init__(
        self,
        columns: Sequence[Column | tuple[str, str] | str],
        rows: Iterable[Mapping[str, Any] | Any],
        *,
        row_key: str = "id",
        on_select: EventHandler | None = None,
        empty: Component | None = None,
        caption: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        normalized = [self._column(column) for column in columns]
        materialized = list(rows)
        if not materialized and empty is not None:
            self.children = (empty,)
            self.props = {"empty": True}
            return

        caption_html = (
            f'<caption class="vd-data-table-caption">{escape(caption)}</caption>'
            if caption
            else ""
        )
        head = "".join(
            f'<th scope="col" data-align="{escape(column.align)}"'
            + (f' style="width:{escape(column.width)}"' if column.width else "")
            + f">{escape(column.label)}</th>"
            for column in normalized
        )
        body = "".join(
            self._render_row(row, normalized, row_key, on_select)
            for row in materialized
        )
        self._markup = (
            '<div class="vd-data-table-scroll"><table class="vd-data-table-table">'
            f"{caption_html}<thead><tr>{head}</tr></thead><tbody>{body}</tbody>"
            "</table></div>"
        )
        self.props = {"empty": False, "interactive": on_select is not None}

    @staticmethod
    def _column(value: Column | tuple[str, str] | str) -> Column:
        if isinstance(value, Column):
            return value
        if isinstance(value, tuple):
            return Column(value[0], value[1])
        return Column(value, value.replace("_", " ").title())

    @staticmethod
    def _read(row: Mapping[str, Any] | Any, key: str) -> Any:
        if isinstance(row, Mapping):
            return row.get(key)
        return getattr(row, key, None)

    def _render_row(
        self,
        row: Mapping[str, Any] | Any,
        columns: Sequence[Column],
        row_key: str,
        on_select: EventHandler | None,
    ) -> str:
        attrs = ['class="vd-data-table-row"']
        if on_select is not None:
            binding = bind_event(on_select)
            value = self._read(row, row_key)
            attrs.extend(
                [
                    f'data-vd-event-click="{escape(binding)}"',
                    f'data-vd-value="{escape(json.dumps(value, default=str))}"',
                    'tabindex="0"',
                    'role="button"',
                ]
            )
        cells = "".join(
            f'<td data-align="{escape(column.align)}">'
            f"{self._cell(self._read(row, column.key))}</td>"
            for column in columns
        )
        return f"<tr {' '.join(attrs)}>{cells}</tr>"

    @staticmethod
    def _cell(value: Any) -> str:
        if isinstance(value, Component):
            return value.render()
        if value is None:
            return '<span class="vd-data-table-empty-value">—</span>'
        return escape(value)

    def render(self) -> str:
        if self.props.get("empty"):
            return super().render()
        return f"<div{self._render_attrs()}>{self._markup}</div>"


class EventRow(Component):
    """A single chronological event with optional semantic status."""

    style = "event-row"

    def __init__(
        self,
        title: str,
        *,
        detail: str | None = None,
        timestamp: str | None = None,
        status: str | None = None,
        meta: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        copy: list[Any] = [Text(title, class_="vd-event-row-title")]
        if detail:
            copy.append(Text(detail, class_="vd-event-row-detail"))
        if meta:
            copy.append(Text(meta, class_="vd-event-row-meta"))
        tail: list[Any] = []
        if status:
            tail.append(StatusBadge(status))
        if timestamp:
            tail.append(Text(timestamp, class_="vd-event-row-time"))
        self.children = (
            _TimelineRail(),
            _EventCopy(*copy),
            _EventTail(*tail),
        )


class _TimelineRail(Component):
    auto_id = False

    def __init__(self) -> None:
        super().__init__(class_="vd-event-row-rail", aria_hidden="true")


class _EventCopy(Component):
    auto_id = False

    def __init__(self, *children: Any) -> None:
        super().__init__(*children, class_="vd-event-row-copy")


class _EventTail(Component):
    auto_id = False

    def __init__(self, *children: Any) -> None:
        super().__init__(*children, class_="vd-event-row-tail")


class Timeline(Component):
    """Ordered chronological collection of :class:`EventRow` objects."""

    style = "timeline"

    def __init__(self, *events: Component, label: str = "Timeline", **kwargs: Any) -> None:
        super().__init__(*events, **kwargs)
        self.attrs["role"] = "list"
        self.attrs["aria-label"] = label
        for event in events:
            event.attrs.setdefault("role", "listitem")


class InspectorPanel(Component):
    """Context-preserving details panel using native dialog semantics."""

    tag = "dialog"
    style = "inspector-panel"

    def __init__(
        self,
        title: str,
        *children: Any,
        open: bool = False,
        description: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        title_id = f"{self.id}-title"
        self.attrs["aria-labelledby"] = title_id
        if open:
            self.attrs["open"] = True
        header_children: list[Any] = [Heading(title, level=2, size="md", id=title_id)]
        if description:
            header_children.append(Text(description, class_="vd-inspector-description"))
        self.children = (
            _InspectorHeader(*header_children),
            _InspectorBody(*children),
        )


class _InspectorHeader(Component):
    auto_id = False

    def __init__(self, *children: Any) -> None:
        super().__init__(*children, class_="vd-inspector-header")


class _InspectorBody(Component):
    auto_id = False

    def __init__(self, *children: Any) -> None:
        super().__init__(*children, class_="vd-inspector-body")


class LogViewer(Component):
    """Dense readable log surface with an accessible empty state."""

    style = "log-viewer"

    def __init__(
        self,
        lines: Iterable[str],
        *,
        label: str = "Logs",
        empty_text: str = "No log entries yet.",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        materialized = list(lines)
        self.attrs["role"] = "log"
        self.attrs["aria-label"] = label
        self.attrs["aria-live"] = "polite"
        if materialized:
            self.children = tuple(_LogLine(line) for line in materialized)
        else:
            self.children = (Text(empty_text, class_="vd-log-viewer-empty"),)


class _LogLine(Component):
    tag = "code"
    auto_id = False

    def __init__(self, line: str) -> None:
        super().__init__(line, class_="vd-log-line")


class CommandBar(Component):
    """Focused command entry point with a Python callable submit handler."""

    style = "command-bar"

    def __init__(
        self,
        *,
        on_submit: EventHandler,
        placeholder: str = "Search or run a command…",
        action_label: str = "Run",
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        binding = bind_event(on_submit)
        field = Input(
            name="command",
            placeholder=placeholder,
            autocomplete="off",
            aria_label=placeholder,
        )
        self.attrs["data-vd-command-bar"] = "true"
        self.children = (
            Icon("search", class_="vd-command-bar-icon", aria_hidden="true"),
            field,
            Button(action_label, variant="primary", data_vd_command_submit=binding),
        )
        self.attrs["data-vd-command-binding"] = binding
