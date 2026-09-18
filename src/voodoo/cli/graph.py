"""Inspect the semantic Voodoo Application Graph."""

from __future__ import annotations

import json
import typer

from voodoo.cli.inspect import _load_app
from voodoo.runtime.application_graph import build_application_graph


def graph(
    app_str: str = typer.Option(None, "--app", help="App instance (e.g. main:app)"),
    json_mode: bool = typer.Option(False, "--json", help="Output machine-readable JSON"),
) -> None:
    """Show the semantic structure Voodoo knows about the application."""
    app = _load_app(app_str)
    application_graph = build_application_graph(app)
    data = application_graph.snapshot()

    if json_mode:
        typer.echo(json.dumps(data, indent=2, sort_keys=True))
        return

    typer.echo("Voodoo Application Graph")
    typer.echo("")
    for node in data["nodes"]:
        if node["kind"] == "application":
            continue
        typer.echo(f"  {node['kind']:<12} {node['name']}")
    typer.echo("")
    typer.echo(f"{len(data['nodes'])} nodes · {len(data['edges'])} relationships")
    typer.echo(f"fingerprint {data['fingerprint'][:12]}")
