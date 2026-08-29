"""CLI: ``voodoo create <app>`` — scaffold a full local runtime app.

Sprint 22: Local runtime DX.  Evolves ``voodoo new`` to wire up the full
local runtime (durable tasks, scheduler, events, object store, agent runtime)
with a crash/restart demo proving durability.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import typer

from voodoo.cli import terminal

__all__ = ["create"]

# ---------------------------------------------------------------------------
# Template: main.py — full local runtime
# ---------------------------------------------------------------------------

_MAIN_PY = '''"""{name} — a Voodoo autonomous app.

This app demonstrates the full local runtime:
  - Durable tasks (queue + workers) that survive restarts
  - Scheduler for recurring jobs
  - Mesh events for real-time communication
  - Agent runtime with mock provider (no network needed)

Run:  python main.py   or   voodoo dev
"""

from voodoo import (
    Agent,
    App,
    Button,
    Card,
    Container,
    Heading,
    Stack,
    Text,
    event,
    page,
    state,
    tool,
)
from voodoo.workers.queue import enqueue, queue

app = App()

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

counter = state("counter", 0)
log_lines = state("log_lines", [])
agent_result = state("agent_result", "Click to run the agent")


def _log(msg: str) -> None:
    """Append a timestamped line to the on-screen log."""
    from datetime import datetime

    ts = datetime.now().strftime("%H:%M:%S")
    lines = log_lines.get()
    lines.append(f"[{{ts}}] {{msg}}")
    # Keep last 20 lines
    log_lines.set(lines[-20:])


# ---------------------------------------------------------------------------
# Durable task — survives restarts
# ---------------------------------------------------------------------------

@queue("increment")
async def increment_worker(payload: dict) -> None:
    """Durable worker: increments the counter and logs the result."""
    n = counter.get() + 1
    counter.set(n)
    _log(f"increment task done → counter = {{n}}")


# ---------------------------------------------------------------------------
# Agent (mock provider — no network needed)
# ---------------------------------------------------------------------------

@tool
async def get_counter() -> str:
    """Return the current counter value."""
    return str(counter.get())


agent = Agent(
    model="mock:test",
    tools=["get_counter"],
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@page("/")
def home():
    return Container(
        Stack(
            Heading("{name}", level=1),
            Text(
                "A Voodoo autonomous app — durable tasks, scheduler, "
                "events, and agents, all running on zero infrastructure.",
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
            Heading("Runtime", level=2),
            Text(f"Counter: {{counter.get()}}"),
            Text(f"Log entries: {{len(log_lines.get())}}"),
            gap="sm",
        )
    )


def _task_card():
    return Card(
        Stack(
            Heading("Durable Tasks", level=2),
            Text(
                "Enqueue a durable task. It survives restarts — "
                "stop the server, start it again, and watch the counter increment.",
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


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@event
async def enqueue_task(element_id, value):
    """Enqueue a durable increment task."""
    await enqueue("increment", {{"source": "ui"}})
    _log("enqueued increment task")


@event
async def run_agent(element_id, value):
    """Run the agent and display the result."""
    _log("running agent...")
    run = await agent.run("What is the current counter value?")
    agent_result.set(run.output)
    _log(f"agent done: {{run.output}}")


# ---------------------------------------------------------------------------
# Startup — enqueue a demo task on first boot
# ---------------------------------------------------------------------------

@app.on_startup
async def on_startup():
    """On first boot, enqueue a demo task to prove durability."""
    import os

    marker = ".voodoo/state/.booted"
    if not os.path.exists(marker):
        os.makedirs(os.path.dirname(marker), exist_ok=True)
        with open(marker, "w") as f:
            f.write("booted")
        await enqueue("increment", {{"source": "startup"}})
        _log("first boot — enqueued demo task")
    else:
        _log("restart detected — pending tasks will be recovered")


if __name__ == "__main__":
    app.run()
'''

# ---------------------------------------------------------------------------
# Template: voodoo.toml
# ---------------------------------------------------------------------------

_VOODOO_TOML = """[app]
name = "{name}"

# Local-first defaults — zero infrastructure required.
# The runtime uses SQLite, local filesystem, and in-memory queues by default.
# Override with env vars or this config for production:
#   VOODOO_DATABASE_URL=postgresql://...
#   VOODOO_QUEUE_PROVIDER=redis
#   VOODOO_OBJECT_STORE_PROVIDER=s3
"""

# ---------------------------------------------------------------------------
# Template: pyproject.toml
# ---------------------------------------------------------------------------

_PYPROJECT_TOML = """[project]
name = "{name}"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "voodoo-framework",
]
"""


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


def create(
    project_name: str = typer.Argument(..., help="Name of the project to create"),
) -> None:
    """Scaffold a full local runtime app with durable tasks, scheduler, events, and agents.

    The generated app runs on zero infrastructure (SQLite + local filesystem)
    and includes a crash/restart demo proving durability.
    """
    project_dir = Path(project_name)
    if project_dir.exists():
        terminal.error(f"Directory '{project_name}' already exists")
        raise typer.Exit(1)

    terminal.wordmark()
    terminal.blank()
    terminal.status("creating", project_name)
    terminal.blank()

    # Create directory structure
    project_dir.mkdir(parents=True)
    (project_dir / "app").mkdir()
    (project_dir / ".voodoo" / "state").mkdir(parents=True)

    # Write files
    (project_dir / "main.py").write_text(_MAIN_PY.format(name=project_name))
    (project_dir / "voodoo.toml").write_text(_VOODOO_TOML.format(name=project_name))
    (project_dir / "pyproject.toml").write_text(
        _PYPROJECT_TOML.format(name=project_name)
    )

    terminal.label_value("created", f"{project_name}/")
    terminal.tree(
        [
            "main.py          # App entry point — full runtime demo",
            "voodoo.toml      # Runtime configuration",
            "pyproject.toml   # Python project metadata",
            "app/             # Folder-based routes (add page.py files here)",
            ".voodoo/state/   # Local state (SQLite, queue, schedules)",
        ]
    )
    terminal.blank()

    # Install dependencies
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
        # Fallback to plain venv + pip
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
            terminal.muted("run 'cd {project_name} && pip install -e .' manually")

    terminal.blank()
    terminal.success("ready")
    terminal.blank()
    terminal.next_steps(
        [
            f"cd {project_name}",
            "voodoo dev",
            "",
            "Then open http://localhost:8000 and click 'Enqueue increment'.",
            "Stop the server (Ctrl+C), run 'voodoo dev' again — the counter",
            "increments because the task is durable.",
        ]
    )
