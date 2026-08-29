"""voodoo approvals — decide pending human approvals from any machine.

Sprint 18: human approval is an execution state that survives process
death. This CLI reads and decides approvals directly from the durable
execution store (SQLite by default), so a decision can be made on any
machine — the waiting execution resumes on whichever worker picks it up.

    voodoo approvals list [--pending] [--json]
    voodoo approvals show <execution-id> [--json]
    voodoo approvals approve <execution-id> [--by NAME] [--note TEXT]
    voodoo approvals deny <execution-id> [--by NAME] [--reason TEXT]

With ``--app`` (e.g. ``main:app``) the application module is imported
first so registered participants (agents, workflows) re-register and the
approved execution actually re-runs.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import typer

from voodoo.cli import terminal

approvals_app = typer.Typer(
    name="approvals",
    help="List, approve, and deny human approvals.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


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


def _load_app(app_str: str | None) -> None:
    """Import the application module so participants re-register."""
    if app_str is None:
        return
    import importlib
    import sys

    module_name, _, attr = app_str.partition(":")
    attr = attr or "app"
    sys.path.insert(0, os.getcwd())
    mod = importlib.import_module(module_name)
    getattr(mod, attr, None)


def _list_approvals(store, pending_only: bool) -> list[dict]:
    """Read approvals from a store, tolerating stores without the seam."""
    if not hasattr(store, "load_approvals"):
        return []
    return store.load_approvals(pending_only=pending_only)


@approvals_app.command("list")
def list_approvals(
    pending_only: bool = typer.Option(
        False, "--pending", help="Only show pending approvals"
    ),
    store_path: str = typer.Option(
        None, "--store", help="Path to the execution store (SQLite by default)"
    ),
    app_str: str = typer.Option(
        None, "--app", help="App instance (e.g. main:app) to import first"
    ),
    json_mode: bool = typer.Option(
        False, "--json", help="Machine-readable JSON output"
    ),
):
    """List approvals — pending and decided."""
    store, resolved = _resolve_store(store_path)
    _load_app(app_str)
    approvals = _list_approvals(store, pending_only)

    if json_mode or terminal.is_json_mode():
        terminal.json_output({"store": resolved, "approvals": approvals})
        return

    terminal.wordmark()
    terminal.blank()
    if not approvals:
        terminal.muted(
            f"no {'pending ' if pending_only else ''}approvals in {resolved}"
        )
        return
    for a in approvals:
        terminal.info(
            f"  {str(a.get('id', ''))[:8]}  {(a.get('question') or '-')[:60]}"
        )
        terminal.muted(
            f"    execution: {str(a.get('execution_id', ''))[:8]}"
            f"  status: {a.get('status', '-')}"
        )
        terminal.muted(
            f"    requested_by: {a.get('requested_by') or '-'}"
            f"  decided_by: {a.get('decided_by') or '-'}"
        )
        terminal.blank()


@approvals_app.command("show")
def show_approval(
    execution_id: str = typer.Argument(..., help="Execution id of the approval"),
    store_path: str = typer.Option(
        None, "--store", help="Path to the execution store (SQLite by default)"
    ),
    json_mode: bool = typer.Option(
        False, "--json", help="Machine-readable JSON output"
    ),
):
    """Show one approval in detail."""
    store, resolved = _resolve_store(store_path)
    approval = (
        store.load_approval(execution_id) if hasattr(store, "load_approval") else None
    )
    if approval is None:
        terminal.error(
            f"approval for execution '{execution_id}' not found in {resolved}"
        )
        raise typer.Exit(1)

    if json_mode or terminal.is_json_mode():
        terminal.json_output(approval)
        return

    terminal.wordmark()
    terminal.blank()
    terminal.status_block(
        [
            ("id", str(approval.get("id", ""))),
            ("execution", str(approval.get("execution_id", ""))),
            ("trace", str(approval.get("trace_id", "") or "-")),
            ("status", approval.get("status", "-")),
            ("requested_by", approval.get("requested_by") or "-"),
            ("decided_by", approval.get("decided_by") or "-"),
            ("decided_at", approval.get("decided_at") or "-"),
            ("participant", approval.get("participant") or "-"),
        ]
    )
    question = approval.get("question")
    if question:
        terminal.blank()
        terminal.label_value("question", question)
    reason = approval.get("reason")
    if reason:
        terminal.label_value("reason", reason)
    terminal.blank()


def _decide(
    execution_id: str,
    *,
    decision: str,
    by: str,
    message: str | None,
    store_path: str | None,
    app_str: str | None,
    json_mode: bool,
) -> None:
    """Shared approve/deny path: recover waiting executions, then decide."""
    from voodoo.runtime.engine import engine as runtime_engine

    store, resolved = _resolve_store(store_path)
    runtime_engine.use_store(store)
    # Restore waiting executions + rehydrate persisted approvals so the
    # decision applies to the durable record — not just this process.
    runtime_engine.recover()
    _load_app(app_str)

    if runtime_engine.approvals.get(execution_id) is None:
        if json_mode or terminal.is_json_mode():
            terminal.json_output(
                {
                    "error": "approval not found",
                    "execution_id": execution_id,
                    "store": resolved,
                }
            )
        else:
            terminal.error(f"approval for execution '{execution_id}' not found")
        raise typer.Exit(1)

    decide_fn = runtime_engine.approve if decision == "approve" else runtime_engine.deny
    kwargs = {}
    if decision == "approve":
        kwargs["note"] = message
    else:
        kwargs["reason"] = message or "denied"
    executed = asyncio.run(decide_fn(execution_id, by=by, **kwargs))

    if json_mode or terminal.is_json_mode():
        terminal.json_output(
            {
                "store": resolved,
                "decision": decision,
                "execution_id": execution_id,
                "by": by,
                "resumed": executed.describe() if executed is not None else None,
            }
        )
        return

    terminal.wordmark()
    terminal.blank()
    icon = "✓" if decision == "approve" else "✗"
    terminal.info(f"  {icon} {decision}d execution {execution_id[:8]} by {by}")
    if executed is not None:
        terminal.muted(f"    execution → {executed.status.value}")
    else:
        terminal.muted("    execution not found in engine (record updated only)")
    terminal.blank()


@approvals_app.command("approve")
def approve_cmd(
    execution_id: str = typer.Argument(..., help="Execution id to approve"),
    by: str = typer.Option("human", "--by", help="Who is approving"),
    note: str = typer.Option(None, "--note", help="Optional note"),
    store_path: str = typer.Option(
        None, "--store", help="Path to the execution store (SQLite by default)"
    ),
    app_str: str = typer.Option(
        None, "--app", help="App instance (e.g. main:app) to import first"
    ),
    json_mode: bool = typer.Option(
        False, "--json", help="Machine-readable JSON output"
    ),
):
    """Approve a waiting execution — it resumes on a worker."""
    _decide(
        execution_id,
        decision="approve",
        by=by,
        message=note,
        store_path=store_path,
        app_str=app_str,
        json_mode=json_mode,
    )


@approvals_app.command("deny")
def deny_cmd(
    execution_id: str = typer.Argument(..., help="Execution id to deny"),
    by: str = typer.Option("human", "--by", help="Who is denying"),
    reason: str = typer.Option(None, "--reason", help="Denial reason"),
    store_path: str = typer.Option(
        None, "--store", help="Path to the execution store (SQLite by default)"
    ),
    app_str: str = typer.Option(
        None, "--app", help="App instance (e.g. main:app) to import first"
    ),
    json_mode: bool = typer.Option(
        False, "--json", help="Machine-readable JSON output"
    ),
):
    """Deny a waiting execution — it fails with the denial reason."""
    _decide(
        execution_id,
        decision="deny",
        by=by,
        message=reason,
        store_path=store_path,
        app_str=app_str,
        json_mode=json_mode,
    )
