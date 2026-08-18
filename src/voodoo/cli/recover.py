"""voodoo recover — reload unfinished executions from the persistence store.

After a restart, the runtime engine is empty. ``voodoo recover`` attaches
the durable execution store (default: the SQLite ``.voodoo/state/data.db``)
to the engine and reloads unfinished executions — ``created`` / ``planned`` /
``authorized`` / ``running`` / ``waiting`` — so they stay inspectable and
resumable (e.g. pending human approvals survive the restart).

``--store`` overrides the location. A path ending in ``.jsonl`` uses the
legacy :class:`JSONFileExecutionStore` reader; anything else is treated as a
SQLite database file (Sprint 3).
"""

from __future__ import annotations

import os
from pathlib import Path

import typer

from voodoo.cli import terminal


def _resolve_store(store_path: str | None):
    """Return the configured execution store (SQLite by default)."""
    from voodoo.config import config
    from voodoo.runtime.persistence import JSONFileExecutionStore
    from voodoo.storage.execution import SQLiteExecutionStore

    if store_path is None:
        store_path = os.environ.get("VOODOO_EXECUTION_STORE", config.db_path).replace(
            ":memory:", ".voodoo/state/data.db"
        )

    if Path(store_path).suffix == ".jsonl":
        return JSONFileExecutionStore(store_path), store_path
    return SQLiteExecutionStore(store_path), store_path


def recover(
    app_str: str = typer.Option(None, "--app", help="App instance (e.g. main:app)"),
    store_path: str = typer.Option(
        None, "--store", help="Path to the execution store (SQLite by default)"
    ),
    json_mode: bool = typer.Option(
        False, "--json", help="Output machine-readable JSON"
    ),
):
    """Reload unfinished executions from the store into the engine."""
    from voodoo.runtime.engine import engine as runtime_engine

    if app_str is not None:
        # Import the app first: it may attach its own store / register
        # capabilities needed by resumable approvals.
        import importlib
        import sys

        module_name, _, attr = app_str.partition(":")
        attr = attr or "app"
        sys.path.insert(0, os.getcwd())
        mod = importlib.import_module(module_name)
        getattr(mod, attr, None)

    store, store_path = _resolve_store(store_path)
    runtime_engine.use_store(store)
    recovered = runtime_engine.recover()

    data = [ex.describe() for ex in recovered]
    if json_mode or terminal.is_json_mode():
        terminal.json_output({"store": store_path, "recovered": data})
        return

    terminal.wordmark()
    terminal.blank()
    if not recovered:
        terminal.muted(f"no unfinished executions in {store_path}")
        return
    terminal.status_block([("store", store_path), ("recovered", str(len(recovered)))])
    from rich.table import Table

    table = Table(
        show_header=True, header_style="dim", border_style="#262626", pad_edge=False
    )
    for c in ("id", "intent", "status", "actor"):
        table.add_column(c)
    for ex in recovered:
        table.add_row(
            ex.id[:8],
            ex.intent.name if ex.intent else "-",
            ex.status.value,
            ex.actor,
        )
    terminal.console.print(table)
    terminal.blank()
