"""Chrome component tests.

Pin the page-level composite primitives (navbar, hero, code block, stats, CTA
band, etc.), their semantic ``vd-*`` classes, and their generated CSS.
"""

from __future__ import annotations

import pytest

from voodoo.adapters import VoodooCSSAdapter
from voodoo.adapters.voodoo_css import generate_component_css
from voodoo.ui import (
    BackLink,
    Brand,
    Chip,
    CodeBlock,
    CTABand,
    Eyebrow,
    FeatureCard,
    Hero,
    LinkArrow,
    Navbar,
    NavLink,
    PageHero,
    Stat,
    Stats,
    ThemeToggle,
    set_style_adapter,
)
from voodoo.ui.styles import current_adapter
from voodoo.ui.styles.theme import Theme, set_theme


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
# Component rendering
# ---------------------------------------------------------------------------


def test_navbar_and_navlink(voodoo_css_adapter):
    html = Navbar(
        Brand("Voodoo"),
        NavLink("Home", href="/", active=True),
        NavLink("Docs", href="/docs"),
    ).render()
    assert "vd-navbar" in html
    assert "vd-navbar--sticky" in html
    assert "vd-brand" in html
    assert "vd-nav-link" in html
    assert "vd-nav-link--active" in html


def test_navbar_not_sticky(voodoo_css_adapter):
    html = Navbar(Brand("V"), sticky=False).render()
    assert "vd-navbar" in html
    assert "vd-navbar--sticky" not in html


def test_theme_toggle_switches_dark_class(voodoo_css_adapter):
    html = ThemeToggle().render()
    assert "vd-theme-toggle" in html
    assert "classList.toggle('dark')" in html
    assert "voodoo_theme" in html
    assert "vd-theme-toggle-sun" in html
    assert "vd-theme-toggle-moon" in html


def test_hero_pagehero_eyebrow_chip(voodoo_css_adapter):
    assert "vd-hero" in Hero("x").render()
    assert "vd-page-hero" in PageHero("x").render()
    assert "vd-eyebrow" in Eyebrow("New").render()
    assert "vd-chip" in Chip("beta").render()


def test_codeblock_escapes_html(voodoo_css_adapter):
    html = CodeBlock("<script>alert(1)</script>", language="html").render()
    assert "vd-code-block" in html
    assert "&lt;script&gt;" in html
    assert "<script>" not in html
    assert 'data-language="html"' in html


def test_stats_and_stat(voodoo_css_adapter):
    html = Stats(Stat("99.99%", "Uptime"), Stat("12ms", "Latency"), cols=2).render()
    assert "vd-stats" in html
    assert "vd-stats--cols-2" in html
    assert "vd-stat" in html
    assert "vd-stat-value" in html
    assert "vd-stat-label" in html
    assert "99.99%" in html


def test_cta_backlink_featurecard_linkarrow(voodoo_css_adapter):
    assert "vd-cta-band" in CTABand("x").render()
    assert "vd-back-link" in BackLink("Back", href="/").render()
    assert "vd-feature-card" in FeatureCard("x").render()
    assert "vd-link-arrow" in LinkArrow("More", href="/docs").render()


# ---------------------------------------------------------------------------
# CSS coverage
# ---------------------------------------------------------------------------


def test_chrome_css_generated():
    css = generate_component_css(Theme())
    for expected in (
        ".vd-navbar",
        ".vd-navbar--sticky",
        ".vd-nav-link",
        ".vd-nav-link--active",
        ".vd-brand",
        ".vd-theme-toggle",
        ".vd-hero",
        ".vd-page-hero",
        ".vd-eyebrow",
        ".vd-chip",
        ".vd-code-block",
        ".vd-stats",
        ".vd-stats--cols-3",
        ".vd-stat",
        ".vd-stat-value",
        ".vd-cta-band",
        ".vd-back-link",
        ".vd-feature-card",
        ".vd-link-arrow",
        "@keyframes vd-fade-up",
        "@keyframes vd-fade-in",
        "@keyframes vd-pulse",
        "prefers-reduced-motion",
    ):
        assert expected in css


def test_code_block_uses_code_tokens():
    css = generate_component_css(Theme())
    assert "var(--vd-code-background)" in css
    assert "var(--vd-code-border)" in css
    assert "var(--vd-code-text)" in css
    assert "var(--vd-font-mono)" in css


def test_secondary_tokens_used_in_chrome_and_buttons():
    css = generate_component_css(Theme())
    assert "var(--vd-color-secondary-soft)" in css
    assert "var(--vd-color-secondary-line)" in css
    assert "var(--vd-color-on-primary)" in css
    assert "var(--vd-color-on-secondary)" in css
