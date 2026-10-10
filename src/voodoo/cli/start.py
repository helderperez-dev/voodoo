"""Production server command for Voodoo applications."""

from __future__ import annotations

import os
from pathlib import Path
from typing import cast

import typer

__all__ = ["start"]


def _forwarded_allow_ips() -> str:
    """Return a non-wildcard proxy trust list for Uvicorn.

    Trusting ``X-Forwarded-*`` from every source lets an Internet client forge
    scheme, host, and client-IP information.  Operators may still provide a
    comma-separated IP/CIDR/host list, but the wildcard is never accepted by
    the production entry point.
    """
    value = os.getenv("FORWARDED_ALLOW_IPS", "127.0.0.1").strip()
    entries = [entry.strip() for entry in value.split(",") if entry.strip()]
    if not entries or "*" in entries:
        raise ValueError(
            "FORWARDED_ALLOW_IPS must contain explicit proxy IPs, CIDRs, or hosts"
        )
    return ",".join(entries)


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

    defaults = {
        "VOODOO_ENV": "production",
        "WEBSOCKETS_MAX_LINE_LENGTH": "8388608",
        "WEBSOCKETS_MAX_NUM_HEADERS": "256",
    }
    previous: dict[str, str | None] = {name: os.environ.get(name) for name in defaults}
    for name, value in defaults.items():
        os.environ.setdefault(name, value)

    try:
        from voodoo.config import get_config, validate_production_config
        from voodoo.core.errors import ConfigurationError

        try:
            validate_production_config(get_config())
        except ConfigurationError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        try:
            forwarded_allow_ips = _forwarded_allow_ips()
        except ValueError as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        import uvicorn

        uvicorn.run(
            app_str,
            host=resolved_host,
            port=resolved_port,
            # One process owns one live local Store writer. Horizontal scaling uses
            # separate Voodoo Nodes with node-local Stores.
            workers=1,
            proxy_headers=True,
            forwarded_allow_ips=forwarded_allow_ips,
            http="h11",
            ws="websockets",
            h11_max_incomplete_event_size=5_242_880,
        )
    finally:
        for env_name, previous_value in previous.items():
            if previous_value is None:
                os.environ.pop(env_name, None)
            else:
                os.environ[env_name] = cast(str, previous_value)
