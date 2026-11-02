"""Resolve every Design System color token from the public Theme contract.

Voodoo ships **no brand color**. The default Theme is a neutral monochrome
scale, and the visual layer consumes only the semantic tokens emitted here.
Every value below is derived from ``Theme.colors``; nothing is guessed from
whether a value "looks customized", so a Theme that reuses a default value is
still authoritative.

Derivation rules (per mode):

- ``brand`` is the optional ``accent`` when set, otherwise the ``primary``
  action fill. A neutral theme therefore has a neutral brand.
- ``on-*`` colors come from the Theme when explicit and are otherwise computed
  from WCAG relative luminance so text on a solid fill stays legible.
- Soft/line/strong status variants and every interactive state are produced
  with ``color-mix`` from the base tokens, so one seed recolors the interface.
"""

from __future__ import annotations

from voodoo.ui.styles.theme import Theme

__all__ = ["generate_design_system_theme_css", "readable_on"]

# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

_LIGHT_TEXT = "#ffffff"
_DARK_TEXT = "#000000"
_STATUSES = ("success", "warning", "danger", "info")


def _parse_hex(value: str) -> tuple[int, int, int] | None:
    """Return RGB for ``#rgb`` / ``#rrggbb`` values, otherwise ``None``."""
    text = value.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        return None
    try:
        return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)
    except ValueError:
        return None


def _luminance(rgb: tuple[int, int, int]) -> float:
    def channel(raw: int) -> float:
        value = raw / 255
        if value <= 0.03928:
            return value / 12.92
        return float(((value + 0.055) / 1.055) ** 2.4)

    red, green, blue = (channel(part) for part in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def readable_on(fill: str, fallback: str | None = None) -> str:
    """Return black or white, whichever has the higher contrast on ``fill``.

    Non-hex colors (``oklch(...)``, ``var(...)``) cannot be evaluated in
    Python, so the explicit ``fallback`` is returned instead.
    """
    rgb = _parse_hex(fill)
    if rgb is None:
        return fallback if fallback is not None else _LIGHT_TEXT
    lum = _luminance(rgb)
    contrast_white = 1.05 / (lum + 0.05)
    contrast_black = (lum + 0.05) / 0.05
    return _LIGHT_TEXT if contrast_white >= contrast_black else _DARK_TEXT


# ---------------------------------------------------------------------------
# Per-mode token resolution
# ---------------------------------------------------------------------------


def _mode_tokens(theme: Theme, *, light: bool) -> dict[str, str]:
    colors = theme.colors
    if light:
        accent = colors.light_accent or colors.accent
        primary = colors.light_primary
        on_primary = colors.light_on_primary
        on_accent = colors.light_on_accent or colors.on_accent
        tokens = {
            "canvas": colors.light_background,
            "panel": colors.light_surface,
            "panel-muted": colors.light_surface_raised,
            "line": colors.light_border,
            "ink": colors.light_text,
            "ink-muted": colors.light_text_muted,
            "shadow": colors.light_text,
        }
    else:
        accent = colors.accent
        primary = colors.primary
        on_primary = colors.on_primary
        on_accent = colors.on_accent
        tokens = {
            "canvas": colors.background,
            "panel": colors.surface,
            "panel-muted": colors.surface_raised,
            "line": colors.border,
            "ink": colors.text,
            "ink-muted": colors.text_muted,
            "shadow": _DARK_TEXT,
        }

    if accent:
        tokens["brand"] = accent
        tokens["on-brand"] = on_accent or readable_on(accent, on_primary)
    else:
        tokens["brand"] = primary
        tokens["on-brand"] = on_primary

    for status in _STATUSES:
        value = getattr(colors, status)
        tokens[status] = value
        tokens[f"on-{status}"] = readable_on(value)
    return tokens


def _status_block(name: str) -> str:
    base = f"var(--vd-color-{name})"
    return f"""    --vd-{name}-soft: color-mix(in srgb, {base} 10%, transparent);
    --vd-{name}-line: color-mix(in srgb, {base} 22%, transparent);
    --vd-{name}-strong: color-mix(in srgb, {base} 70%, var(--vd-ink));
    --vd-{name}-focus: color-mix(in srgb, {base} 20%, transparent);
    --vd-color-{name}-default: {base};"""


def _render_scope(selector: str, tokens: dict[str, str]) -> str:
    status_colors = "\n".join(
        f"    --vd-color-{name}: {tokens[name]};\n"
        f"    --vd-on-{name}: {tokens[f'on-{name}']};"
        for name in _STATUSES
    )
    status_blocks = "\n".join(_status_block(name) for name in _STATUSES)
    return f"""{selector} {{
    --vd-brand: {tokens["brand"]};
    --vd-on-brand: {tokens["on-brand"]};
    --vd-color-primary-fg: var(--vd-on-brand);
    --vd-brand-hover: color-mix(in srgb, var(--vd-brand) 88%, var(--vd-canvas));
    --vd-brand-strong: color-mix(in srgb, var(--vd-brand) 76%, var(--vd-canvas));
    --vd-brand-highlight: var(--vd-brand);
    --vd-brand-highlight-hover: var(--vd-brand-hover);
    --vd-brand-soft: color-mix(in srgb, var(--vd-brand) 10%, transparent);
    --vd-brand-softer: color-mix(in srgb, var(--vd-brand) 5%, transparent);
    --vd-brand-line: color-mix(in srgb, var(--vd-brand) 22%, transparent);
    --vd-brand-glow: color-mix(in srgb, var(--vd-brand) 20%, transparent);
    --vd-focus-ring: color-mix(in srgb, var(--vd-brand) 32%, transparent);

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
    --vd-overlay-scrim: color-mix(in srgb, var(--vd-shadow-color) 24%, transparent);
    --vd-shadow-color: {tokens["shadow"]};

{status_colors}
{status_blocks}
    --vd-danger-badge-strong: var(--vd-danger-strong);
}}"""


def generate_design_system_theme_css(theme: Theme) -> str:
    """Return the Theme-derived token layer for light (``:root``) and dark."""
    light = _render_scope(":root", _mode_tokens(theme, light=True))
    dark = _render_scope(".dark", _mode_tokens(theme, light=False))
    return f"""/* Voodoo Design System 4 — Theme contract */
{light}

{dark}"""
