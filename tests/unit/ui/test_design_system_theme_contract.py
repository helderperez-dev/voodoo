"""The Theme contract is the single, authoritative source of color tokens."""

from voodoo.ui.styles.theme import Theme, create_theme
from voodoo.ui.styles.theme_contract import (
    generate_design_system_theme_css,
    readable_on,
)


def _scopes(css: str) -> tuple[str, str]:
    light, dark = css.split("\n\n.dark", maxsplit=1)
    return light, dark


def test_default_theme_is_monochrome_without_brand_hue() -> None:
    light, dark = _scopes(generate_design_system_theme_css(Theme()))

    assert "--vd-brand: #18181B;" in light
    assert "--vd-on-brand: #FFFFFF;" in light
    assert "--vd-brand: #FAFAFA;" in dark
    assert "--vd-on-brand: #09090B;" in dark
    assert "#7c3aed" not in (light + dark).lower()


def test_default_theme_uses_its_own_surface_values() -> None:
    light, dark = _scopes(generate_design_system_theme_css(Theme()))

    assert "--vd-canvas: #FFFFFF;" in light
    assert "--vd-panel: #FAFAFA;" in light
    assert "--vd-line: #E4E4E7;" in light
    assert "--vd-ink: #18181B;" in light
    assert "--vd-canvas: #09090B;" in dark
    assert "--vd-panel: #18181B;" in dark
    assert "--vd-ink: #FAFAFA;" in dark


def test_accent_recolors_brand_in_both_modes() -> None:
    css = generate_design_system_theme_css(create_theme(accent="#0ea5e9"))

    assert css.count("--vd-brand: #0ea5e9;") == 2


def test_light_accent_applies_only_to_light_mode() -> None:
    theme = Theme()
    theme.colors.accent = "#0ea5e9"
    theme.colors.light_accent = "#0369a1"
    light, dark = _scopes(generate_design_system_theme_css(theme))

    assert "--vd-brand: #0369a1;" in light
    assert "--vd-brand: #0ea5e9;" in dark


def test_primary_without_accent_controls_brand() -> None:
    css = generate_design_system_theme_css(create_theme(primary="#111827"))

    assert css.count("--vd-brand: #111827;") == 2


def test_secondary_no_longer_implies_a_brand_color() -> None:
    css = generate_design_system_theme_css(create_theme(secondary="#ec4899"))

    assert "#ec4899" not in css


def test_on_brand_contrast_is_computed_for_accents() -> None:
    light_fill = generate_design_system_theme_css(create_theme(accent="#fde047"))
    dark_fill = generate_design_system_theme_css(create_theme(accent="#1e3a8a"))

    assert light_fill.count("--vd-on-brand: #000000;") == 2
    assert dark_fill.count("--vd-on-brand: #ffffff;") == 2


def test_explicit_on_accent_wins_over_computed_contrast() -> None:
    theme = create_theme(accent="#fde047")
    theme.colors.on_accent = "#111111"
    light, _ = _scopes(generate_design_system_theme_css(theme))

    assert "--vd-on-brand: #111111;" in light


def test_shared_theme_surface_overrides_apply_to_light_and_dark() -> None:
    theme = create_theme(
        background="#001122",
        surface="#112233",
        text="#fefefe",
        border="#334455",
    )
    css = generate_design_system_theme_css(theme)

    assert css.count("--vd-canvas: #001122;") == 2
    assert css.count("--vd-panel: #112233;") == 2
    assert css.count("--vd-ink: #fefefe;") == 2
    assert css.count("--vd-line: #334455;") == 2


def test_explicit_light_surface_override_wins_only_in_light_scope() -> None:
    theme = Theme()
    theme.colors.light_surface = "#fff7ed"
    light, dark = _scopes(generate_design_system_theme_css(theme))

    assert "--vd-panel: #fff7ed;" in light
    assert "--vd-panel: #18181B;" in dark


def test_value_equal_to_a_former_default_is_still_authoritative() -> None:
    theme = Theme()
    theme.colors.surface = "#18181B"
    theme.colors.light_surface = "#18181B"
    light, _ = _scopes(generate_design_system_theme_css(theme))

    assert "--vd-panel: #18181B;" in light


def test_status_colors_derive_every_variant_from_the_theme() -> None:
    theme = Theme()
    theme.colors.success = "#00aa55"
    theme.colors.danger = "#cc0033"
    css = generate_design_system_theme_css(theme)

    assert css.count("--vd-color-success: #00aa55;") == 2
    assert css.count("--vd-color-danger: #cc0033;") == 2
    for variant in ("soft", "line", "strong", "focus"):
        assert css.count(f"--vd-danger-{variant}:") == 2
    assert "--vd-on-danger: #ffffff;" in css


def test_readable_on_picks_highest_contrast_and_handles_non_hex() -> None:
    assert readable_on("#ffffff") == "#000000"
    assert readable_on("#000000") == "#ffffff"
    assert readable_on("#fff") == "#000000"
    assert readable_on("oklch(60% 0.2 250)", "#abcdef") == "#abcdef"
    assert readable_on("not-a-color") == "#ffffff"


def test_create_theme_seeds_with_equal_values_do_not_collide() -> None:
    theme = create_theme(background="#101010", surface="#101010", text="#eeeeee")

    assert theme.colors.background == theme.colors.surface == "#101010"
    assert theme.colors.light_background == theme.colors.light_surface == "#101010"
    assert theme.colors.text == theme.colors.light_text == "#eeeeee"
