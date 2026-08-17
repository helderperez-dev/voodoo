"""Simplify voodoo ai init - no interactive prompts, auto-detect IDE."""

from pathlib import Path

import typer
from rich.progress import Progress, SpinnerColumn, TextColumn

from voodoo.cli import terminal
from voodoo.cli.scaffolding import _detect_ide, _sync_ai_assets

ai_app = typer.Typer(
    help="Manage AI development context and IDE integrations.",
    no_args_is_help=True,
    add_completion=False,
)


@ai_app.command()
def init(
    ide: str = typer.Option(
        None,
        "--ide",
        "-i",
        help="Target AI IDE rules (trae, cursor, windsurf, vscode, all, none). Auto-detects if omitted.",
    ),
):
    """
    Generate AI development context (.voodoo/ai/) and optional IDE-specific integrations.
    """
    valid_ides = ["trae", "cursor", "windsurf", "vscode", "all", "none"]
    selected_ide = ide.lower() if ide else None

    if selected_ide and selected_ide not in valid_ides:
        terminal.error(
            f"Invalid IDE '{selected_ide}'. Choose from: {', '.join(valid_ides)}",
        )
        raise typer.Exit(1)

    if not selected_ide:
        selected_ide = _detect_ide() or "none"

    terminal.wordmark()
    terminal.blank()
    terminal.label_value("ide", selected_ide)
    terminal.muted("generating ai context")
    terminal.blank()

    with Progress(
        SpinnerColumn(style="white"),
        TextColumn("[dim]{task.description}[/]"),
        transient=True,
    ) as progress:
        progress.add_task(
            description="writing .voodoo/ai docs...",
            total=None,
        )
        _sync_ai_assets(Path("."), progress, ide=selected_ide)

    terminal.success("ready")
    terminal.muted(".voodoo/ai/")
    if selected_ide != "none":
        terminal.muted(f"ide rules: {selected_ide}")
    terminal.blank()
