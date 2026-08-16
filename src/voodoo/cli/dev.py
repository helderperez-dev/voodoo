from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

console = Console()


def dev(
    app_str: str = typer.Argument(
        "main:app", help="App instance to run (e.g., main:app)"
    ),
    port: int = typer.Option(8000, help="Port to run the server on"),
):
    """
    Start the Voodoo development server.
    """
    module_name = app_str.split(":")[0]
    module_path = Path(module_name.replace(".", "/") + ".py")
    module_dir = Path(module_name.replace(".", "/"))

    if not module_path.exists() and not (
        module_dir.is_dir() and (module_dir / "__init__.py").exists()
    ):
        console.print(
            f"\n[bold red]Error:[/bold red] Could not find module [yellow]{module_name}[/yellow]."
        )
        console.print("Are you sure you are inside a Voodoo project directory?")
        console.print(
            "To start a new project, run: [bold cyan]voodoo new <project_name>[/bold cyan]\n"
        )
        raise typer.Exit(1)

    console.print(
        Panel.fit(
            f"Starting Voodoo Server on port [bold yellow]{port}[/bold yellow]",
            border_style="yellow",
        )
    )

    # Print Voodoo dev banner with version and URLs
    import voodoo

    ver = getattr(voodoo, "__version__", "unknown")
    from voodoo.config import config as _cfg

    host = _cfg.host
    display_host = "localhost" if host in ("0.0.0.0", "::", "") else host
    local_url = f"http://{display_host}:{port}"
    console.print(f"\n  [bold magenta]🔮 Voodoo v{ver}[/bold magenta]")
    console.print(f"  ➜  Local:   [cyan]{local_url}[/cyan]")
    console.print(f"  ➜  Docs:    [cyan]{local_url}/docs[/cyan]")
    console.print("")

    # We use a subprocess to run uvicorn through the current python executable
    # to ensure we don't accidentally pick up a global system uvicorn that lacks the voodoo package
    import os
    import subprocess
    import sys

    local_venv_python = (
        Path(".venv/bin/python")
        if os.name != "nt"
        else Path(".venv/Scripts/python.exe")
    )

    if local_venv_python.exists():
        python_exe = str(local_venv_python.absolute())
        console.print("[dim]Using local virtual environment.[/dim]")
    else:
        python_exe = sys.executable
        console.print("[dim]Using global environment.[/dim]")

    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(sys.path)
    env["WEBSOCKETS_MAX_LINE_LENGTH"] = "8388608"  # 8 MB to match uvicorn's h11 setting
    env["WEBSOCKETS_MAX_NUM_HEADERS"] = "256"

    try:
        # We let uvicorn take over the terminal output
        subprocess.run(
            [
                python_exe,
                "-m",
                "uvicorn",
                app_str,
                "--reload",
                "--port",
                str(port),
                "--http",
                "h11",
                "--ws",
                "auto",
                "--h11-max-incomplete-event-size",
                "5242880",
            ],
            env=env,
        )
    except KeyboardInterrupt:
        console.print("\n[bold red]Server stopped.[/bold red]")
