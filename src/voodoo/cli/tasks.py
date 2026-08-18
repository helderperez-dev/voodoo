"""voodoo tasks — inspect and manage durable background tasks."""

from __future__ import annotations

import typer

from voodoo.cli import terminal

tasks_app = typer.Typer(
    name="tasks",
    help="Inspect and manage durable background tasks.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _get_queue():
    from voodoo.workers.queue import _get_queue

    return _get_queue()


@tasks_app.command("list")
def list_tasks(
    status: str = typer.Option(None, "--status", help="Filter by status"),
    task_type: str = typer.Option(None, "--type", help="Filter by task type"),
    json_mode: bool = typer.Option(False, "--json", help="Machine-readable JSON"),
):
    """List recent tasks."""
    import asyncio

    from voodoo.storage.queue import TaskStatus

    async def run():
        q = await _get_queue()
        stat = TaskStatus(status) if status else None
        tasks = await q.list(status=stat, task_type=task_type)
        stats = await q.stats()
        if json_mode or terminal.is_json_mode():
            terminal.json_output(
                {"stats": stats.describe(), "tasks": [t.describe() for t in tasks]}
            )
            return
        terminal.wordmark()
        terminal.blank()
        terminal.status_block(
            [
                ("provider", q.capabilities().provider),
                ("total", str(stats.total)),
                ("pending", str(stats.pending)),
                ("running", str(stats.running)),
                ("retrying", str(stats.retrying)),
                ("completed", str(stats.completed)),
                ("failed", str(stats.failed)),
            ]
        )
        terminal.blank()
        if not tasks:
            terminal.muted("no tasks found")
            return
        from rich.table import Table

        table = Table(
            show_header=True, header_style="dim", border_style="#262626", pad_edge=False
        )
        for c in ("id", "type", "status", "priority", "attempts", "created_at"):
            table.add_column(c)
        for t in tasks:
            table.add_row(
                str(t.id),
                t.type,
                t.status.value,
                str(t.priority),
                f"{t.attempts}/{t.max_attempts}",
                t.created_at.strftime("%H:%M:%S") if t.created_at else "-",
            )
        terminal.console.print(table)
        terminal.blank()

    asyncio.run(run())


@tasks_app.command("retry")
def retry_task(
    task_id: int = typer.Argument(..., help="Task ID to retry"),
    json_mode: bool = typer.Option(False, "--json", help="Machine-readable JSON"),
):
    """Manually retry a failed task."""
    import asyncio

    async def run():
        q = await _get_queue()
        result = await q.retry(task_id)
        if result is None:
            if json_mode or terminal.is_json_mode():
                terminal.json_output(
                    {"error": f"task {task_id} not found or not failed"}
                )
                return
            terminal.wordmark()
            terminal.blank()
            terminal.muted(f"task {task_id} not found or not failed")
            return
        if json_mode or terminal.is_json_mode():
            terminal.json_output(result.describe())
            return
        terminal.wordmark()
        terminal.blank()
        terminal.status_block(
            [("task", str(result.id)), ("status", result.status.value)]
        )
        terminal.blank()

    asyncio.run(run())
