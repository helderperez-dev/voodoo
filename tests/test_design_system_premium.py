"""Acceptance gates for Voodoo's default visual language."""

from voodoo.ui import (
    Badge,
    Button,
    Card,
    Container,
    Grid,
    Heading,
    Input,
    Navbar,
    NavLink,
    Page,
    Text,
    ThemeToggle,
)
from voodoo.ui.rendering import render_page
from voodoo.ui.styles.system import generate_design_system_css
from voodoo.ui.styles.theme import default_theme


def test_design_system_exposes_voodoo_brand_and_light_dark_surfaces() -> None:
    css = generate_design_system_css(default_theme)

    assert "--vd-brand: #7c3aed" in css
    assert "--vd-canvas: #ffffff" in css
    assert ".dark {" in css
    assert "--vd-canvas: #09090f" in css
    assert "--vd-shadow-card:" in css
    assert "--vd-focus-ring:" in css


def test_primary_actions_use_voodoo_brand_not_monochrome_fill() -> None:
    css = generate_design_system_css(default_theme)

    assert ".vd-button--primary" in css
    assert (
        "background: linear-gradient(180deg, #8b5cf6 0%, var(--vd-brand) 100%)"
        in css
    )
    assert "box-shadow: var(--vd-shadow-brand)" in css


def test_default_components_render_semantic_design_system_classes() -> None:
    ui = Page(
        Container(
            Grid(
                Card(
                    Heading("Build real things", level=1),
                    Text("Effortlessly.", tone="muted"),
                    Button("Get Started", variant="primary"),
                    Badge("Runtime", variant="primary"),
                    Input(placeholder="Search"),
                ),
                cols="1",
                gap="lg",
            )
        )
    )

    html = ui.render()
    assert "vd-page" in html
    assert "vd-container" in html
    assert "vd-grid" in html
    assert "vd-card" in html
    assert "vd-heading" in html
    assert "vd-button--primary" in html
    assert "vd-badge--primary" in html
    assert "vd-input" in html


def test_navigation_and_theme_controls_use_premium_chrome() -> None:
    ui = Navbar(
        NavLink("Home", href="/", active=True),
        NavLink("Components", href="/components"),
        ThemeToggle(),
    )
    html = ui.render()

    assert "vd-navbar" in html
    assert "vd-navbar--sticky" in html
    assert "vd-nav-link--active" in html
    assert "vd-theme-toggle" in html


def test_full_page_includes_design_system_layer() -> None:
    html = render_page(
        Page(
            Container(
                Card(
                    Heading("Hello, Voodoo", level=1),
                    Text("One Runtime. One local Store.", tone="muted"),
                    Button("Get Started", variant="primary"),
                )
            )
        )
    )

    assert "Voodoo Design System 3" in html
    assert "--vd-brand: #7c3aed" in html
    assert "vd-button--primary" in html
    assert "vd-card" in html
