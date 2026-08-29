"""``voodoo status`` — runtime health overview.

Displays a quick snapshot of the runtime: request counts, error rate,
latency, agent activity, queue depth, and OTel export status.
Works after a restart because rolling counters are persisted to
``.voodoo/telemetry_summary.json``.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

__all__ = ["status"]


def status() -> None:
    """Show runtime health overview."""
    from voodoo.telemetry import telemetry_store
    from voodoo.telemetry.otlp import is_available as otlp_available

    summary = telemetry_store.get_summary()
    console = Console()

    # -- header --------------------------------------------------------
    console.print("[bold cyan]Voodoo Runtime Status[/bold cyan]")
    console.print()

    # -- requests & errors ---------------------------------------------
    tbl = Table(show_header=True, header_style="bold")
    tbl.add_column("Metric", style="dim")
    tbl.add_column("Value", justify="right")

    total = summary.get("requests_total", 0)
    errors = summary.get("errors_total", 0)
    error_rate = f"{(errors / total * 100):.1f}%" if total else "—"
    avg_lat = summary.get("average_latency_ms", 0.0)

    tbl.add_row("Requests total", str(total))
    tbl.add_row("Errors total", str(errors))
    tbl.add_row("Error rate", error_rate)
    tbl.add_row("Avg latency", f"{avg_lat:.1f} ms")
    tbl.add_row("DB queries", str(summary.get("db_queries", 0)))
    console.print(tbl)
    console.print()

    # -- agent activity ------------------------------------------------
    agent_tbl = Table(show_header=True, header_style="bold")
    agent_tbl.add_column("Agent Metric", style="dim")
    agent_tbl.add_column("Value", justify="right")

    agent_tbl.add_row("Agent runs", str(summary.get("agent_runs", 0)))
    agent_tbl.add_row("Tokens in", str(summary.get("agent_tokens_in", 0)))
    agent_tbl.add_row("Tokens out", str(summary.get("agent_tokens_out", 0)))
    agent_tbl.add_row("Agent cost", f"${summary.get('agent_cost', 0.0):.6f}")
    agent_tbl.add_row("Tool calls", str(summary.get("tool_calls_total", 0)))
    agent_tbl.add_row("Tool errors", str(summary.get("tool_errors", 0)))
    agent_tbl.add_row("Spans recorded", str(summary.get("spans_total", 0)))
    console.print(agent_tbl)
    console.print()

    # -- infrastructure ------------------------------------------------
    infra_tbl = Table(show_header=True, header_style="bold")
    infra_tbl.add_column("Infrastructure", style="dim")
    infra_tbl.add_column("Status")

    infra_tbl.add_row("OTLP export", "active" if otlp_available() else "off")
    console.print(infra_tbl)


app = typer.Typer(name="status", help="Runtime health overview.", no_args_is_help=True)
app.command()(status)
