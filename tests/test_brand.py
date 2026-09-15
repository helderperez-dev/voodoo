"""Tests for the theme-aware Brand component."""

import pytest

from voodoo.ui import Brand
from voodoo.ui.brand import BRAND_CSS
from voodoo.ui.rendering import render_page


def test_brand_preserves_child_based_api():
    html = Brand("Voodoo", href="/home").render()

    assert 'href="/home"' in html
    assert ">Voodoo</a>" in html
    assert "vd-brand-logo" not in html


def test_brand_renders_theme_specific_assets_without_generic_img_style():
    html = Brand(
        light="/logo-black.png",
        dark="/logo-white.png",
        alt="Voodoo",
        width=160,
        href="/",
    ).render()

    assert 'src="/logo-black.png"' in html
    assert 'src="/logo-white.png"' in html
    assert 'alt="Voodoo"' in html
    assert 'width="160"' in html
    assert "vd-brand-logo--light" in html
    assert "vd-brand-logo--dark" in html
    assert "vd-img" not in html


def test_brand_single_asset_is_shared_by_both_themes():
    html = Brand(light="/logo.svg", alt="Acme").render()

    assert html.count("<img") == 1
    assert 'src="/logo.svg"' in html
    assert "vd-brand-logo--light" not in html
    assert "vd-brand-logo--dark" not in html


def test_brand_rejects_children_in_image_mode():
    with pytest.raises(ValueError, match="cannot be combined"):
        Brand("Voodoo", light="/logo.svg")


def test_brand_css_switches_assets_and_removes_radius():
    assert "border-radius: 0 !important" in BRAND_CSS
    assert ".dark .vd-brand-logo--light { display: none; }" in BRAND_CSS
    assert ".dark .vd-brand-logo--dark { display: block; }" in BRAND_CSS


def test_render_page_includes_brand_css():
    html = render_page(Brand(light="/logo-black.png", dark="/logo-white.png"))

    assert "/* Brand asset switching */" in html
    assert ".vd-brand-logo--light" in html
    assert ".dark .vd-brand-logo--dark" in html
