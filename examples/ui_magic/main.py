"""Voodoo UI Magic — Sprint 25 acceptance application.

Run with:

    python examples/ui_magic/main.py

The application intentionally contains no application JavaScript and no custom
CSS. It demonstrates the Voodoo happy path: Python callables, reactive State,
async actions, forms, product components, system components and soft links.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from voodoo import App, page, state
from voodoo.ui import (
    Button,
    Column,
    CommandBar,
    DataTable,
    EmptyState,
    EventRow,
    Field,
    Flex,
    Form,
    Heading,
    Input,
    InspectorPanel,
    Link,
    Metric,
    Page,
    RuntimeStatus,
    Stack,
    StatusBadge,
    Switch,
    Text,
    ThemeToggle,
    Timeline,
    WorldEntityInspector,
)

app = App(theme="default")

_devices = state(
    [
        {"id": "edge-01", "name": "Workshop", "status": "online", "battery": "82%"},
        {"id": "edge-02", "name": "Studio", "status": "degraded", "battery": "31%"},
        {"id": "edge-03", "name": "Lab", "status": "offline", "battery": "—"},
    ]
)
_selected = state(None)
_live = state(True)
_busy = state(False)
_notice = state("All systems observed normally.")
_activity = state(
    [
        {
            "title": "Runtime started",
            "detail": "Operational world is ready",
            "status": "completed",
            "time": "now",
        }
    ]
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S UTC")


def _add_activity(title: str, detail: str, status: str = "completed") -> None:
    _activity.update(
        lambda rows: [
            {"title": title, "detail": detail, "status": status, "time": _now()},
            *rows,
        ][:12]
    )


async def select_device(device_id: str) -> None:
    selected = next(
        (device for device in _devices.get() if device["id"] == device_id),
        None,
    )
    _selected.set(selected)


async def close_inspector() -> None:
    _selected.set(None)


async def set_live(value: bool) -> None:
    _live.set(value)
    _notice.set("Live updates enabled." if value else "Live updates paused.")
    _add_activity("Live mode changed", _notice.get())


async def refresh_devices() -> None:
    _busy.set(True)
    _notice.set("Refreshing device observations…")
    await asyncio.sleep(0.15)
    _devices.update(
        lambda rows: [
            {
                **row,
                "battery": "84%" if row["id"] == "edge-01" else row["battery"],
            }
            for row in rows
        ]
    )
    _notice.set("Observations refreshed without a page reload.")
    _add_activity("Observations refreshed", "3 devices reconciled")
    _busy.set(False)


async def enroll_device(values: dict[str, str]) -> None:
    name = (values.get("name") or "New node").strip()
    next_id = f"edge-{len(_devices.get()) + 1:02d}"
    _devices.update(
        lambda rows: [
            *rows,
            {"id": next_id, "name": name, "status": "online", "battery": "100%"},
        ]
    )
    _notice.set(f"{name} enrolled successfully.")
    _add_activity("Device enrolled", f"{name} · {next_id}")


async def run_command(command: str) -> None:
    command = (command or "").strip()
    if not command:
        return
    _busy.set(True)
    _notice.set(f"Running “{command}”…")
    await asyncio.sleep(0.12)
    _notice.set(f"Command “{command}” completed.")
    _add_activity("Command completed", command)
    _busy.set(False)


def _nav() -> Flex:
    return Flex(
        Flex(
            Text("Voodoo", class_="vd-app-wordmark"),
            StatusBadge("online", "Runtime live", pulse=True),
            items="center",
            gap="md",
        ),
        Flex(
            Link("Overview", href="/"),
            Link("Activity", href="/activity"),
            ThemeToggle(),
            items="center",
            gap="sm",
        ),
        justify="between",
        items="center",
        wrap="wrap",
        gap="lg",
    )


def _runtime_snapshot() -> dict:
    devices = _devices.get()
    failed = sum(1 for device in devices if device["status"] == "offline")
    return {
        "summary": {
            "executions": len(_activity.get()),
            "active_executions": 1 if _busy.get() else 0,
            "waiting_executions": 0,
            "failed_executions": failed,
            "pending_approvals": 0,
            "entities": len(devices),
        }
    }


def _device_table() -> DataTable:
    rows = [
        {
            **device,
            "status_view": StatusBadge(device["status"]),
        }
        for device in _devices.get()
    ]
    return DataTable(
        [
            Column("name", "Device"),
            Column("status_view", "Status"),
            Column("battery", "Battery", align="end"),
        ],
        rows,
        row_key="id",
        on_select=select_device,
        empty=EmptyState(
            "No devices",
            "Enroll a node and Voodoo will begin observing it immediately.",
        ),
        caption="Select a device to inspect its current projected state.",
    )


def _inspector() -> InspectorPanel | None:
    selected = _selected.get()
    if selected is None:
        return None
    entity = {
        "id": selected["id"],
        "type": "device",
        "properties": {
            "name": selected["name"],
            "status": selected["status"],
            "battery.level": selected["battery"],
            "live_updates": _live.get(),
        },
        "relationship_count": 1,
        "observation_count": len(_activity.get()),
    }
    return InspectorPanel(
        selected["name"],
        Stack(
            WorldEntityInspector(entity),
            Button("Close", on_click=close_inspector, variant="ghost"),
            gap="lg",
        ),
        description="Projected World state",
        open=True,
    )


@page("/")
def overview():
    devices = _devices.get()
    online = sum(1 for device in devices if device["status"] == "online")
    degraded = sum(1 for device in devices if device["status"] == "degraded")

    return Page(
        Stack(
            _nav(),
            Stack(
                Text("OPERATIONS", class_="vd-section-label"),
                Heading("A calm view of a changing world", size="xl"),
                Text(
                    "Python describes the interface. Voodoo owns reactivity, events, "
                    "browser transport and visual behavior.",
                    tone="muted",
                ),
                gap="sm",
            ),
            Flex(
                Metric("Online", online, description="Observed now"),
                Metric("Degraded", degraded, description="Needs attention"),
                Metric("Total", len(devices), description="World entities"),
                gap="xxl",
                wrap="wrap",
            ),
            RuntimeStatus(_runtime_snapshot()),
            Stack(
                Flex(
                    Heading("Devices", level=2, size="md"),
                    Button(
                        "Refresh",
                        on_click=refresh_devices,
                        loading=_busy.get(),
                        variant="secondary",
                    ),
                    justify="between",
                    items="center",
                ),
                Text(_notice.get(), tone="muted"),
                _device_table(),
                gap="md",
            ),
            Stack(
                Heading("Runtime controls", level=2, size="md"),
                Switch(
                    "Live updates",
                    description="Keep the interface synchronized with runtime state.",
                    checked=_live.get(),
                    on_change=set_live,
                ),
                CommandBar(on_submit=run_command),
                gap="lg",
            ),
            Form(
                Stack(
                    Heading("Enroll a device", level=2, size="md"),
                    Field(
                        "Name",
                        Input(name="name", placeholder="Workshop sensor"),
                        hint="A friendly name is enough for this demo.",
                        required=True,
                    ),
                    Button("Enroll", variant="primary"),
                    gap="md",
                ),
                on_submit=enroll_device,
            ),
            _inspector(),
            gap="xxl",
        ),
        density="comfortable",
    )


@page("/activity")
def activity():
    events = [
        EventRow(
            row["title"],
            detail=row["detail"],
            timestamp=row["time"],
            status=row["status"],
        )
        for row in _activity.get()
    ]
    return Page(
        Stack(
            _nav(),
            Stack(
                Text("ACTIVITY", class_="vd-section-label"),
                Heading("Everything important stays inspectable", size="xl"),
                Text(
                    "This page is reached through Voodoo soft navigation and shares "
                    "the same reactive Python state.",
                    tone="muted",
                ),
                gap="sm",
            ),
            Timeline(*events, label="Recent runtime activity"),
            gap="xxl",
        ),
        density="compact",
    )


if __name__ == "__main__":
    app.run()
