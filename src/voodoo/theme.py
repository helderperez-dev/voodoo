"""Compatibility alias — design tokens live in ``voodoo.ui.styles.theme``.

This shim replaces itself with the real module in ``sys.modules`` so that
``voodoo.theme is voodoo.ui.styles.theme`` and mutable globals
(``default_theme``) are always current. The static imports below are for
type checkers only (mypy cannot follow the runtime aliasing).
"""

import sys

from voodoo.ui.styles import theme
from voodoo.ui.styles.theme import (  # noqa: F401
    ComponentOverrides,
    Theme,
    ThemeColors,
    ThemeMotion,
    ThemeRadius,
    ThemeShadows,
    ThemeSpacing,
    ThemeTypography,
    create_theme,
    default_theme,
    set_theme,
)

sys.modules[__name__] = theme
