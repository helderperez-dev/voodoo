"""CLI: ``voodoo protocol export`` — export JSON Schema for protocol entities."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from voodoo.protocol import export_json_schemas, schema_for

__all__ = ["protocol_app"]

protocol_app = typer.Typer(
    name="protocol",
    help="Protocol schema operations.",
    no_args_is_help=True,
)


@protocol_app.command("export")
def export_schemas(
    output: str = typer.Option(
        "",
        "--output",
        "-o",
        help="Output file path (default: stdout).",
    ),
    entity: str = typer.Option(
        "",
        "--entity",
        "-e",
        help="Export a single entity by name (e.g. 'Execution').",
    ),
    indent: int = typer.Option(2, "--indent", help="JSON indentation."),
) -> None:
    """Export JSON Schema for all Voodoo protocol entities."""
    if entity:
        try:
            schema = schema_for(entity)
        except KeyError:
            typer.echo(f"Unknown entity: {entity}", err=True)
            typer.echo(f"Available: {', '.join(sorted(_entity_names()))}", err=True)
            raise typer.Exit(1) from None
        result = json.dumps(schema, indent=indent, default=str)
    else:
        schemas = export_json_schemas()
        result = json.dumps(schemas, indent=indent, default=str)

    if output:
        Path(output).write_text(result + "\n")
        count = 1 if entity else len(_entity_names())
        typer.echo(f"Exported {count} schema(s) to {output}")
    else:
        typer.echo(result)


@protocol_app.command("list")
def list_entities() -> None:
    """List all protocol entity names."""
    for name in sorted(_entity_names()):
        typer.echo(name)


def _entity_names() -> list[str]:
    from voodoo.protocol.schemas import PROTOCOL_ENTITIES

    return list(PROTOCOL_ENTITIES.keys())
