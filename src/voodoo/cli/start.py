"""Production server command for Voodoo applications."""

from __future__ import annotations

import os
from pathlib import Path

import typer

__all__ = ["start"]


def start(
    app_str: str | None = typer.Argument(
        None,
        help="App instance to run. Defaults to main:app or voodoo.core:app.",
    ),
    host: str | None = typer.Option(
        None,
        help="Host to bind to. Defaults to VOODOO_HOST or 0.0.0.0.",
    ),
    port: int | None = typer.Option(
        None,
        help="Port to bind to. Defaults to PORT, VOODOO_PORT, or 8000.",
    ),
) -> None:
    """Start a Voodoo application in production mode."""
    if app_str is None:
        app_str = "main:app" if Path("main.py").exists() else "voodoo.core:app"

    resolved_host = host or os.getenv("VOODOO_HOST") or "0.0.0.0"
    configured_port = os.getenv("PORT") or os.getenv("VOODOO_PORT") or "8000"
    resolved_port = port if port is not None else int(configured_port)

    # Production should be the safe default for this command while still
    # allowing an explicitly configured environment to win.
    os.environ.setdefault("VOODOO_ENV", "production")
    os.environ.setdefault("WEBSOCKETS_MAX_LINE_LENGTH", "8388608")
    os.environ.setdefault("WEBSOCKETS_MAX_NUM_HEADERS", "256")

    import uvicorn

    uvicorn.run(
        app_str,
        host=resolved_host,
        port=resolved_port,
        # One process owns one live local Store writer. Horizontal scaling uses
        # separate Voodoo Nodes with node-local Stores.
        workers=1,
        proxy_headers=True,
        forwarded_allow_ips=os.getenv("FORWARDED_ALLOW_IPS", "127.0.0.1"),
        http="h11",
        ws="websockets",
        h11_max_incomplete_event_size=5_242_880,
    )
