"""voodoo executions — list executions from the durable SQLite store.

Reads the materialized ``executions`` table plus the append-only event
journal. Falls back to the in-memory engine state when no SQLite store is
available.
"""

from __future__ import annotations

import typer

from voodoo.cli import terminal

executions_app = typer.Typer(
    name="executions",
    help="List and inspect durable executions.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _get_store():
    """Return (store, store_path) — SQLite by default, None if unavailable."""
    from voodoo.config import config
    from voodoo.storage.execution import SQLiteExecutionStore

    store_path = config.db_path.replace(":memory:", ".voodoo/state/data.db")
    try:
        store = SQLiteExecutionStore(store_path)
        return store, store_path
    except Exception:
        return None, store_path


@executions_app.command("list")
def list_executions(
    status: str = typer.Option(None, "--status", help="Filter by status"),
    limit: int = typer.Option(20, "--limit", help="Maximum rows"),
    json_mode: bool = typer.Option(False, "--json", help="Machine-readable JSON"),
):
    """List recent executions from the durable store."""
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
        executions = store.load_all()
        if status:
            executions = [e for e in executions if e.status.value == status]
        executions = executions[-limit:]
        if json_mode or terminal.is_json_mode():
            terminal.json_output([e.describe() for e in executions])
            return
        terminal.wordmark()
        terminal.blank()
        terminal.status_block(
            [("store", store_path), ("executions", str(len(executions)))]
        )
        terminal.blank()
        if not executions:
            terminal.muted("no executions found")
            return
        from rich.table import Table

        table = Table(
            show_header=True, header_style="dim", border_style="#262626", pad_edge=False
        )
        for c in ("id", "intent", "status", "actor", "cost"):
            table.add_column(c)
        for ex in executions:
            table.add_row(
                ex.id[:8],
                ex.intent.name if ex.intent else "-",
                ex.status.value,
                ex.actor,
                f"{ex.cost:.4f}",
            )
        terminal.console.print(table)
        terminal.blank()
    finally:
        store.close()


@executions_app.command("show")
def show_execution(
    execution_id: str = typer.Argument(..., help="Execution ID (full or prefix)"),
    json_mode: bool = typer.Option(False, "--json", help="Machine-readable JSON"),
):
    """Show one execution and its event timeline from the journal."""
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
        executions = store.load_all()
        match = next((e for e in executions if e.id.startswith(execution_id)), None)
        if match is None:
            if json_mode or terminal.is_json_mode():
                terminal.json_output({"error": f"execution {execution_id!r} not found"})
                return
            terminal.wordmark()
            terminal.blank()
            terminal.muted(f"execution {execution_id!r} not found")
            return

        timeline = store.timeline(match.id)
        if json_mode or terminal.is_json_mode():
            terminal.json_output({"execution": match.describe(), "timeline": timeline})
            return

        terminal.wordmark()
        terminal.blank()
        d = match.describe()
        terminal.status_block(
            [
                ("id", d["id"]),
                ("trace", d["trace_id"]),
                ("status", d["status"]),
                ("intent", d["intent"] or "-"),
                ("actor", d["actor"]),
                ("cost", f"{d['cost']:.6f}"),
            ]
        )
        if timeline:
            terminal.blank()
            terminal.heading("timeline")
            for ev in timeline:
                terminal.console.print(
                    f"  [dim]{ev['timestamp']}[/dim]  {ev['event_type']}"
                )
        terminal.blank()
    finally:
        store.close()


@executions_app.command("events")
def list_events(
    limit: int = typer.Option(50, "--limit", help="Maximum events"),
    json_mode: bool = typer.Option(False, "--json", help="Machine-readable JSON"),
):
    """List recent journal events across all executions."""
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
        events = store.list_events(limit=limit)
        if json_mode or terminal.is_json_mode():
            terminal.json_output(events)
            return
        terminal.wordmark()
        terminal.blank()
        terminal.status_block([("store", store_path), ("events", str(len(events)))])
        terminal.blank()
        if not events:
            terminal.muted("no events recorded")
            return
        from rich.table import Table

        table = Table(
            show_header=True, header_style="dim", border_style="#262626", pad_edge=False
        )
        for c in ("seq", "execution", "event", "timestamp"):
            table.add_column(c)
        for ev in events:
            table.add_row(
                str(ev["sequence"]),
                str(ev["execution_id"])[:8],
                ev["event_type"],
                str(ev["timestamp"]),
            )
        terminal.console.print(table)
        terminal.blank()
    finally:
        store.close()


@executions_app.command("import-jsonl")
def import_jsonl(
    source: str = typer.Argument(
        ..., help="Path to the legacy .voodoo/executions.jsonl file"
    ),
    json_mode: bool = typer.Option(False, "--json", help="Machine-readable JSON"),
):
    """Migrate legacy JSONL execution records into the SQLite store."""
    from voodoo.runtime.persistence import JSONFileExecutionStore

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
        legacy = JSONFileExecutionStore(source)
        imported = 0
        for ex in legacy.load_latest().values():
            store.save(ex)
            imported += 1
        if json_mode or terminal.is_json_mode():
            terminal.json_output(
                {"store": store_path, "source": source, "imported": imported}
            )
            return
        terminal.wordmark()
        terminal.blank()
        terminal.status_block(
            [("store", store_path), ("source", source), ("imported", str(imported))]
        )
        terminal.blank()
    finally:
        store.close()
