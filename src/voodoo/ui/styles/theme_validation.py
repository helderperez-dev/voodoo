"""Validate that a Theme is accessible before it is shared or shipped.

A theme is a data file that can restyle every component, so the guarantees a
component contract relies on (legible text, visible controls) must be checkable
from the theme alone. :func:`validate_theme` evaluates the WCAG contrast of
every foreground/background pairing the Design System actually renders, in both
light and dark mode.

Only hex colors can be evaluated in Python; values such as ``oklch(...)`` are
reported as ``unverified`` instead of silently passing.
"""

from __future__ import annotations

from dataclasses import dataclass

from voodoo.ui.styles.theme import Theme
from voodoo.ui.styles.theme_contract import _mode_tokens, _parse_hex

__all__ = ["ContrastIssue", "contrast_ratio", "ensure_contrast", "validate_theme"]

#: WCAG AA for body text.
TEXT_MINIMUM = 4.5
#: WCAG 2.1 non-text contrast for controls, focus indicators and boundaries.
UI_MINIMUM = 3.0

# (foreground token, background token, minimum ratio, purpose)
_PAIRS: tuple[tuple[str, str, float, str], ...] = (
    ("ink", "canvas", TEXT_MINIMUM, "body text on canvas"),
    ("ink", "panel", TEXT_MINIMUM, "body text on panels"),
    ("ink", "panel-muted", TEXT_MINIMUM, "body text on raised surfaces"),
    ("ink-muted", "canvas", TEXT_MINIMUM, "secondary text on canvas"),
    ("ink-muted", "panel", TEXT_MINIMUM, "secondary text on panels"),
    ("on-brand", "brand", TEXT_MINIMUM, "text on brand fills"),
    ("on-success", "success", TEXT_MINIMUM, "text on success fills"),
    ("on-warning", "warning", TEXT_MINIMUM, "text on warning fills"),
    ("on-danger", "danger", TEXT_MINIMUM, "text on danger fills"),
    ("on-info", "info", TEXT_MINIMUM, "text on info fills"),
    ("brand", "canvas", UI_MINIMUM, "focus ring and brand controls on canvas"),
    ("brand", "panel", UI_MINIMUM, "focus ring and brand controls on panels"),
)


@dataclass(frozen=True)
class ContrastIssue:
    """One failing or unverifiable foreground/background pairing."""

    mode: str
    foreground: str
    background: str
    purpose: str
    ratio: float | None
    required: float

    @property
    def unverified(self) -> bool:
        return self.ratio is None

    def __str__(self) -> str:
        if self.ratio is None:
            return (
                f"[{self.mode}] {self.purpose}: {self.foreground} on "
                f"{self.background} cannot be verified (non-hex color)"
            )
        return (
            f"[{self.mode}] {self.purpose}: {self.foreground} on "
            f"{self.background} is {self.ratio:.2f}:1, needs {self.required}:1"
        )


def _luminance(rgb: tuple[int, int, int]) -> float:
    def channel(raw: int) -> float:
        value = raw / 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = (channel(part) for part in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(foreground: str, background: str) -> float | None:
    """Return the WCAG contrast ratio, or ``None`` for non-hex colors."""
    fg = _parse_hex(foreground)
    bg = _parse_hex(background)
    if fg is None or bg is None:
        return None
    lighter, darker = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def validate_theme(theme: Theme) -> list[ContrastIssue]:
    """Return every contrast failure for light and dark mode (empty = valid)."""
    issues: list[ContrastIssue] = []
    for mode, light in (("light", True), ("dark", False)):
        tokens = _mode_tokens(theme, light=light)
        for fg, bg, required, purpose in _PAIRS:
            ratio = contrast_ratio(tokens[fg], tokens[bg])
            if ratio is None or ratio < required:
                issues.append(ContrastIssue(mode, fg, bg, purpose, ratio, required))
    return issues


def _to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def ensure_contrast(
    color: str, backgrounds: tuple[str, ...], minimum: float = UI_MINIMUM
) -> str:
    """Nudge ``color`` toward black or white until it meets ``minimum``.

    The hue is preserved; only lightness moves, in the direction that increases
    contrast with the given backgrounds. Non-hex colors are returned unchanged.
    """
    rgb = _parse_hex(color)
    if rgb is None or not backgrounds:
        return color

    def worst(value: tuple[int, int, int]) -> float:
        ratios = [contrast_ratio(_to_hex(value), bg) for bg in backgrounds]
        return min(r for r in ratios if r is not None) if ratios else minimum

    if worst(rgb) >= minimum:
        return color
    bg_lum = sum(
        _luminance(parsed) for bg in backgrounds if (parsed := _parse_hex(bg))
    ) / len(backgrounds)
    target = (0, 0, 0) if bg_lum > 0.5 else (255, 255, 255)
    for step in range(1, 21):
        weight = step * 0.05
        mixed = tuple(
            round(channel * (1 - weight) + goal * weight)
            for channel, goal in zip(rgb, target, strict=True)
        )
        candidate = (mixed[0], mixed[1], mixed[2])
        if worst(candidate) >= minimum:
            return _to_hex(candidate)
    return _to_hex(target)
