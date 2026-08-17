"""Centralized terminal presentation layer for the Voodoo CLI.

Implements the Voodoo visual identity: monochromatic with #C8FF3D accent,
structured label/value output, no emoji/ASCII art/banners, concise status words.
"""

from __future__ import annotations

import sys
from typing import Any

from rich.console import Console

# Single shared console instance
console = Console()

# ── Color palette ──────────────────────────────────────────────

ACCENT = "#C8FF3D"
ERROR = "#FF5C5C"
WARNING = "#F2C94C"
PRIMARY = "#EDEDED"
SECONDARY = "#A3A3A3"
MUTED = "#737373"
SUBTLE = "#525252"
DIVIDER = "#262626"

# Status word → color mapping
_STATUS_COLORS = {
    "ready": ACCENT,
    "running": ACCENT,
    "created": ACCENT,
    "connected": ACCENT,
    "ok": ACCENT,
    "failed": ERROR,
    "error": ERROR,
    "stopped": ERROR,
    "disconnected": ERROR,
    "warning": WARNING,
    "waiting": WARNING,
    "building": WARNING,
    "deploying": WARNING,
    "disabled": MUTED,
    "missing": MUTED,
    "not found": MUTED,
}


# ── Output primitives ──────────────────────────────────────────


def wordmark(version: str | None = None) -> None:
    """Print the voodoo wordmark, optionally with version."""
    if version:
        console.print(f"[bold]voodoo[/] [dim]{version}[/]")
    else:
        console.print("[bold]voodoo[/]")


def heading(text: str) -> None:
    """Print a section heading."""
    console.print(f"\n[bold]{text}[/]")


def label_value(label: str, value: Any, *, label_width: int = 14) -> None:
    """Print an aligned label/value pair."""
    console.print(f"  [dim]{label:<{label_width}}[/] [primary]{value}[/]")


def status(label: str, state: str, *, label_width: int = 14) -> None:
    """Print a label with a status word."""
    color = _STATUS_COLORS.get(state.lower(), PRIMARY)
    console.print(f"  [dim]{label:<{label_width}}[/] [{color}]{state}[/]")


def info(message: str) -> None:
    """Print a primary information line."""
    console.print(f"  {message}")


def muted(message: str) -> None:
    """Print muted/secondary text."""
    console.print(f"  [dim]{message}[/]")


def accent_text(text: str) -> None:
    """Print text with the voodoo accent color."""
    console.print(f"  [{ACCENT}]{text}[/]")


def divider() -> None:
    """Print a subtle divider."""
    console.print(f"  [{DIVIDER}]{'─' * 40}[/]")


def blank() -> None:
    """Print a blank line."""
    console.print()


def success(message: str = "ready") -> None:
    """Print an understated success state."""
    console.print(f"\n  [{ACCENT}]{message}[/]")


def error(message: str, *, hint: str | None = None) -> None:
    """Print a clear, actionable error."""
    console.print(f"\n  [{ERROR}]{message}[/]")
    if hint:
        console.print(f"\n  [dim]→ {hint}[/]")


def warning(message: str) -> None:
    """Print a warning."""
    console.print(f"  [{WARNING}]{message}[/]")


def kv_block(pairs: list[tuple[str, str]], *, label_width: int = 14) -> None:
    """Print a block of label/value pairs."""
    for label, value in pairs:
        label_value(label, value, label_width=label_width)


def status_block(pairs: list[tuple[str, str]], *, label_width: int = 14) -> None:
    """Print a block of label/status pairs."""
    for label, state in pairs:
        status(label, state, label_width=label_width)


def tree(items: list[str], *, indent: int = 2) -> None:
    """Print a simple tree structure."""
    prefix = " " * indent
    for item in items:
        console.print(f"{prefix}{item}")


def next_steps(steps: list[str]) -> None:
    """Print next steps."""
    console.print()
    for step in steps:
        console.print(f"  [dim]{step}[/]")
    console.print()


def json_output(data: Any) -> None:
    """Print clean JSON for machine-readable output."""
    import json

    console.print(json.dumps(data, indent=2, default=str))


def is_json_mode() -> bool:
    """Check if --json flag was passed."""
    return "--json" in sys.argv
