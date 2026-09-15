"""Resolve Design System 3 visual tokens from the public Theme contract.

Design System 3 introduced a stronger Voodoo visual identity with its own
premium surface palette. The public ``Theme`` API predates those visual tokens,
so this bridge keeps the approved DS3 defaults while making explicit Theme
customizations authoritative again.
"""

from __future__ import annotations

from voodoo.ui.styles.theme import Theme, ThemeColors

_DEFAULTS = ThemeColors()


def _dark_value(current: str, legacy_default: str, premium_default: str) -> str:
    """Use the DS3 default unless the Theme explicitly changed the value."""
    return premium_default if current == legacy_default else current


def _light_value(
    light_value: str,
    light_default: str,
    shared_value: str,
    shared_default: str,
    premium_default: str,
) -> str:
    """Prefer an explicit light override, then a shared override, then DS3."""
    if light_value != light_default:
        return light_value
    if shared_value != shared_default:
        return shared_value
    return premium_default


def _brand(theme: Theme, *, light: bool) -> str:
    colors = theme.colors

    if light:
        if colors.light_primary != _DEFAULTS.light_primary:
            return colors.light_primary
        if colors.light_secondary != _DEFAULTS.light_secondary:
            return colors.light_secondary
        if colors.primary != _DEFAULTS.primary:
            return colors.primary
        if colors.secondary != _DEFAULTS.secondary:
            return colors.secondary
    else:
        if colors.primary != _DEFAULTS.primary:
            return colors.primary
        if colors.secondary != _DEFAULTS.secondary:
            return colors.secondary

    return "#7c3aed"


def _mode_tokens(theme: Theme, *, light: bool) -> dict[str, str]:
    colors = theme.colors

    if light:
        return {
            "brand": _brand(theme, light=True),
            "canvas": _light_value(
                colors.light_background,
                _DEFAULTS.light_background,
                colors.background,
                _DEFAULTS.background,
                "#ffffff",
            ),
            "panel": _light_value(
                colors.light_surface,
                _DEFAULTS.light_surface,
                colors.surface,
                _DEFAULTS.surface,
                "#ffffff",
            ),
            "panel-muted": _light_value(
                colors.light_surface_raised,
                _DEFAULTS.light_surface_raised,
                colors.surface_raised,
                _DEFAULTS.surface_raised,
                "#f6f6f8",
            ),
            "line": _light_value(
                colors.light_border,
                _DEFAULTS.light_border,
                colors.border,
                _DEFAULTS.border,
                "#e8e8ed",
            ),
            "ink": _light_value(
                colors.light_text,
                _DEFAULTS.light_text,
                colors.text,
                _DEFAULTS.text,
                "#111118",
            ),
            "ink-muted": _light_value(
                colors.light_text_muted,
                _DEFAULTS.light_text_muted,
                colors.text_muted,
                _DEFAULTS.text_muted,
                "#6f6f7b",
            ),
        }

    return {
        "brand": _brand(theme, light=False),
        "canvas": _dark_value(colors.background, _DEFAULTS.background, "#09090f"),
        "panel": _dark_value(colors.surface, _DEFAULTS.surface, "#101017"),
        "panel-muted": _dark_value(
            colors.surface_raised, _DEFAULTS.surface_raised, "#171720"
        ),
        "line": _dark_value(colors.border, _DEFAULTS.border, "#252532"),
        "ink": _dark_value(colors.text, _DEFAULTS.text, "#f7f7fb"),
        "ink-muted": _dark_value(colors.text_muted, _DEFAULTS.text_muted, "#aaaab7"),
    }


def _render_scope(selector: str, tokens: dict[str, str]) -> str:
    return f"""{selector} {{
    --vd-brand: {tokens["brand"]};
    --vd-brand-hover: color-mix(in srgb, var(--vd-brand) 88%, black);
    --vd-brand-strong: color-mix(in srgb, var(--vd-brand) 76%, black);
    --vd-brand-soft: color-mix(in srgb, var(--vd-brand) 10%, transparent);
    --vd-brand-softer: color-mix(in srgb, var(--vd-brand) 5%, transparent);
    --vd-brand-line: color-mix(in srgb, var(--vd-brand) 22%, transparent);
    --vd-brand-glow: color-mix(in srgb, var(--vd-brand) 20%, transparent);
    --vd-focus-ring: color-mix(in srgb, var(--vd-brand) 28%, transparent);

    --vd-canvas: {tokens["canvas"]};
    --vd-panel: {tokens["panel"]};
    --vd-panel-subtle: color-mix(in srgb, var(--vd-panel) 72%, var(--vd-canvas));
    --vd-panel-muted: {tokens["panel-muted"]};
    --vd-line: {tokens["line"]};
    --vd-line-strong: color-mix(in srgb, var(--vd-line) 82%, var(--vd-ink));
    --vd-ink: {tokens["ink"]};
    --vd-ink-muted: {tokens["ink-muted"]};
    --vd-ink-faint: color-mix(in srgb, var(--vd-ink-muted) 72%, transparent);
    --vd-surface-hover: color-mix(in srgb, var(--vd-ink) 4%, var(--vd-panel));
    --vd-surface-pressed: color-mix(in srgb, var(--vd-ink) 7%, var(--vd-panel));
    --vd-overlay: color-mix(in srgb, var(--vd-canvas) 82%, transparent);
}}"""


def generate_design_system_theme_css(theme: Theme) -> str:
    """Return the Theme-authoritative DS3 token bridge for light and dark."""
    light = _render_scope(":root", _mode_tokens(theme, light=True))
    dark = _render_scope(".dark", _mode_tokens(theme, light=False))
    return f"""/* Voodoo Design System 3 — Theme contract */
{light}

{dark}"""


__all__ = ["generate_design_system_theme_css"]
