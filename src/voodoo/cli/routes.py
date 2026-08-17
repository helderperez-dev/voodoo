import os
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from voodoo.cli import terminal


def routes(
    app_str: str = typer.Argument(
        None, help="App instance to inspect (e.g. main:app). Auto-discovers if omitted."
    ),
):
    """
    List all registered HTTP, WebSocket, and API routes in the application.
    """
    import importlib

    # Auto-discover app: prefer main:app for backward compat
    if app_str is None:
        if Path("main.py").exists():
            app_str = "main:app"
        else:
            app_str = "voodoo.core:app"

    module_name, app_name = app_str.split(":") if ":" in app_str else ("main", "app")
    sys.path.insert(0, os.getcwd())
    try:
        mod = importlib.import_module(module_name)
        application = getattr(mod, app_name)
    except Exception as e:
        terminal.error(f"Could not load application '{app_str}': {e}")
        raise typer.Exit(1) from None

    terminal.wordmark()
    terminal.blank()
    terminal.muted(f"routes for {app_str}")
    terminal.blank()

    console = Console()
    table = Table(
        show_header=True, header_style="dim", border_style="#262626", pad_edge=False
    )
    table.add_column("type", style="dim", no_wrap=True)
    table.add_column("path", style="white")
    table.add_column("methods", style="green")
    table.add_column("name", style="dim")

    for route in getattr(application, "routes", []):
        r_type = type(route).__name__
        r_path = getattr(route, "path", getattr(route, "path_format", str(route)))
        r_methods = (
            ", ".join(sorted(getattr(route, "methods", [])))
            if hasattr(route, "methods") and route.methods
            else "WS/ALL"
        )
        r_name = getattr(route, "name", "") or getattr(
            getattr(route, "endpoint", None), "__name__", ""
        )
        table.add_row(r_type, r_path, r_methods, r_name)

    console.print(table)
    terminal.blank()
