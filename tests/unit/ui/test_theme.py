import pytest

from voodoo.ui.styles.theme import (
    Theme,
    ThemeColors,
    ThemePalette,
    ThemeShadows,
    ThemeSpacing,
    create_theme,
    default_theme,
    set_theme,
)
from voodoo.ui.styles.palette import color


def test_default_theme():
    assert default_theme.mode == "dark"
    assert default_theme.colors.primary == "#FAFAFA"


def test_custom_theme():
    custom_colors = ThemeColors(primary="#FF0000", extra={"custom": "#00FF00"})
    theme = Theme(mode="light", colors=custom_colors)

    assert theme.mode == "light"
    assert theme.colors.primary == "#FF0000"

    css_vars = theme.to_css_variables()
    assert "--vd-color-primary: #FF0000;" in css_vars
    assert "--vd-color-custom: #00FF00;" in css_vars

    tw_config = theme.to_tailwind_config()
    assert '"primary"' in tw_config
    assert "var(--vd-color-primary)" in tw_config


def test_css_variables_use_vd_prefix():
    css_vars = default_theme.to_css_variables()
    assert "--vd-color-primary:" in css_vars
    assert "--vd-color-background:" in css_vars
    assert "--vd-color-surface:" in css_vars
    assert "--vd-color-border:" in css_vars
    assert "--vd-radius-md:" in css_vars
    assert "--vd-space-md:" in css_vars
    assert "--vd-shadow-sm:" in css_vars
    assert "--vd-font-sans:" in css_vars
    assert "--vd-motion-fast:" in css_vars


def test_light_and_dark_mode_vars():
    css_vars = default_theme.to_css_variables()
    assert ":root {" in css_vars
    assert ".dark {" in css_vars


def test_spacing_tokens():
    spacing = ThemeSpacing()
    assert spacing.xs == "0.25rem"
    assert spacing.sm == "0.5rem"
    assert spacing.md == "0.75rem"
    assert spacing.lg == "1rem"
    assert spacing.xl == "1.5rem"
    assert spacing.xxl == "2rem"


def test_shadow_tokens():
    shadows = ThemeShadows()
    assert "0 1px 2px" in shadows.sm
    assert "0 1px 3px" in shadows.md


def test_create_theme():
    theme = create_theme(primary="#635BFF", font="Inter")
    assert theme.colors.primary == "#635BFF"
    assert "Inter" in theme.typography.font_family


def test_set_theme():
    original_theme = default_theme
    try:
        new_theme = Theme(mode="light")
        set_theme(new_theme)

        from voodoo.ui.styles import theme as theme_module

        assert theme_module.default_theme.mode == "light"
    finally:
        set_theme(original_theme)


def test_default_palette_emits_tailwind_compatible_steps():
    css_vars = Theme().to_css_variables()
    assert "--vd-color-violet-50: oklch(" in css_vars
    assert "--vd-color-violet-500: oklch(" in css_vars
    assert "--vd-color-violet-950: oklch(" in css_vars
    assert color("violet", 500) == "var(--vd-color-violet-500)"


def test_custom_palette_extends_defaults_and_exports_to_tailwind():
    theme = create_theme(palette={"brand": {50: "#f5f3ff", 500: "#7c3aed"}})
    assert theme.palette.scales["brand"][500] == "#7c3aed"
    assert "zinc" in theme.palette.scales

    css_vars = theme.to_css_variables()
    assert "--vd-color-brand-500: #7c3aed;" in css_vars

    tailwind = theme.to_tailwind_config()
    assert '"brand"' in tailwind
    assert '"500": "var(--vd-color-brand-500)"' in tailwind


def test_palette_rejects_nonstandard_steps():
    with pytest.raises(ValueError, match="invalid palette step"):
        ThemePalette(scales={"brand": {550: "#7c3aed"}})


def test_palette_rejects_values_that_can_escape_css_declarations():
    with pytest.raises(ValueError, match="invalid CSS color value"):
        ThemePalette(scales={"brand": {500: "red; display: none"}})
