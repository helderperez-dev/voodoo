from voodoo.ui.styles.theme import Theme, create_theme
from voodoo.ui.styles.theme_contract import generate_design_system_theme_css


def test_design_system_3_keeps_approved_default_palette() -> None:
    css = generate_design_system_theme_css(Theme())

    assert css.count("--vd-brand: #7c3aed;") == 2
    assert "--vd-canvas: #ffffff;" in css
    assert "--vd-panel: #ffffff;" in css
    assert "--vd-line: #e8e8ed;" in css
    assert "--vd-ink: #111118;" in css
    assert "--vd-canvas: #09090f;" in css
    assert "--vd-panel: #101017;" in css
    assert "--vd-line: #252532;" in css
    assert "--vd-ink: #f7f7fb;" in css


def test_create_theme_primary_controls_ds3_brand_in_both_modes() -> None:
    css = generate_design_system_theme_css(create_theme(primary="#0ea5e9"))

    assert css.count("--vd-brand: #0ea5e9;") == 2


def test_create_theme_secondary_can_control_ds3_brand() -> None:
    css = generate_design_system_theme_css(create_theme(secondary="#ec4899"))

    assert css.count("--vd-brand: #ec4899;") == 2


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
    css = generate_design_system_theme_css(theme)

    light, dark = css.split("\n\n.dark", maxsplit=1)
    assert "--vd-panel: #fff7ed;" in light
    assert "--vd-panel: #101017;" in dark
