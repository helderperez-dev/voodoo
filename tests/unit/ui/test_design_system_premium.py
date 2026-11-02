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
from voodoo.ui.styles.theme_contract import generate_design_system_theme_css


def test_design_system_has_no_literal_brand_color() -> None:
    css = generate_design_system_css(default_theme)
    full = render_page(Page(Button("Action", variant="primary")))

    for literal in ("#7c3aed", "#8b5cf6", "#6d28d9", "#5b21b6", "#6366f1"):
        assert literal not in css.lower()
        assert literal not in full.lower()
    assert "--vd-shadow-card:" in css
    assert ".dark {" in css


def test_default_theme_is_neutral_monochrome_in_both_modes() -> None:
    css = generate_design_system_theme_css(default_theme)
    light, dark = css.split("\n\n.dark", maxsplit=1)

    assert "--vd-brand: #18181B;" in light
    assert "--vd-brand: #FAFAFA;" in dark
    assert "--vd-canvas: #FFFFFF;" in light
    assert "--vd-canvas: #09090B;" in dark


def test_primary_actions_are_flat_theme_driven_fills() -> None:
    css = generate_design_system_css(default_theme)

    assert ".vd-button--primary" in css
    assert "background: var(--vd-brand);" in css
    assert "linear-gradient(180deg, var(--vd-brand-highlight)" not in css


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

    assert "Voodoo Design System 4" in html
    assert "--vd-brand:" in html
    assert "#7c3aed" not in html.lower()
    assert "vd-button--primary" in html
    assert "vd-card" in html


def test_design_system_is_the_final_framework_visual_layer() -> None:
    html = render_page(Page(Button("Action", variant="primary")))

    product = html.index("/* Reusable product patterns */")
    extended = html.index("/* Extended UI components */")
    system = html.index("/* Canonical Voodoo runtime/system concepts */")
    convergence = html.index("/* Voodoo Design System 4 — final convergence layer */")
    project = html.index("/* Project theme customization — always wins */")

    assert product < extended < system < convergence < project


def test_design_system_converges_extended_component_families() -> None:
    css = generate_design_system_css(default_theme)

    for selector in (
        ".vd-command-panel",
        ".vd-context-menu-panel",
        ".vd-search-input",
        ".vd-drop-zone",
        ".vd-enhanced-data-table-container",
        ".vd-toolbar",
        ".vd-pagination",
        ".vd-step-indicator",
        ".vd-form-validation-summary",
        ".vd-world-entity-inspector",
    ):
        assert selector in css
