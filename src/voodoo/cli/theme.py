"""voodoo theme — manage shareable theme presets.

Presets live in ``.voodoo/theme/theme.json`` (plus an optional sibling
``custom.css``), are installable from PyPI as ``voodoo-theme-<name>``, and can
be switched with ``voodoo theme use <name|path|url>``.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

import typer

from voodoo.cli import terminal
from voodoo.core.errors import ConfigurationError
from voodoo.security.redaction import redact_string
from voodoo.ui.styles.theme import Theme

logger = logging.getLogger(__name__)

theme_app = typer.Typer(
    name="theme",
    help="Manage shareable theme presets.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _project_theme_dir() -> Path:
    return Path.cwd() / ".voodoo" / "theme"


def _write_preset(
    directory: Path, *, name: str, theme: Theme, custom_css: str = ""
) -> None:
    """Materialize a theme into a project theme directory."""
    from voodoo.ui.styles.presets import ThemePreset

    preset = ThemePreset(name=name, theme=theme)
    directory.mkdir(parents=True, exist_ok=True)
    data = preset.model_dump(mode="json")
    (directory / "theme.json").write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )
    if custom_css:
        (directory / "custom.css").write_text(custom_css, encoding="utf-8")


@theme_app.command("list")
def list_themes(
    json_mode: bool = typer.Option(False, "--json", help="Machine-readable JSON"),
) -> None:
    """List discoverable theme presets."""
    from voodoo.ui.styles.presets import list_presets

    presets = list_presets()
    if json_mode or terminal.is_json_mode():
        terminal.json_output(presets)
        return
    terminal.wordmark()
    terminal.blank()
    terminal.status_block([("themes", str(len(presets)))])
    terminal.blank()
    if not presets:
        terminal.muted("no themes found")
        return
    for preset in presets:
        name = preset["name"]
        desc = preset["description"] or ""
        source = preset["source"]
        line = f"  [bold]{name}[/]"
        if desc:
            line += f" [dim]— {desc}[/]"
        if source != "builtin":
            line += f" [dim]({source})[/]"
        terminal.console.print(line)
    terminal.blank()


@theme_app.command("use")
def use_theme(
    preset: str = typer.Argument(..., help="Preset name, path, or URL"),
) -> None:
    """Switch the project to a preset (writes .voodoo/theme/theme.json)."""
    from voodoo.ui.styles.presets import resolve_theme

    try:
        source = resolve_theme(preset)
    except ConfigurationError as exc:
        terminal.error(str(exc), hint="try 'voodoo theme list'")
        raise typer.Exit(1) from exc

    directory = _project_theme_dir()
    _write_preset(
        directory, name=preset, theme=source.theme, custom_css=source.custom_css
    )
    terminal.wordmark()
    terminal.blank()
    terminal.status_block(
        [
            ("theme", source.theme.mode),
            ("origin", source.origin),
            ("written", str(directory)),
        ]
    )
    terminal.success("theme ready")


@theme_app.command("init")
def init_theme(
    name: str = typer.Argument(
        "default", help="Preset to snapshot as a starting point"
    ),
) -> None:
    """Generate .voodoo/theme/theme.json from a preset (start customizing)."""
    from voodoo.ui.styles.presets import resolve_theme

    try:
        source = resolve_theme(name)
    except ConfigurationError as exc:
        terminal.error(str(exc), hint="try 'voodoo theme list'")
        raise typer.Exit(1) from exc

    directory = _project_theme_dir()
    _write_preset(directory, name=name, theme=source.theme)
    # Create an empty custom.css if missing (editor-friendly escape hatch).
    custom_css = directory / "custom.css"
    if not custom_css.exists():
        custom_css.write_text(
            "/* Theme custom CSS — appended after the framework stylesheet. */\n",
            encoding="utf-8",
        )
    terminal.wordmark()
    terminal.blank()
    terminal.status_block([("written", str(directory))])
    terminal.next_steps(
        [
            "edit .voodoo/theme/theme.json to tune tokens",
            "add theme-specific CSS to .voodoo/theme/custom.css",
            'reference it in voodoo.toml: [theme] preset = "default"',
        ]
    )
    terminal.success("theme initialized")


@theme_app.command("new")
def new_theme(
    name: str = typer.Argument(..., help="Theme name, e.g. 'acme'"),
    accent: str | None = typer.Option(
        None, "--accent", help="Brand accent color (omit for monochrome)"
    ),
    base: str = typer.Option(
        "default", "--from", help="Preset to start from (name, path, or URL)"
    ),
    font: str | None = typer.Option(None, "--font", help="Body font family"),
    output: str | None = typer.Option(
        None, "--output", "-o", help="Directory to write (default: .voodoo/theme)"
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing theme"),
) -> None:
    """Create a theme from a preset and a few seeds (activates it by default)."""
    from voodoo.ui.styles.presets import resolve_theme

    try:
        source = resolve_theme(base)
    except ConfigurationError as exc:
        terminal.error(str(exc), hint="try 'voodoo theme list'")
        raise typer.Exit(1) from exc

    directory = Path(output) if output else _project_theme_dir()
    if (directory / "theme.json").exists() and not force:
        terminal.error(
            f"{directory / 'theme.json'} already exists",
            hint="pass --force to overwrite it",
        )
        raise typer.Exit(1)

    theme = source.theme.model_copy(deep=True)
    if accent:
        from voodoo.ui.styles.theme_validation import ensure_contrast

        theme.colors.accent = ensure_contrast(
            accent, (theme.colors.background, theme.colors.surface)
        )
        theme.colors.light_accent = ensure_contrast(
            accent, (theme.colors.light_background, theme.colors.light_surface)
        )
        theme.colors.on_accent = None
        theme.colors.light_on_accent = None
    if font:
        theme.typography.font_family = font
    _write_preset(directory, name=name, theme=theme, custom_css=source.custom_css)

    issues = _theme_issues(theme)
    terminal.wordmark()
    terminal.blank()
    terminal.status_block(
        [
            ("theme", name),
            ("based on", source.origin),
            ("accent", accent or "none (monochrome)"),
            ("written", str(directory)),
        ]
    )
    for issue in issues:
        terminal.warning(str(issue))
    terminal.next_steps(
        [
            f"edit {directory / 'theme.json'} to tune tokens",
            "run 'voodoo theme validate' to check contrast",
        ]
    )
    terminal.success("theme created")


def _theme_issues(theme: Theme) -> list[object]:
    from voodoo.ui.styles.theme_validation import validate_theme

    return list(validate_theme(theme))


@theme_app.command("validate")
def validate_theme_command(
    preset: str | None = typer.Argument(
        None, help="Preset name, path, or URL (default: the project theme)"
    ),
    json_mode: bool = typer.Option(False, "--json", help="Machine-readable JSON"),
    allow_unverified: bool = typer.Option(
        False,
        "--allow-unverified",
        help="Do not fail on non-hex colors that cannot be checked",
    ),
) -> None:
    """Check WCAG contrast for every pairing, in light and dark mode."""
    from voodoo.ui.styles.presets import resolve_theme
    from voodoo.ui.styles.theme_validation import ContrastIssue, validate_theme

    try:
        source = resolve_theme(preset)
    except ConfigurationError as exc:
        terminal.error(str(exc), hint="try 'voodoo theme list'")
        raise typer.Exit(1) from exc

    issues: list[ContrastIssue] = validate_theme(source.theme)
    failing = [i for i in issues if not (allow_unverified and i.unverified)]
    if json_mode:
        typer.echo(
            json.dumps(
                {
                    "origin": source.origin,
                    "valid": not failing,
                    "issues": [
                        {
                            "mode": i.mode,
                            "foreground": i.foreground,
                            "background": i.background,
                            "purpose": i.purpose,
                            "ratio": i.ratio,
                            "required": i.required,
                            "unverified": i.unverified,
                        }
                        for i in issues
                    ],
                },
                indent=2,
            )
        )
    else:
        for issue in issues:
            terminal.warning(str(issue))
        if not failing:
            terminal.success(f"theme valid ({source.origin})")
    if failing:
        if not json_mode:
            terminal.error(f"{len(failing)} contrast issue(s) in {source.origin}")
        raise typer.Exit(1)


@theme_app.command("install")
def install_theme(
    name: str = typer.Argument(
        ..., help="Preset name (PyPI package voodoo-theme-<name>)"
    ),
) -> None:
    """Install a theme preset from PyPI (pip install voodoo-theme-<name>)."""
    from voodoo.ui.styles.presets import _load_from_pypi

    pkg = f"voodoo-theme-{name}"
    try:
        source = _load_from_pypi(name)
        terminal.wordmark()
        terminal.blank()
        terminal.status_block([("theme", name), ("status", "already installed")])
        terminal.console.print(f"  [dim]{source.origin}[/]")
        return
    except ConfigurationError as error:
        logger.info(
            "theme preset lookup fell back to package installation name=%s error=%s",
            redact_string(name),
            redact_string(str(error)),
        )
        pass

    terminal.wordmark()
    terminal.blank()
    terminal.info(f"installing {pkg} ...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", pkg],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        terminal.error(
            f"install failed: {result.stderr.strip() or result.stdout.strip()}",
            hint="check the theme name, Python environment, and network access, then retry",
        )
        raise typer.Exit(1)

    try:
        source = _load_from_pypi(name)
    except ConfigurationError as exc:
        terminal.error(
            str(exc), hint="try 'voodoo theme list' or verify the theme name"
        )
        raise typer.Exit(1) from exc
    terminal.status_block([("theme", name), ("status", "installed")])
    terminal.console.print(f"  [dim]{source.origin}[/]")
    terminal.success("theme installed")


__all__ = ["theme_app"]
