"""voodoo objects — list/get artifacts from the object store."""

from __future__ import annotations

import typer

from voodoo.cli import terminal

objects_app = typer.Typer(
    name="objects",
    help="Inspect object store and artifacts.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@objects_app.command("list")
def list_objects(
    prefix: str = typer.Option("", "--prefix", help="Filter by key prefix"),
    json_mode: bool = typer.Option(False, "--json", help="Machine-readable JSON"),
):
    """List objects in the store."""
    from voodoo.storage.objects import LocalObjectStore

    store = LocalObjectStore()
    try:
        keys = store.list(prefix)
        if json_mode or terminal.is_json_mode():
            terminal.json_output(keys)
            return
        terminal.wordmark()
        terminal.blank()
        terminal.status_block([("store", str(store.root)), ("objects", str(len(keys)))])
        terminal.blank()
        if not keys:
            terminal.muted("no objects found")
            return
        for key in keys:
            terminal.console.print(f"  {key}")
        terminal.blank()
    finally:
        store.close()


@objects_app.command("get")
def get_object(
    key: str = typer.Argument(..., help="Object key"),
    json_mode: bool = typer.Option(False, "--json", help="Machine-readable JSON"),
):
    """Get object metadata (and content size)."""
    from voodoo.storage.objects import LocalObjectStore

    store = LocalObjectStore()
    try:
        try:
            stat = store.stat(key)
        except KeyError:
            if json_mode or terminal.is_json_mode():
                terminal.json_output({"error": f"object {key!r} not found"})
                return
            terminal.wordmark()
            terminal.blank()
            terminal.muted(f"object {key!r} not found")
            return
        if json_mode or terminal.is_json_mode():
            terminal.json_output(stat)
            return
        terminal.wordmark()
        terminal.blank()
        terminal.status_block(
            [
                ("key", stat["key"]),
                ("size", str(stat["size"])),
                ("content_type", stat["content_type"]),
                ("checksum", stat["checksum"]),
                ("created_at", stat["created_at"]),
            ]
        )
        terminal.blank()
    finally:
        store.close()


@objects_app.command("artifacts")
def list_artifacts(
    execution_id: str = typer.Argument(None, help="Execution ID (optional)"),
    json_mode: bool = typer.Option(False, "--json", help="Machine-readable JSON"),
):
    """List artifacts (optionally filtered by execution)."""
    from voodoo.storage.execution import SQLiteExecutionStore

    store = SQLiteExecutionStore(".voodoo/state/data.db")
    try:
        artifacts = store.list_artifacts(execution_id=execution_id, limit=100)
        if json_mode or terminal.is_json_mode():
            terminal.json_output(artifacts)
            return
        terminal.wordmark()
        terminal.blank()
        terminal.status_block([("artifacts", str(len(artifacts)))])
        terminal.blank()
        if not artifacts:
            terminal.muted("no artifacts found")
            return
        from rich.table import Table

        table = Table(
            show_header=True, header_style="dim", border_style="#262626", pad_edge=False
        )
        for c in ("id", "execution", "created_by", "checksum"):
            table.add_column(c)
        for a in artifacts:
            table.add_row(
                a["id"][:8],
                a["execution_id"][:8],
                a["created_by"] or "-",
                (a["checksum"] or "-")[:16],
            )
        terminal.console.print(table)
        terminal.blank()
    finally:
        store.close()
