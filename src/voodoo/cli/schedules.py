"""voodoo schedules — list/inspect/pause/resume durable schedules."""

from __future__ import annotations

import typer

from voodoo.cli import terminal

schedules_app = typer.Typer(
    name="schedules",
    help="List and manage durable schedules.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _get_store():
    from voodoo.config import config
    from voodoo.storage.scheduler import SQLiteScheduleStore

    store_path = config.db_path.replace("data.db", "schedules.db")
    try:
        return SQLiteScheduleStore(store_path), store_path
    except Exception:
        return None, store_path


@schedules_app.command("list")
def list_schedules(
    json_mode: bool = typer.Option(False, "--json", help="Machine-readable JSON"),
):
    """List all schedules."""
    store, store_path = _get_store()
    if store is None:
        if json_mode or terminal.is_json_mode():
            terminal.json_output({"error": f"cannot open store at {store_path}"})
            return
        terminal.wordmark()
        terminal.blank()
        terminal.muted(f"cannot open store at {store_path}")
        return

    try:
        schedules = store.list_all()
        if json_mode or terminal.is_json_mode():
            terminal.json_output(schedules)
            return
        terminal.wordmark()
        terminal.blank()
        terminal.status_block(
            [("store", store_path), ("schedules", str(len(schedules)))]
        )
        terminal.blank()
        if not schedules:
            terminal.muted("no schedules found")
            return
        from rich.table import Table

        table = Table(
            show_header=True, header_style="dim", border_style="#262626", pad_edge=False
        )
        for c in ("id", "name", "kind", "next_run", "task", "active"):
            table.add_column(c)
        for s in schedules:
            table.add_row(
                s["id"][:8],
                s["name"],
                s["kind"],
                s["next_run_at"],
                s["task_type"],
                "yes" if s["active"] else "no",
            )
        terminal.console.print(table)
        terminal.blank()
    finally:
        store.close()


@schedules_app.command("pause")
def pause_schedule(
    schedule_id: str = typer.Argument(..., help="Schedule ID"),
    json_mode: bool = typer.Option(False, "--json", help="Machine-readable JSON"),
):
    """Pause a schedule."""
    store, store_path = _get_store()
    if store is None:
        terminal.json_output({"error": f"cannot open store at {store_path}"})
        return
    try:
        ok = store.pause(schedule_id)
        if json_mode or terminal.is_json_mode():
            terminal.json_output({"paused": ok})
        else:
            terminal.wordmark()
            terminal.blank()
            if ok:
                terminal.status("schedule", f"paused {schedule_id}")
            else:
                terminal.muted(f"schedule {schedule_id} not found or already paused")
            terminal.blank()
    finally:
        store.close()


@schedules_app.command("resume")
def resume_schedule(
    schedule_id: str = typer.Argument(..., help="Schedule ID"),
    json_mode: bool = typer.Option(False, "--json", help="Machine-readable JSON"),
):
    """Resume a paused schedule."""
    store, store_path = _get_store()
    if store is None:
        terminal.json_output({"error": f"cannot open store at {store_path}"})
        return
    try:
        ok = store.resume(schedule_id)
        if json_mode or terminal.is_json_mode():
            terminal.json_output({"resumed": ok})
        else:
            terminal.wordmark()
            terminal.blank()
            if ok:
                terminal.status("schedule", f"resumed {schedule_id}")
            else:
                terminal.muted(f"schedule {schedule_id} not found or already active")
            terminal.blank()
    finally:
        store.close()
