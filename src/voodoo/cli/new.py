import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from voodoo.cli.scaffolding import _detect_ide, _sync_ai_assets

console = Console()


def new(  # noqa: C901
    project_name: str,
    template: str = typer.Option(
        "helderperez-dev/voodoo-templates",
        "--template",
        "-t",
        help="GitHub repository URL or 'user/repo' to use as a template",
    ),
    variant: str = typer.Option(
        "default",
        "--variant",
        "-v",
        help="Specific template variant inside the repository",
    ),
    ide: str | None = typer.Option(
        None,
        "--ide",
        "-i",
        help="Target AI IDE rules (trae, cursor, windsurf, vscode, all, none)",
    ),
):
    """
    Scaffold a new Voodoo project or clone a community template.
    """
    console.print(
        Panel.fit(
            f"Creating new Voodoo project: [bold cyan]{project_name}[/bold cyan]",
            border_style="cyan",
        )
    )

    project_dir = Path(project_name)
    if project_dir.exists():
        console.print(
            f"[bold red]Error:[/bold red] Directory '{project_name}' already exists."
        )
        raise typer.Exit(1)

    valid_ides = ["trae", "cursor", "windsurf", "vscode", "all", "none"]
    selected_ide = ide.lower() if ide else None

    if selected_ide and selected_ide not in valid_ides:
        console.print(
            f"[bold red]Error:[/bold red] Invalid IDE '{selected_ide}'. Choose from: {', '.join(valid_ides)}"
        )
        raise typer.Exit(1)

    if not selected_ide:
        detected = _detect_ide()
        if sys.stdin.isatty():
            detected_hint = (
                f" [dim](detected: [bold cyan]{detected}[/bold cyan])[/dim]"
                if detected
                else ""
            )
            console.print(
                f"\n[bold]Select AI IDE configuration to generate{detected_hint}:[/bold]"
            )
            console.print("  [cyan]1[/cyan] - Trae (.trae/rules, skills)")
            console.print("  [cyan]2[/cyan] - Cursor (.cursor/rules/voodoo.mdc)")
            console.print("  [cyan]3[/cyan] - Windsurf (.windsurfrules)")
            console.print(
                "  [cyan]4[/cyan] - VS Code / Copilot (.github/copilot-instructions.md)"
            )
            console.print("  [cyan]5[/cyan] - All IDE configurations")
            console.print("  [cyan]6[/cyan] - None (core .voodoo/ai docs only)")

            mapping = {
                "1": "trae",
                "trae": "trae",
                "2": "cursor",
                "cursor": "cursor",
                "3": "windsurf",
                "windsurf": "windsurf",
                "4": "vscode",
                "vscode": "vscode",
                "5": "all",
                "all": "all",
                "6": "none",
                "none": "none",
            }
            default_key = {
                "trae": "1",
                "cursor": "2",
                "windsurf": "3",
                "vscode": "4",
                "all": "5",
                "none": "6",
            }.get(detected or "", "6")
            user_choice = typer.prompt(
                "Select option", default=default_key, show_default=True
            )
            selected_ide = mapping.get(user_choice.strip().lower(), detected or "none")
            console.print("")
        else:
            selected_ide = detected or "none"

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        if template:
            task = progress.add_task(
                description=f"Cloning [cyan]{variant}[/cyan] template from [cyan]{template}[/cyan]...",
                total=None,
            )

            # Resolve URL
            if (
                template.startswith("http://")
                or template.startswith("https://")
                or template.startswith("git@")
                or template.startswith("/")
                or template.startswith("file://")
            ):
                repo_url = template
            elif len(template.split("/")) == 2:
                repo_url = f"https://github.com/{template}.git"
            else:
                console.print(
                    "\n[bold red]Error:[/bold red] Template must be a valid Git URL, local path, or 'user/repo'."
                )
                raise typer.Exit(1)

            fallback_to_offline = False

            try:
                with tempfile.TemporaryDirectory() as tmp_dir:
                    subprocess.run(
                        ["git", "clone", "--depth", "1", repo_url, tmp_dir],
                        check=True,
                        capture_output=True,
                    )

                    variant_path = Path(tmp_dir) / variant

                    if not variant_path.exists() or not variant_path.is_dir():
                        # If variant doesn't exist, check if the repo root itself is the template
                        if (
                            variant == "default"
                            and not (Path(tmp_dir) / "default").exists()
                        ):
                            variant_path = Path(tmp_dir)
                        else:
                            console.print(
                                f"\n[bold red]Error:[/bold red] Variant '{variant}' not found in template repository."
                            )
                            raise typer.Exit(1)

                    # Copy the template files over to the project directory
                    shutil.copytree(variant_path, project_dir, dirs_exist_ok=True)

            except subprocess.CalledProcessError:
                console.print(
                    f"\n[bold yellow]Warning:[/bold yellow] Failed to clone template from {repo_url}"
                )
                console.print(
                    "[yellow]Falling back to offline default scaffolding...[/yellow]"
                )
                fallback_to_offline = True

            if not fallback_to_offline:
                # Remove the .git folder so the user starts with a clean slate
                if (project_dir / ".git").exists():
                    shutil.rmtree(project_dir / ".git", ignore_errors=True)

                if not (project_dir / ".data").exists():
                    os.makedirs(project_dir / ".data", exist_ok=True)

        if not template or fallback_to_offline:
            task = progress.add_task(
                description="Scaffolding offline project structure...", total=None
            )

            time.sleep(0.3)

            # Ensure the root project directory exists first
            os.makedirs(project_dir, exist_ok=True)

            # Create directory structure per S5 spec
            for d in [
                "app/pages",
                "app/pages/users",
                "app/components",
                "app/agents",
                "app/workers",
                "tests",
                ".data",
            ]:
                os.makedirs(project_dir / d, exist_ok=True)

            progress.update(task, description="Writing base configuration...")
            time.sleep(0.3)

            (project_dir / ".env").write_text("VOODOO_DB_PATH=.data/voodoo.db\n")

            (project_dir / "pyproject.toml").write_text(f"""[project]
name = "{project_dir.name}"
version = "0.1.0"
dependencies = [
    "voodoo-framework"
]
""")

            progress.update(task, description="Generating entry point...")
            time.sleep(0.3)

            (project_dir / "main.py").write_text("""import os
import uvicorn
from voodoo.core import create_app
from voodoo.config import config

# Fix for large cookies in WebSockets
os.environ["WEBSOCKETS_MAX_LINE_LENGTH"] = "8388608"

# Voodoo automatically looks for the "app" folder in the current working directory
app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.host,
        port=config.port,
        reload=True,
        ws_max_size=16777216,
        ws_max_queue=32,
        http="h11",
        ws="auto",
        h11_max_incomplete_event_size=5242880
    )
""")

            progress.update(task, description="Generating pages...")
            time.sleep(0.3)

            (project_dir / "app" / "pages" / "index.py").write_text(
                """from voodoo.components import Div, Heading, Text


def page(request):
    return Div(
        Heading("Hello, Voodoo!", level=1),
        Div(Text("Welcome to your new Voodoo app.")),
    )
"""
            )

            (project_dir / "app" / "pages" / "about.py").write_text(
                """from voodoo.components import Div, Heading, Text


def page(request):
    return Div(
        Heading("About", level=1),
        Text("This is the about page."),
    )
"""
            )

            (project_dir / "app" / "pages" / "users" / "[id].py").write_text(
                """from voodoo.components import Div, Heading, Text


def page(request, id: str):
    return Div(
        Heading(f"User {id}", level=1),
        Text(f"Profile page for user {id}."),
    )
"""
            )

            progress.update(task, description="Generating models and workers...")
            time.sleep(0.2)

            (project_dir / "app" / "models.py").write_text(
                '"""Define your data models here."""\n'
                "from voodoo.data import Model\n\n\n"
                "# class Example(Model):\n"
                "#     name: str\n"
                "#     value: int\n"
            )

            (project_dir / "app" / "workers.py").write_text(
                '"""Background workers (registered via @task)."""\n'
                "from voodoo.workers import task\n\n\n"
                "# @task\n"
                "# async def example_worker():\n"
                "#     ...\n"
            )

            (project_dir / "app" / "agents.py").write_text(
                '"""AI agents (registered via Agent)."""\n'
                "from voodoo import Agent\n\n\n"
                '# agent = Agent(model="openai:gpt-4o")\n'
            )

            (project_dir / "app" / "styles.css").write_text(
                "/* Custom styles for your Voodoo app */\n"
            )

            (project_dir / "tests" / "test_app.py").write_text(
                '"""Tests for your Voodoo app."""\n\n'
                "def test_placeholder():\n"
                "    assert True\n"
            )

        _sync_ai_assets(project_dir, progress, ide=selected_ide)

        # Set up local virtual environment and install dependencies
        if (project_dir / "pyproject.toml").exists():
            task = progress.add_task(
                description="Setting up local virtual environment (.venv)...",
                total=None,
            )
            has_uv = shutil.which("uv") is not None
            try:
                if has_uv:
                    subprocess.run(
                        ["uv", "venv"], cwd=project_dir, check=True, capture_output=True
                    )
                    progress.update(
                        task, description="Installing dependencies with uv..."
                    )
                    subprocess.run(
                        ["uv", "pip", "install", "-e", "."],
                        cwd=project_dir,
                        check=True,
                        capture_output=True,
                    )
                else:
                    subprocess.run(
                        [sys.executable, "-m", "venv", ".venv"],
                        cwd=project_dir,
                        check=True,
                        capture_output=True,
                    )
                    progress.update(
                        task, description="Installing dependencies with pip..."
                    )
                    pip_exe = (
                        ".venv/bin/pip"
                        if os.name != "nt"
                        else ".venv\\Scripts\\pip.exe"
                    )
                    subprocess.run(
                        [str(project_dir / pip_exe), "install", "-e", "."],
                        cwd=project_dir,
                        check=True,
                        capture_output=True,
                    )

                # Clean up build artifacts created by pip/uv install -e .
                for item in project_dir.glob("*.egg-info"):
                    if item.is_dir():
                        shutil.rmtree(item)
            except subprocess.CalledProcessError as e:
                console.print(
                    "\n[bold yellow]Warning:[/bold yellow] Failed to set up local environment or install dependencies."
                )
                if e.stderr:
                    console.print(f"[dim]{e.stderr.decode()}[/dim]")

    console.print("[bold green]✓ Project scaffolded successfully![/bold green]")
    console.print(
        f"\nNext steps:\n  [cyan]cd {project_name}[/cyan]\n  [cyan]voodoo dev[/cyan]\n"
    )
