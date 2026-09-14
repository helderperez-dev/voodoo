"""CLI: ``voodoo create <app>`` — scaffold the stable default Voodoo app.

The official scaffold intentionally stays small. It demonstrates the public App,
page, and UI contracts while the Runtime opens the default Voodoo Store at
``.voodoo/application.vstore``. Specialized examples belong outside the default
scaffold until their APIs are stable.
"""

from __future__ import annotations

from pathlib import Path

import typer

from voodoo.cli import terminal

__all__ = ["create"]


_MAIN_PY = '''"""{name} — a minimal Store-first Voodoo application."""

from voodoo import App, page
from voodoo.ui import A, Button, Container, Heading, Stack, Text

app = App()


@page("/")
async def home():
    return Container(
        Stack(
            Heading("Hello, Voodoo", level=1),
            Text(
                "One Runtime. One local Store. No external infrastructure required.",
                tone="muted",
            ),
            Button("Get started", variant="primary"),
            A(
                "Voodoo on GitHub",
                href="https://github.com/helderperez-dev/voodoo",
                target="_blank",
            ),
            gap="md",
        )
    )


if __name__ == "__main__":
    app.run()
'''


_VOODOO_TOML = """[app]
name = "{name}"

# Voodoo Store is the default local durable infrastructure.
# The Runtime creates .voodoo/application.vstore automatically.
# No database, queue, cache, or object-server configuration is required.
"""


_PYPROJECT_TOML = """[project]
name = "{name}"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["voodoo-framework"]
"""


def create(
    project_name: str = typer.Argument(..., help="Name of the project to create"),
) -> None:
    """Scaffold the stable Store-first Voodoo application.

    Creation is intentionally side-effect free: it writes the project files but
    does not create environments, access the network, or install dependencies.
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
    (project_dir / ".voodoo").mkdir()

    (project_dir / "main.py").write_text(_MAIN_PY.format(name=project_name))
    (project_dir / "voodoo.toml").write_text(_VOODOO_TOML.format(name=project_name))
    (project_dir / "pyproject.toml").write_text(
        _PYPROJECT_TOML.format(name=project_name)
    )

    terminal.label_value("created", f"{project_name}/")
    terminal.tree(
        [
            "main.py                    # Minimal app entry point",
            "voodoo.toml                # Runtime configuration",
            "pyproject.toml             # Resolves latest Voodoo release",
            ".voodoo/                   # Local Runtime state",
            "  application.vstore       # Created automatically on first run",
        ]
    )
    terminal.blank()
    terminal.success("ready")
    terminal.blank()
    terminal.next_steps(
        [
            f"cd {project_name}",
            "pip install -e .",
            "voodoo dev",
            "",
            "Open http://localhost:8000.",
            "The Runtime creates .voodoo/application.vstore on first start.",
        ]
    )
