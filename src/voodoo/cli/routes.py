import os
import sys

import typer
from rich.console import Console

console = Console()


def routes(
    app_str: str = typer.Argument(
        "main:app", help="App instance to inspect (e.g. main:app)"
    ),
):
    """
    List all registered HTTP, WebSocket, and API routes in the application.
    """
    import importlib

    from rich.table import Table

    module_name, app_name = app_str.split(":") if ":" in app_str else ("main", "app")
    sys.path.insert(0, os.getcwd())
    try:
        mod = importlib.import_module(module_name)
        application = getattr(mod, app_name)
    except Exception as e:
        console.print(
            f"[bold red]Error loading application '{app_str}':[/bold red] {e}"
        )
        raise typer.Exit(1) from None

    table = Table(title=f"🔮 Voodoo Routes ({app_str})", border_style="cyan")
    table.add_column("Type", style="magenta", no_wrap=True)
    table.add_column("Path", style="cyan")
    table.add_column("Methods", style="green")
    table.add_column("Name / Handler", style="dim")

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
