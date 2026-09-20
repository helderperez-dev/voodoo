"""Design system tests — Sprint 15.

Pin the Voodoo CSS adapter's layout parity, full stylesheet coverage, and the
light/dark/system theme mode plumbing introduced in Sprint 15. These tests
ensure the default (zero-config) render path produces world-class, semantic
output without hardcoded Tailwind utility classes.
"""

from __future__ import annotations

import pytest

from voodoo.adapters import VoodooCSSAdapter
from voodoo.adapters.voodoo_css import generate_component_css
from voodoo.ui import (
    Badge,
    Button,
    Card,
    Container,
    Flex,
    Grid,
    Heading,
    Page,
    Stack,
    Text,
    set_style_adapter,
)
from voodoo.ui.rendering import _get_client_js, render_page
from voodoo.ui.styles import current_adapter
from voodoo.ui.styles.theme import Theme, set_theme

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def voodoo_css_adapter():
    """Use VoodooCSSAdapter (the default) for these tests."""
    original = current_adapter()
    set_style_adapter(VoodooCSSAdapter())
    yield
    set_style_adapter(original)


@pytest.fixture(autouse=True)
def _restore_theme():
    """Restore the global default theme after each test (no cross-test leak)."""
    from voodoo.ui.styles.theme import default_theme

    original = default_theme
    yield
    set_theme(original)


# ---------------------------------------------------------------------------
# Layout parity — Flex / Grid / Container / Page / Stack
# ---------------------------------------------------------------------------


def test_flex_layout_classes(voodoo_css_adapter):
    flex = Flex(
        "a",
        "b",
        direction="col",
        justify="center",
        items="center",
        wrap="wrap",
        gap="lg",
    )
    html = flex.render()
    for cls in (
        "vd-flex",
        "vd-flex--col",
        "vd-flex--justify-center",
        "vd-flex--items-center",
        "vd-flex--wrap",
        "vd-flex--gap-lg",
    ):
        assert cls in html


def test_grid_layout_classes(voodoo_css_adapter):
    grid = Grid("a", "b", "c", cols="3", gap="md")
    html = grid.render()
    assert "vd-grid" in html
    assert "vd-grid--cols-3" in html
    assert "vd-grid--gap-md" in html


def test_container_classes(voodoo_css_adapter):
    centered = Container("x", size="sm").render()
    assert "vd-container--sm" in centered
    assert "vd-container--centered" in centered

    uncentered = Container("x", centered=False).render()
    assert "vd-container--centered" not in uncentered


def test_page_classes(voodoo_css_adapter):
    padded = Page("x", size="lg", pad=True).render()
    assert "vd-page--lg" in padded
    assert "vd-page--pad" in padded

    flush = Page("x", pad=False).render()
    assert "vd-page--pad" not in flush


def test_stack_defaults_to_vertical(voodoo_css_adapter):
    stack = Stack("a", "b", gap="lg").render()
    assert "vd-flex--col" in stack
    assert "vd-flex--gap-lg" in stack


# ---------------------------------------------------------------------------
# Stylesheet coverage
# ---------------------------------------------------------------------------


def test_numeric_gap_uses_calc_not_spacing_token():
    css = generate_component_css(Theme())
    # Numeric gaps map to Tailwind's 4px base, not the (nonexistent) --vd-space-4.
    assert "calc(0.25rem * 4)" in css
    assert "var(--vd-space-4)" not in css
    # Named gaps resolve through the spacing scale.
    assert "var(--vd-space-lg)" in css


def test_generate_component_css_covers_components():
    css = generate_component_css(Theme())
    for expected in (
        "box-sizing: border-box",  # base reset
        ".vd-button",
        ".vd-button--primary",
        ".vd-card",
        ".vd-form",
        ".vd-input",
        ".vd-badge",
        ".vd-grid--cols-3",
        ".vd-container--centered",
        ".vd-page--pad",
        ".vd-list--unstyled",
        ".vd-list--ordered",
    ):
        assert expected in css


def test_scaffold_components_render_semantic(voodoo_css_adapter):
    """A mini showcase mirrors the generated scaffold and stays semantic."""
    page = Page(
        Stack(
            Heading("Hello", level=1),
            Text("Intro", tone="muted"),
            Flex(Button("Go", variant="primary"), gap="sm"),
            Grid(
                Badge("Feature", variant="secondary"),
                Card("Card body"),
                cols="3",
                gap="md",
            ),
            gap="lg",
        )
    )
    html = page.render()
    assert "vd-page" in html
    assert "vd-button--primary" in html
    assert "vd-badge--secondary" in html
    assert "vd-grid--cols-3" in html
    # No raw Tailwind utility classes leak through the default adapter.
    assert "space-y-" not in html
    assert "text-center" not in html


# ---------------------------------------------------------------------------
# Theme mode plumbing (light / dark / system)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mode", "expected_class"),
    [("dark", "dark"), ("light", "light"), ("system", "system")],
)
def test_render_page_html_class_respects_mode(voodoo_css_adapter, mode, expected_class):
    set_theme(Theme(mode=mode))
    html = render_page(Text("hi"))
    assert f'class="{expected_class}"' in html
    # No duplicated "dark dark" from the old forced html_class.
    assert 'class="dark dark"' not in html


def test_render_page_includes_theme_init_script(voodoo_css_adapter):
    html = render_page(Text("hi"))
    assert "voodoo_theme" in html
    assert "prefers-color-scheme" in html
    assert 'document.documentElement.classList.toggle("dark"' in html


def test_client_js_exposes_set_theme():
    js = _get_client_js()
    assert "setTheme" in js
    assert "voodoo_theme" in js
