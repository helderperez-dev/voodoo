"""voodoo inspect — inspect runtime state: runs, agents, tools, workflows, state, capabilities, mesh.

Subcommands
-----------
run <id>       Show an execution (or list recent executions).
agent          Recent agent runs.
tool           Recent tool calls.
task           Recent task-shaped executions (actor-driven).
workflow       Workflow executions by trace.
state          Entities and their history.
capabilities   Registered capabilities and tool permission requirements.
mesh           Mesh surface: exposed functions, event handlers, active nodes.

Two modes:
* default — inspect an app in-process (imports ``app_str``, e.g. ``main:app``),
  reading the runtime engine + telemetry store + mesh network.
* ``--url`` — fetch metrics from a live server (``GET {url}/voodoo/metrics``).
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from typing import Any
from urllib.request import urlopen

import typer
from rich.table import Table

from voodoo.cli import terminal

inspect_app = typer.Typer(help="inspect runtime state", no_args_is_help=True)


def _fetch_live(url: str) -> dict[str, Any]:
    """Fetch metrics summary from a live server."""
    endpoint = url.rstrip("/") + "/voodoo/metrics"
    with urlopen(endpoint, timeout=5) as resp:  # noqa: S310 — user-supplied URL
        return json.loads(resp.read().decode())


def _load_app(app_str: str | None) -> Any:
    """Import the app in-process so runtime/telemetry/mesh state is readable."""
    if app_str is None:
        app_str = "main:app" if os.path.exists("main.py") else "voodoo.core:app"
    module_name, _, attr = app_str.partition(":")
    attr = attr or "app"
    sys.path.insert(0, os.getcwd())
    mod = importlib.import_module(module_name)
    return getattr(mod, attr, None)


def _is_json(json_mode: bool) -> bool:
    """JSON mode: explicit flag or global --json in argv."""
    return bool(json_mode) or terminal.is_json_mode()


def _table(columns: list[str]) -> Table:
    table = Table(
        show_header=True, header_style="dim", border_style="#262626", pad_edge=False
    )
    for c in columns:
        table.add_column(c)
    return table


def _emit(data: Any, json_mode: bool = False) -> None:
    if _is_json(json_mode):
        if data is not None:
            terminal.json_output(data)
    else:
        terminal.wordmark()
        terminal.blank()


@inspect_app.command("run")
def inspect_run(
    execution_id: str = typer.Argument(
        None, help="Execution id (lists recent if omitted)"
    ),
    app_str: str = typer.Option(None, "--app", help="App instance (e.g. main:app)"),
    json_mode: bool = typer.Option(
        False, "--json", help="Output machine-readable JSON"
    ),
):
    """Show an execution — status, intent, capabilities, effects, cost."""
    from voodoo.runtime import engine

    if execution_id is None:
        executions = engine.recent(20)
        _emit(None, json_mode)
        if not executions and not terminal.is_json_mode():
            terminal.muted("no executions recorded in this process")
        table = _table(["id", "intent", "status", "cost", "effects", "duration"])
        for ex in executions:
            table.add_row(
                ex.id[:8],
                ex.intent.name if ex.intent else "-",
                ex.status.value,
                f"{ex.cost:.4f}",
                str(len(ex.effects)),
                f"{ex.duration_seconds:.3f}s" if ex.duration_seconds else "-",
            )
        if _is_json(json_mode):
            terminal.json_output([e.describe() for e in executions])
        else:
            terminal.console.print(table)
            terminal.blank()
        return

    ex = engine.get(execution_id)
    _emit(None, json_mode)
    if ex is None:
        terminal.error(f"execution '{execution_id}' not found")
        raise typer.Exit(1)
    if _is_json(json_mode):
        terminal.json_output(ex.describe())
        return
    d = ex.describe()
    terminal.status_block(
        [
            ("id", d["id"]),
            ("trace", d["trace_id"]),
            ("status", d["status"]),
            ("intent", d["intent"] or "-"),
            ("actor", d["actor"]),
            ("cost", f"{d['cost']:.6f}"),
            (
                "duration",
                f"{d['duration_seconds']:.3f}s" if d["duration_seconds"] else "-",
            ),
        ]
    )
    if d["capabilities"]:
        terminal.label_value("capabilities", ", ".join(d["capabilities"]))
    if d["effects"]:
        terminal.label_value("effects", ", ".join(d["effects"]))
    if d["error"]:
        terminal.error(d["error"])
    terminal.blank()


@inspect_app.command("agent")
def inspect_agent(
    app_str: str = typer.Option(None, "--app"),
    json_mode: bool = typer.Option(
        False, "--json", help="Output machine-readable JSON"
    ),
    url: str = typer.Option(
        None, "--url", help="Live server URL (e.g. http://localhost:8000)"
    ),
    limit: int = typer.Option(10, "--limit"),
):
    """Recent agent runs: model, tokens, cost, tool calls, status."""
    if url:
        summary = _fetch_live(url)
        runs = summary.get("recent_agent_runs", [])[:limit]
        _emit(None, json_mode)
        if _is_json(json_mode):
            terminal.json_output(runs)
            return
        table = _table(["run", "model", "status", "tokens", "cost", "tools"])
        for r in runs:
            table.add_row(
                str(r.get("run_id", ""))[:8],
                r.get("model", "-"),
                r.get("status", "-"),
                str((r.get("tokens_in", 0) or 0) + (r.get("tokens_out", 0) or 0)),
                f"{r.get('cost', 0) or 0:.6f}",
                str(len(r.get("tool_calls", []) or [])),
            )
        terminal.console.print(table)
        terminal.blank()
        return

    _load_app(app_str)  # import side effects populate telemetry
    from voodoo.telemetry import telemetry_store

    runs = telemetry_store.metrics["agent_runs"][-limit:]
    _emit(None, json_mode)
    if _is_json(json_mode):
        terminal.json_output(runs)
        return
    if not runs:
        terminal.muted("no agent runs recorded in this process")
    table = _table(["run", "model", "status", "tokens", "cost", "tools"])
    for r in runs:
        table.add_row(
            str(r.get("run_id", ""))[:8],
            r.get("model", "-"),
            r.get("status", "-"),
            str((r.get("tokens_in", 0) or 0) + (r.get("tokens_out", 0) or 0)),
            f"{r.get('cost', 0) or 0:.6f}",
            str(len(r.get("tool_calls", []) or [])),
        )
    terminal.console.print(table)
    terminal.blank()


@inspect_app.command("plan")
def inspect_plan(
    intent_name: str = typer.Argument(
        ..., help="Intent name to plan (e.g. 'notify.customer')"
    ),
    requires: str = typer.Option(
        None, "--requires", help="Comma-separated required capabilities"
    ),
    app_str: str = typer.Option(None, "--app", help="App instance (e.g. main:app)"),
    json_mode: bool = typer.Option(
        False, "--json", help="Output machine-readable JSON"
    ),
):
    """Plan an intent — show the planner's strategy + participant assignment."""
    from voodoo.primitives.intent import Intent
    from voodoo.runtime.planner import Planner

    _load_app(app_str)

    intent = Intent(name=intent_name)
    if requires:
        for cap in requires.split(","):
            cap = cap.strip()
            if cap:
                intent.require(cap)

    planner = Planner()
    plan = planner.plan(intent)
    data = plan.describe()

    _emit(None, json_mode)
    if _is_json(json_mode):
        terminal.json_output(data)
        return

    terminal.status_block(
        [
            ("intent", data["intent"]),
            ("strategy", data["strategy"]),
            ("steps", str(len(data["steps"]))),
            ("unresolved", str(len(data["unresolved"]))),
        ]
    )
    if data["decisions"]:
        terminal.blank()
        for d in data["decisions"]:
            terminal.console.print(f"  [dim]{d}[/dim]")
    if data["unresolved"]:
        terminal.blank()
        terminal.muted(f"unresolved capabilities: {', '.join(data['unresolved'])}")
    terminal.blank()


@inspect_app.command("tool")
def inspect_tool(
    app_str: str = typer.Option(None, "--app"),
    json_mode: bool = typer.Option(
        False, "--json", help="Output machine-readable JSON"
    ),
    limit: int = typer.Option(15, "--limit"),
):
    """Recent tool calls: name, latency, error."""
    _load_app(app_str)
    from voodoo.telemetry import telemetry_store

    calls = telemetry_store.metrics["tool_calls"][-limit:]
    _emit(None, json_mode)
    if _is_json(json_mode):
        terminal.json_output(calls)
        return
    if not calls:
        terminal.muted("no tool calls recorded in this process")
    table = _table(["tool", "latency", "status", "trace"])
    for c in calls:
        table.add_row(
            c.get("tool", "-"),
            f"{c.get('latency_ms', 0):.1f}ms",
            "failed" if c.get("error") else "ok",
            (c.get("trace_id") or "")[:8],
        )
    terminal.console.print(table)
    terminal.blank()


@inspect_app.command("task")
def inspect_task(
    app_str: str = typer.Option(None, "--app"),
    json_mode: bool = typer.Option(
        False, "--json", help="Output machine-readable JSON"
    ),
    limit: int = typer.Option(20, "--limit"),
):
    """Executions whose actor is task/agent-driven (Task units)."""
    from voodoo.runtime import engine

    _load_app(app_str)
    task_execs = [e for e in engine.recent(100) if e.actor not in ("system",)][:limit]
    _emit(None, json_mode)
    if _is_json(json_mode):
        terminal.json_output([e.describe() for e in task_execs])
        return
    if not task_execs:
        terminal.muted("no task executions recorded in this process")
    table = _table(["id", "intent", "actor", "status", "cost"])
    for ex in task_execs:
        table.add_row(
            ex.id[:8],
            ex.intent.name if ex.intent else "-",
            ex.actor,
            ex.status.value,
            f"{ex.cost:.4f}",
        )
    terminal.console.print(table)
    terminal.blank()


@inspect_app.command("workflow")
def inspect_workflow(
    trace_id: str = typer.Argument(None, help="Trace id (groups task executions)"),
    app_str: str = typer.Option(None, "--app"),
    json_mode: bool = typer.Option(
        False, "--json", help="Output machine-readable JSON"
    ),
):
    """Executions grouped by trace — the observable workflow structure."""
    from voodoo.runtime import ExecutionGraph, engine

    _load_app(app_str)
    executions = engine.recent(200)
    if trace_id:
        executions = [e for e in executions if e.trace_id == trace_id]
    graph = ExecutionGraph.from_executions(executions)
    described = graph.describe()
    _emit(None, json_mode)
    if _is_json(json_mode):
        terminal.json_output(described)
        return
    if not described:
        terminal.muted("no executions recorded in this process")
    for root in described:
        terminal.heading(f"trace {root['trace_id'][:8]} · {root.get('intent') or '-'}")
        terminal.tree(
            [
                f"{root['intent'] or root['id'][:8]} [{root['status']}]",
                *[
                    f"  {c.get('intent') or c['id'][:8]} [{c['status']}] (actor: {c.get('actor')})"
                    for c in root.get("children", [])
                ],
            ]
        )
        terminal.blank()


@inspect_app.command("state")
def inspect_state(
    entity: str = typer.Argument(None, help="Entity kind (e.g. lead, order)"),
    app_str: str = typer.Option(None, "--app"),
    json_mode: bool = typer.Option(
        False, "--json", help="Output machine-readable JSON"
    ),
):
    """Observable state changes recorded on executions."""
    from voodoo.runtime import engine

    _load_app(app_str)
    changes = []
    for ex in engine.recent(200):
        for st in ex.state_changes:
            changes.append(
                {
                    "execution_id": ex.id,
                    "trace_id": ex.trace_id,
                    "kind": getattr(st, "kind", None),
                    "entity_id": getattr(st, "entity_id", None),
                    "data": getattr(st, "data", None),
                }
            )
    if entity is not None:
        changes = [c for c in changes if c["kind"] == entity]
    _emit(None, json_mode)
    if _is_json(json_mode):
        terminal.json_output(changes)
        return
    if not changes:
        terminal.muted("no state changes recorded in this process")
    table = _table(["kind", "entity", "execution", "trace"])
    for c in changes[:50]:
        table.add_row(
            c["kind"] or "-",
            str(c["entity_id"] or "-")[:8],
            c["execution_id"][:8],
            c["trace_id"][:8],
        )
    terminal.console.print(table)
    terminal.blank()


@inspect_app.command("capabilities")
def inspect_capabilities(
    app_str: str = typer.Option(None, "--app"),
    json_mode: bool = typer.Option(
        False, "--json", help="Output machine-readable JSON"
    ),
):
    """Registered capability templates and tool permission requirements."""
    from voodoo.runtime import engine

    _load_app(app_str)
    cap_data = engine.capabilities.describe()
    # tool permission requirements
    try:
        from voodoo.ai.tools.registry import default_registry

        tool_perms = {
            spec.name: spec.permissions
            for spec in default_registry.list_tools()
            if getattr(spec, "permissions", None)
        }
    except Exception:  # noqa: BLE001
        tool_perms = {}
    _emit(None, json_mode)
    if _is_json(json_mode):
        terminal.json_output({"capabilities": cap_data, "tool_permissions": tool_perms})
        return
    terminal.status_block(
        [
            ("capabilities", str(len(cap_data["capabilities"]))),
            ("approval req.", str(len(cap_data["approval_required"]))),
        ]
    )
    if cap_data["capabilities"]:
        terminal.label_value("names", ", ".join(cap_data["capabilities"]))
    if tool_perms:
        terminal.blank()
        table = _table(["tool", "requires"])
        for name, perms in tool_perms.items():
            table.add_row(name, ", ".join(perms))
        terminal.console.print(table)
    terminal.blank()


@inspect_app.command("mesh")
def inspect_mesh(
    app_str: str = typer.Option(None, "--app"),
    json_mode: bool = typer.Option(
        False, "--json", help="Output machine-readable JSON"
    ),
):
    """Mesh surface: exposed functions, event handlers, active nodes."""
    from voodoo.mesh import mesh

    _load_app(app_str)
    data = {
        "exposed": sorted(mesh.exposed_functions.keys()),
        "handlers": {e: len(h) for e, h in sorted(mesh.event_handlers.items())},
        "active_nodes": len(mesh.active_nodes),
    }
    _emit(None, json_mode)
    if _is_json(json_mode):
        terminal.json_output(data)
        return
    terminal.status_block(
        [
            ("exposed", str(len(data["exposed"]))),
            ("event types", str(len(data["handlers"]))),
            ("active nodes", str(data["active_nodes"])),
        ]
    )
    if data["handlers"]:
        terminal.blank()
        table = _table(["event", "handlers"])
        for event, count in data["handlers"].items():
            table.add_row(event, str(count))
        terminal.console.print(table)
    terminal.blank()


@inspect_app.command("approvals")
def inspect_approvals(
    pending_only: bool = typer.Option(
        False, "--pending", help="Only show pending approvals"
    ),
    app_str: str = typer.Option(None, "--app"),
    json_mode: bool = typer.Option(
        False, "--json", help="Output machine-readable JSON"
    ),
):
    """Human approvals — pending and decided, with capability + requester."""
    from voodoo.runtime import engine

    _load_app(app_str)
    approvals = list(engine.approvals.records.values())
    if pending_only:
        approvals = [a for a in approvals if a.status.value == "pending"]
    data = [a.describe() for a in approvals]
    _emit(None, json_mode)
    if _is_json(json_mode):
        terminal.json_output(data)
        return
    if not data:
        terminal.muted("no approvals recorded in this process")
    table = _table(["id", "capability", "question", "status", "by"])
    for a in data:
        table.add_row(
            a["execution_id"][:8],
            a["capability"] or "-",
            (a["question"] or "-")[:48],
            a["status"],
            a["decided_by"] or "-",
        )
    terminal.console.print(table)
    terminal.blank()
