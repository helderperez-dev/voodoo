"""CLI: ``voodoo create <app>`` — scaffold a Store-first Voodoo app.

The generated project exercises the default Voodoo Runtime + Voodoo Store path
without requiring PostgreSQL, Redis, S3, SQLite, or another infrastructure
service.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import typer

from voodoo.cli import terminal

__all__ = ["create"]


_MAIN_PY = '''"""{name} — a Store-first Voodoo application.

The default runtime persists application data, durable work, events, execution
state, and other Runtime infrastructure in ``.voodoo/application.vstore``.
No external database, queue, or object server is required for local use.

Run: ``python main.py`` or ``voodoo dev``.
"""

from voodoo import (
    Agent,
    App,
    Button,
    Card,
    Container,
    Heading,
    Model,
    Stack,
    Text,
    event,
    page,
    state,
    tool,
)
from voodoo.workers.queue import enqueue, queue

app = App()


class Counter(Model):
    """Persistent application data stored in application.vstore."""

    name: str
    value: int


counter_value = state(0)
log_lines = state([])
agent_result = state("Click to run the agent")


def _log(msg: str) -> None:
    from datetime import datetime

    ts = datetime.now().strftime("%H:%M:%S")
    lines = list(log_lines.get())
    lines.append(f"[{{ts}}] {{msg}}")
    log_lines.set(lines[-20:])


async def _counter() -> Counter:
    row = await Counter.first(name="main")
    if row is None:
        row = await Counter.create(name="main", value=0)
    return row


@queue("increment")
async def increment_worker(payload: dict) -> None:
    """Durable worker backed by the same application.vstore."""
    row = await _counter()
    row.value += 1
    await row.save()
    counter_value.set(row.value)
    _log(f"durable increment complete → counter = {{row.value}}")


@tool
async def get_counter() -> str:
    """Read persistent application state for the local mock agent."""
    row = await _counter()
    return str(row.value)


agent = Agent(model="mock:test", tools=["get_counter"])


@page("/")
async def home():
    row = await _counter()
    counter_value.set(row.value)
    return Container(
        Stack(
            Heading("{name}", level=1),
            Text(
                "Voodoo Runtime + Voodoo Store — zero external infrastructure.",
                tone="muted",
            ),
            _status_card(),
            _task_card(),
            _agent_card(),
            _log_card(),
            gap="lg",
        )
    )


def _status_card():
    return Card(
        Stack(
            Heading("Persistent Runtime", level=2),
            Text(f"Counter: {{counter_value.get()}}"),
            Text("Stored in .voodoo/application.vstore", tone="muted"),
            gap="sm",
        )
    )


def _task_card():
    return Card(
        Stack(
            Heading("Durable Work", level=2),
            Text(
                "Enqueue a task, restart the process, and refresh the page. "
                "The persisted counter is recovered from Voodoo Store.",
                tone="muted",
            ),
            Button(
                "Enqueue increment",
                onclick="vd.event('enqueue_task')",
                variant="primary",
            ),
            gap="sm",
        )
    )


def _agent_card():
    return Card(
        Stack(
            Heading("Agent", level=2),
            Text(f"Result: {{agent_result.get()}}"),
            Button(
                "Run agent",
                onclick="vd.event('run_agent')",
                variant="secondary",
            ),
            gap="sm",
        )
    )


def _log_card():
    return Card(
        Stack(
            Heading("Event Log", level=2),
            *[Text(line, tone="muted") for line in log_lines.get()],
            gap="xs",
        )
    )


@event
async def enqueue_task(element_id, value):
    await enqueue(
        "increment",
        {{"source": "ui"}},
        idempotency_key=None,
    )
    _log("durable increment enqueued")


@event
async def run_agent(element_id, value):
    _log("running local mock agent...")
    run = await agent.run("What is the persistent counter value?")
    agent_result.set(run.output)
    _log(f"agent done: {{run.output}}")


if __name__ == "__main__":
    app.run()
'''


_VOODOO_TOML = """[app]
name = "{name}"

# Store-first defaults — zero external infrastructure required.
# Voodoo uses .voodoo/application.vstore for durable application infrastructure.
# No provider configuration is needed for the default local path.
#
# External infrastructure remains available as an explicit override, for example:
# [database]
# provider = "postgres"
# url = "postgresql://..."
#
# [queue]
# provider = "redis"
# url = "redis://..."
"""


_PYPROJECT_TOML = """[project]
name = "{name}"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "voodoo-framework",
]
"""


def create(
    project_name: str = typer.Argument(..., help="Name of the project to create"),
) -> None:
    """Scaffold a Store-first Voodoo app with durable data, work, and agents.

    The generated app uses Voodoo Store at ``.voodoo/application.vstore`` and
    requires no external database, queue, or object server for local use.
    """
    project_dir = Path(project_name)
    if project_dir.exists():
        terminal.error(f"Directory '{project_name}' already exists")
        raise typer.Exit(1)

    terminal.wordmark()
    terminal.blank()
    terminal.status("creating", project_name)
    terminal.blank()

    project_dir.mkdir(parents=True)
    (project_dir / "app").mkdir()
    (project_dir / ".voodoo").mkdir()

    (project_dir / "main.py").write_text(_MAIN_PY.format(name=project_name))
    (project_dir / "voodoo.toml").write_text(_VOODOO_TOML.format(name=project_name))
    (project_dir / "pyproject.toml").write_text(
        _PYPROJECT_TOML.format(name=project_name)
    )

    terminal.label_value("created", f"{project_name}/")
    terminal.tree(
        [
            "main.py                    # App entry point — Store-first demo",
            "voodoo.toml                # Runtime configuration",
            "pyproject.toml             # Python project metadata",
            "app/                       # Folder-based routes",
            ".voodoo/                   # Voodoo local infrastructure",
            "  application.vstore       # Created automatically on first run",
        ]
    )
    terminal.blank()

    terminal.status("installing", "dependencies")
    terminal.blank()

    local_venv = project_dir / ".venv"
    try:
        subprocess.run(
            [sys.executable, "-m", "uv", "venv", str(local_venv)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                str(local_venv / "bin" / "python"),
                "-m",
                "uv",
                "pip",
                "install",
                "-e",
                ".",
            ],
            cwd=str(project_dir),
            check=True,
            capture_output=True,
        )
        terminal.muted("installed via uv")
    except (subprocess.CalledProcessError, FileNotFoundError):
        try:
            subprocess.run(
                [sys.executable, "-m", "venv", str(local_venv)],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                [
                    str(local_venv / "bin" / "pip"),
                    "install",
                    "-e",
                    ".",
                ],
                cwd=str(project_dir),
                check=True,
                capture_output=True,
            )
            terminal.muted("installed via pip")
        except subprocess.CalledProcessError as exc:
            terminal.warning(f"dependency install failed: {exc}")
            terminal.muted(f"run 'cd {project_name} && pip install -e .' manually")

    terminal.blank()
    terminal.success("ready")
    terminal.blank()
    terminal.next_steps(
        [
            f"cd {project_name}",
            "voodoo dev",
            "",
            "Open http://localhost:8000 and click 'Enqueue increment'.",
            "Restart the server and refresh: the counter is recovered from",
            ".voodoo/application.vstore.",
        ]
    )
