"""Theme tokens: one source of truth translated into CSS variables and a
Tailwind config. Components reference semantic names only (``primary``,
``danger``, ``radius``); the concrete values live here.
"""

import json

from pydantic import BaseModel, Field


class ThemeColors(BaseModel):
    """Modern color palette for the theme."""

    primary: str = "#007AFF"  # Apple blue
    primary_hover: str = "#0066D6"  # Darkened primary
    secondary: str = "#5856D6"  # Violet

    # Status
    success: str = "#22C55E"
    warning: str = "#F59E0B"
    danger: str = "#EF4444"

    # Dark mode
    background: str = "#0A0A0A"  # Charcoal
    surface: str = "rgba(255, 255, 255, 0.05)"  # Glass surface
    text: str = "#F3F4F6"
    text_muted: str = "#9CA3AF"
    border: str = "rgba(255, 255, 255, 0.1)"

    # Light mode
    light_background: str = "#F9FAFB"
    light_surface: str = "rgba(0, 0, 0, 0.05)"
    light_text: str = "#111827"
    light_text_muted: str = "#4B5563"
    light_border: str = "rgba(0, 0, 0, 0.1)"

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
                "light_text",
                "light_text_muted",
                "light_border",
            }
        )
        hyphenated = {k.replace("_", "-"): v for k, v in named.items()}
        return {**hyphenated, **self.extra}


class ThemeRadius(BaseModel):
    """Corner radii."""

    sm: str = "0.375rem"
    md: str = "0.5rem"
    lg: str = "0.75rem"
    full: str = "9999px"


class ThemeFonts(BaseModel):
    """Typography settings."""

    sans: str = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif'
    mono: str = 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace'


class Theme(BaseModel):
    """
    Core Theme configuration for Voodoo.
    Designed for modern macOS 'glass' aesthetic.
    """

    mode: str = "dark"  # dark, light, system
    colors: ThemeColors = Field(default_factory=ThemeColors)
    radius: ThemeRadius = Field(default_factory=ThemeRadius)
    fonts: ThemeFonts = Field(default_factory=ThemeFonts)

    def to_tailwind_config(self) -> str:
        """Generates the Tailwind configuration script."""
        config = {
            "darkMode": "class",
            "theme": {
                "extend": {
                    "colors": self.colors.semantic(),
                    "borderRadius": {
                        "sm": self.radius.sm,
                        "md": self.radius.md,
                        "lg": self.radius.lg,
                        "full": self.radius.full,
                    },
                    "fontFamily": {
                        "sans": [self.fonts.sans],
                        "mono": [self.fonts.mono],
                    },
                }
            },
        }
        return json.dumps(config)

    def to_css_variables(self) -> str:
        """Generates global CSS variables for the theme."""
        base_colors = self.colors.semantic()

        dark_vars = (
            [
                f"--color-{name.replace('_', '-')}: {value};"
                for name, value in base_colors.items()
            ]
            + [
                f"--radius-{name}: {value};"
                for name, value in self.radius.model_dump().items()
            ]
            + [
                f"--font-sans: {self.fonts.sans};",
                f"--font-mono: {self.fonts.mono};",
            ]
        )

        light_overrides = {
            "background": self.colors.light_background,
            "surface": self.colors.light_surface,
            "text": self.colors.light_text,
            "text_muted": self.colors.light_text_muted,
            "border": self.colors.light_border,
        }
        light_vars = (
            [
                f"--color-{name.replace('_', '-')}: {value};"
                for name, value in {**base_colors, **light_overrides}.items()
            ]
            + [
                f"--radius-{name}: {value};"
                for name, value in self.radius.model_dump().items()
            ]
            + [
                f"--font-sans: {self.fonts.sans};",
                f"--font-mono: {self.fonts.mono};",
            ]
        )

        return (
            ":root {\n    "
            + "\n    ".join(light_vars)
            + "\n}\n"
            + ".dark {\n    "
            + "\n    ".join(dark_vars)
            + "\n}"
        )


# Global default theme
default_theme = Theme()


def set_theme(theme: Theme):
    """Sets the global default theme."""
    global default_theme
    default_theme = theme
