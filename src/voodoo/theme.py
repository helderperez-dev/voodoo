"""Compatibility alias for :mod:`voodoo.ui.styles.theme`."""

import sys

from voodoo.ui.styles import theme

ComponentOverrides = theme.ComponentOverrides
Theme = theme.Theme
ThemeBreakpoints = theme.ThemeBreakpoints
ThemeCode = theme.ThemeCode
ThemeColors = theme.ThemeColors
ThemeMotion = theme.ThemeMotion
ThemePalette = theme.ThemePalette
ThemeRadius = theme.ThemeRadius
ThemeShadows = theme.ThemeShadows
ThemeSpacing = theme.ThemeSpacing
ThemeTypography = theme.ThemeTypography
create_theme = theme.create_theme
default_theme = theme.default_theme
set_theme = theme.set_theme

__all__ = [
    "ComponentOverrides", "Theme", "ThemeBreakpoints", "ThemeCode", "ThemeColors",
    "ThemeMotion", "ThemePalette", "ThemeRadius", "ThemeShadows", "ThemeSpacing",
    "ThemeTypography", "create_theme", "default_theme", "set_theme",
]

sys.modules[__name__] = theme
