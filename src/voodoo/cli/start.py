"""Production server command for Voodoo applications."""

import os
from pathlib import Path

import typer


def start(
    app_str: str = typer.Argument(
        None,
        help="App instance to run. Defaults to main:app or voodoo.core:app.",
    ),
    host: str = typer.Option(None, help="Host to bind to. Defaults to VOODOO_HOST or 0.0.0.0."),
    port: int = typer.Option(None, help="Port to bind to. Defaults to PORT, VOODOO_PORT, or 8000."),
    workers: int = typer.Option(1, min=1, help="Number of Uvicorn worker processes."),
):
    """Start a Voodoo application in production mode."""
    if app_str is None:
        app_str = "main:app" if Path("main.py").exists() else "voodoo.core:app"

    resolved_host = host or os.getenv("VOODOO_HOST", "0.0.0.0")
    resolved_port = port or int(os.getenv("PORT") or os.getenv("VOODOO_PORT", "8000"))

    # Production should be the safe default for this command while still
    # allowing an explicitly configured environment to win.
    os.environ.setdefault("VOODOO_ENV", "production")

    import uvicorn

    uvicorn.run(
        app_str,
        host=resolved_host,
        port=resolved_port,
        workers=workers,
        proxy_headers=True,
        forwarded_allow_ips="*",
        http="h11",
        ws="auto",
        h11_max_incomplete_event_size=5_242_880,
    )
