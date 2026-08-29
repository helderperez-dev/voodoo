"""``voodoo workers`` — worker state & queue depth.

Shows registered background workers, their queue depth, and whether
the worker loop is running.
"""

from __future__ import annotations

import asyncio
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

__all__ = ["workers"]


async def _gather_worker_info() -> dict[str, Any]:
    """Collect worker and queue state without side-effects."""
    from voodoo.workers.queue import _get_queue, _worker_tasks, _workers

    info: dict[str, Any] = {
        "registered": list(_workers.keys()),
        "running_tasks": len([t for t in _worker_tasks if not t.done()]),
        "queue_depth": 0,
    }

    try:
        q = await _get_queue()
        if hasattr(q, "list"):
            tasks = await q.list()
            info["queue_depth"] = len(tasks)
        elif hasattr(q, "depth"):
            info["queue_depth"] = await q.depth()
    except Exception:
        pass

    return info


def workers() -> None:
    """Show registered workers and queue depth."""
    console = Console()
    info = asyncio.run(_gather_worker_info())

    console.print("[bold cyan]Voodoo Workers[/bold cyan]")
    console.print()

    tbl = Table(show_header=True, header_style="bold")
    tbl.add_column("Worker", style="dim")
    tbl.add_column("Status")

    registered = info["registered"]
    if not registered:
        console.print("[dim]No workers registered.[/dim]")
    else:
        running = info["running_tasks"]
        for name in registered:
            tbl.add_row(name, "running" if running > 0 else "idle")
        console.print(tbl)

    console.print()
    console.print(f"Queue depth: [bold]{info['queue_depth']}[/bold]")
    console.print(f"Running worker tasks: [bold]{info['running_tasks']}[/bold]")


app = typer.Typer(
    name="workers", help="Worker state & queue depth.", no_args_is_help=True
)
app.command()(workers)
