"""Design tokens: one source of truth translated into CSS variables and
adapter config. Components reference semantic names only (``primary``,
``danger``, ``radius``); the concrete values live here.

All CSS variables use the ``--vd-*`` prefix to namespace Voodoo tokens and
avoid collisions with project-level CSS.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Token groups
# ---------------------------------------------------------------------------


class ThemeColors(BaseModel):
    """Semantic color palette."""

    primary: str = "#FAFAFA"  # Dark-mode action fill (near-white; Linear/Vercel)
    primary_hover: str = "#E4E4E7"  # Dark-mode hover (Zinc-200)
    secondary: str = "#6366F1"  # Indigo accent (links, focus, emphasis)

    # Status
    success: str = "#22C55E"
    warning: str = "#F59E0B"
    danger: str = "#EF4444"
    info: str = "#3B82F6"

    # Surfaces — dark mode
    background: str = "#09090B"  # Zinc-950
    surface: str = "#18181B"  # Zinc-900
    surface_raised: str = "#27272A"  # Zinc-800
    text: str = "#FAFAFA"
    text_muted: str = "#A1A1AA"  # Zinc-400 (readable on Zinc-950)
    border: str = "#27272A"  # Zinc-800

    # Surfaces — light mode
    light_background: str = "#FFFFFF"
    light_surface: str = "#FAFAFA"
    light_surface_raised: str = "#F4F4F5"
    light_text: str = "#18181B"
    light_text_muted: str = "#71717A"
    light_border: str = "#E4E4E7"

    # Action fill — light mode (primary inverts: near-black light, near-white dark)
    light_primary: str = "#18181B"  # Zinc-900
    light_primary_hover: str = "#27272A"  # Zinc-800

    # Accent fill — light mode. Defaults to the same indigo as dark mode so the
    # stock theme is unchanged; themes may darken it for contrast on white.
    light_secondary: str = "#6366F1"

    # On-color contrast — text/icons placed on top of a solid fill.
    # Kept explicit (not derived) so themes can force legible contrast.
    on_primary: str = "#09090B"  # near-black on the near-white dark-mode fill
    on_secondary: str = "#FFFFFF"  # white on the saturated accent
    light_on_primary: str = "#FFFFFF"  # white on the near-black light-mode fill
    light_on_secondary: str = "#FFFFFF"  # white on the (default) light accent

    # Allow extra colors
    extra: dict[str, str] = Field(default_factory=dict)

    def semantic(self) -> dict[str, str]:
        """All named colors (built-in + ``extra``) as semantic→value.

        Keys use hyphenated names (``primary-hover`` not ``primary_hover``)
        to match Tailwind/CSS conventions.
        """
        named = self.model_dump(
            exclude={
                "extra",
                "light_background",
                "light_surface",
                "light_surface_raised",
                "light_text",
                "light_text_muted",
                "light_border",
                "light_primary",
                "light_primary_hover",
                "light_secondary",
                "light_on_primary",
                "light_on_secondary",
            }
        )
        hyphenated = {k.replace("_", "-"): v for k, v in named.items()}
        return {**hyphenated, **self.extra}

    def light_overrides(self) -> dict[str, str]:
        return {
            "background": self.light_background,
            "surface": self.light_surface,
            "surface-raised": self.light_surface_raised,
            "text": self.light_text,
            "text-muted": self.light_text_muted,
            "border": self.light_border,
            "primary": self.light_primary,
            "primary-hover": self.light_primary_hover,
            "secondary": self.light_secondary,
            "on-primary": self.light_on_primary,
            "on-secondary": self.light_on_secondary,
        }


class ThemeSpacing(BaseModel):
    """Spacing scale (8px base)."""

    xs: str = "0.25rem"  # 4px
    sm: str = "0.5rem"  # 8px
    md: str = "0.75rem"  # 12px
    lg: str = "1rem"  # 16px
    xl: str = "1.5rem"  # 24px
    xxl: str = "2rem"  # 32px
    xxxl: str = "3rem"  # 48px


class ThemeRadius(BaseModel):
    """Corner radii."""

    sm: str = "0.375rem"
    md: str = "0.5rem"
    lg: str = "0.75rem"
    xl: str = "1rem"
    xxl: str = "1.5rem"
    full: str = "9999px"


class ThemeShadows(BaseModel):
    """Shadow scale — extremely subtle by default."""

    sm: str = "0 1px 2px 0 rgb(0 0 0 / 0.05)"
    md: str = "0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)"
    lg: str = "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)"


class ThemeMotion(BaseModel):
    """Transition durations."""

    fast: str = "150ms"
    normal: str = "200ms"
    slow: str = "300ms"


class ThemeBreakpoints(BaseModel):
    """Responsive breakpoints (mobile-first)."""

    sm: str = "640px"
    md: str = "768px"
    lg: str = "1024px"
    xl: str = "1280px"


class ThemeCode(BaseModel):
    """Syntax/terminal palette for ``CodeBlock`` — fixed-dark by default so the
    terminal reads as a window in both light and dark themes."""

    background: str = "#0F0D0B"
    surface: str = "#171412"
    border: str = "#26211D"
    text: str = "#D8CFC3"
    comment: str = "#6E645A"
    keyword: str = "#E8A33D"
    function: str = "#8AB4E8"
    string: str = "#A8C98A"
    live: str = "#46A758"


class ThemeTypography(BaseModel):
    """Typography settings."""

    font_family: str = (
        '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, '
        "Arial, sans-serif"
    )
    mono_family: str = (
        "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "
        '"Liberation Mono", "Courier New", monospace'
    )
    # Optional display/serif face for large headings. Empty = fall back to
    # ``font_family`` (the default theme is intentionally sans-serif throughout).
    display_family: str = ""
    # Font size scale
    xs: str = "0.75rem"  # 12px
    sm: str = "0.875rem"  # 14px
    md: str = "1rem"  # 16px
    lg: str = "1.125rem"  # 18px
    xl: str = "1.25rem"  # 20px
    xxl: str = "1.5rem"  # 24px
    xxxl: str = "2rem"  # 32px
    display: str = "3rem"  # 48px
    # Line heights
    tight: str = "1.2"
    normal: str = "1.5"
    relaxed: str = "1.75"
    # Font weights
    normal_weight: str = "400"
    medium_weight: str = "500"
    semibold_weight: str = "600"
    bold_weight: str = "700"


# ---------------------------------------------------------------------------
# Component overrides (Level 3 customization)
# ---------------------------------------------------------------------------


class ComponentOverrides(BaseModel):
    """Per-component class overrides from the theme.

    Each key is a component style key (``"button"``, ``"card"``); the value
    is a dict of slot→class-string. The adapter merges these with its own
    defaults.

    Example::

        theme.components = ComponentOverrides(
            button={
                "primary": "my-btn-primary",
            },
        )
    """

    model_config = {"extra": "allow"}

    def for_slot(self, component: str, slot: str = "root") -> str:
        """Return the override class for a component slot, or ``""``."""
        overrides: dict[str, Any] = getattr(self, component, None) or {}
        if isinstance(overrides, dict):
            return str(overrides.get(slot, ""))
        return ""


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------


class Theme(BaseModel):
    """Core theme configuration for Voodoo.

    The default theme is minimalist, modern, and follows an
    Apple × Linear × Vercel × Raycast aesthetic: generous whitespace,
    clean typography, subtle borders, moderate radius, extremely discreet
    shadows, and excellent dark mode.
    """

    mode: str = "dark"  # dark, light, system
    colors: ThemeColors = Field(default_factory=ThemeColors)
    spacing: ThemeSpacing = Field(default_factory=ThemeSpacing)
    radius: ThemeRadius = Field(default_factory=ThemeRadius)
    shadows: ThemeShadows = Field(default_factory=ThemeShadows)
    motion: ThemeMotion = Field(default_factory=ThemeMotion)
    typography: ThemeTypography = Field(default_factory=ThemeTypography)
    breakpoints: ThemeBreakpoints = Field(default_factory=ThemeBreakpoints)
    code: ThemeCode = Field(default_factory=ThemeCode)
    components: ComponentOverrides = Field(default_factory=ComponentOverrides)
    # Arbitrary extra tokens (``--vd-<name>: <value>``) for theme-specific
    # chrome that the core token set does not model (e.g. a custom glow).
    extra_tokens: dict[str, str] = Field(default_factory=dict)

    # -- CSS output ----------------------------------------------------------

    def to_css_variables(self) -> str:
        """Generate CSS custom properties with the ``--vd-`` prefix."""
        dark_color_vars = [
            f"--vd-color-{name}: {value};"
            for name, value in self.colors.semantic().items()
        ]
        light_color_vars = [
            f"--vd-color-{name}: {value};"
            for name, value in {
                **self.colors.semantic(),
                **self.colors.light_overrides(),
            }.items()
        ]
        spacing_vars = [
            f"--vd-space-{name}: {value};"
            for name, value in self.spacing.model_dump().items()
        ]
        radius_vars = [
            f"--vd-radius-{name}: {value};"
            for name, value in self.radius.model_dump().items()
        ]
        shadow_vars = [
            f"--vd-shadow-{name}: {value};"
            for name, value in self.shadows.model_dump().items()
        ]
        motion_vars = [
            f"--vd-motion-{name}: {value};"
            for name, value in self.motion.model_dump().items()
        ]
        typo_vars = [
            f"--vd-font-sans: {self.typography.font_family};",
            f"--vd-font-mono: {self.typography.mono_family};",
            f"--vd-font-display: {self.typography.display_family or self.typography.font_family};",
            f"--vd-text-xs: {self.typography.xs};",
            f"--vd-text-sm: {self.typography.sm};",
            f"--vd-text-md: {self.typography.md};",
            f"--vd-text-lg: {self.typography.lg};",
            f"--vd-text-xl: {self.typography.xl};",
            f"--vd-text-xxl: {self.typography.xxl};",
            f"--vd-text-xxxl: {self.typography.xxxl};",
            f"--vd-text-display: {self.typography.display};",
            f"--vd-leading-tight: {self.typography.tight};",
            f"--vd-leading-normal: {self.typography.normal};",
            f"--vd-leading-relaxed: {self.typography.relaxed};",
            f"--vd-weight-normal: {self.typography.normal_weight};",
            f"--vd-weight-medium: {self.typography.medium_weight};",
            f"--vd-weight-semibold: {self.typography.semibold_weight};",
            f"--vd-weight-bold: {self.typography.bold_weight};",
        ]
        breakpoint_vars = [
            f"--vd-breakpoint-{name}: {value};"
            for name, value in self.breakpoints.model_dump().items()
        ]
        code_vars = [
            f"--vd-code-{name}: {value};"
            for name, value in self.code.model_dump().items()
        ]
        # Derived accent tokens resolve against the *current* ``--vd-color-*``
        # value, so they track light/dark automatically (color-mix computes at
        # use time). Emitted once in ``:root`` and inherited by ``.dark``.
        derived_vars = [
            "--vd-color-secondary-soft: "
            "color-mix(in srgb, var(--vd-color-secondary) 12%, transparent);",
            "--vd-color-secondary-line: "
            "color-mix(in srgb, var(--vd-color-secondary) 32%, transparent);",
            "--vd-color-secondary-glow: "
            "color-mix(in srgb, var(--vd-color-secondary) 22%, transparent);",
            "--vd-color-border-soft: "
            "color-mix(in srgb, var(--vd-color-border) 80%, transparent);",
        ]
        extra_token_vars = [
            f"--vd-{name}: {value};" for name, value in self.extra_tokens.items()
        ]
        # Mode-independent tokens shared by ``:root`` and ``.dark``.
        shared_vars = (
            spacing_vars
            + radius_vars
            + shadow_vars
            + motion_vars
            + typo_vars
            + breakpoint_vars
            + code_vars
            + derived_vars
            + extra_token_vars
        )

        return (
            ":root {\n    "
            + "\n    ".join(light_color_vars + shared_vars)
            + "\n}\n"
            + ".dark {\n    "
            + "\n    ".join(dark_color_vars + shared_vars)
            + "\n}"
        )

    def to_tailwind_config(self) -> str:
        """Generate a Tailwind config JSON using ``--vd-*`` variables."""
        colors = {name: f"var(--vd-color-{name})" for name in self.colors.semantic()}
        config = {
            "darkMode": "class",
            "theme": {
                "extend": {
                    "colors": colors,
                    "borderRadius": {
                        "sm": "var(--vd-radius-sm)",
                        "md": "var(--vd-radius-md)",
                        "lg": "var(--vd-radius-lg)",
                        "xl": "var(--vd-radius-xl)",
                        "xxl": "var(--vd-radius-xxl)",
                        "full": "var(--vd-radius-full)",
                    },
                    "spacing": {
                        name: f"var(--vd-space-{name})"
                        for name in self.spacing.model_dump()
                    },
                    "boxShadow": {
                        "sm": "var(--vd-shadow-sm)",
                        "md": "var(--vd-shadow-md)",
                        "lg": "var(--vd-shadow-lg)",
                    },
                    "fontFamily": {
                        "sans": ["var(--vd-font-sans)"],
                        "mono": ["var(--vd-font-mono)"],
                        "display": ["var(--vd-font-display)"],
                    },
                    "transitionDuration": {
                        "fast": "var(--vd-motion-fast)",
                        "normal": "var(--vd-motion-normal)",
                        "slow": "var(--vd-motion-slow)",
                    },
                }
            },
        }
        return json.dumps(config)


# ---------------------------------------------------------------------------
# create_theme() — ergonomic factory
# ---------------------------------------------------------------------------


def create_theme(
    *,
    primary: str | None = None,
    secondary: str | None = None,
    background: str | None = None,
    surface: str | None = None,
    text: str | None = None,
    border: str | None = None,
    font: str | None = None,
    display_font: str | None = None,
    radius: str | None = None,
    mode: str = "dark",
    **extra_colors: str,
) -> Theme:
    """Create a theme with sensible defaults and simple overrides.

    Example::

        theme = create_theme(primary="#635BFF", font="Inter", radius="md")
        app = App(theme=theme)
    """
    colors = ThemeColors()
    if primary:
        colors.primary = primary
        colors.light_primary = primary
    if secondary:
        colors.secondary = secondary
    if background:
        colors.background = background
    if surface:
        colors.surface = surface
    if text:
        colors.text = text
    if border:
        colors.border = border
    if extra_colors:
        colors.extra = {**colors.extra, **extra_colors}

    typography = ThemeTypography()
    if font:
        typography.font_family = font
    if display_font:
        typography.display_family = display_font

    radius_obj = ThemeRadius()
    # radius="md" is already the default; this is for future token-mapped sizes

    return Theme(
        mode=mode,
        colors=colors,
        typography=typography,
        radius=radius_obj,
    )


# Global default theme
default_theme = Theme()


def set_theme(theme: Theme) -> None:
    """Set the global default theme."""
    global default_theme
    default_theme = theme


__all__ = [
    "ComponentOverrides",
    "Theme",
    "ThemeBreakpoints",
    "ThemeCode",
    "ThemeColors",
    "ThemeMotion",
    "ThemeRadius",
    "ThemeShadows",
    "ThemeSpacing",
    "ThemeTypography",
    "create_theme",
    "default_theme",
    "set_theme",
]
