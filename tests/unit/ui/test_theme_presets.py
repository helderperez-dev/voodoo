"""Theme preset tests.

Pin the preset resolution order, the JSON round-trip, and the ember-paper
built-in's warm palette (including light/dark secondary accent overrides).
"""

from __future__ import annotations

import json

import pytest

from voodoo.ui.styles.presets import (
    ThemePreset,
    list_presets,
    resolve_theme,
)
from voodoo.ui.styles.theme import set_theme


@pytest.fixture(autouse=True)
def _restore_theme():
    """Restore the global default theme after each test (no cross-test leak)."""
    from voodoo.ui.styles.theme import default_theme

    original = default_theme
    yield
    set_theme(original)


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def test_list_presets_includes_builtins():
    names = [p["name"] for p in list_presets()]
    assert "default" in names
    assert "ember-paper" in names


def test_resolve_default_origin():
    source = resolve_theme("default")
    assert source.origin == "builtin:default"
    assert source.theme.mode == "dark"


def test_resolve_unknown_raises():
    from voodoo.core.errors import ConfigurationError

    with pytest.raises(ConfigurationError):
        resolve_theme("does-not-exist-xyz")


# ---------------------------------------------------------------------------
# ember-paper built-in
# ---------------------------------------------------------------------------


def test_ember_paper_accent_switches_light_dark():
    source = resolve_theme("ember-paper")
    assert source.origin == "builtin:ember-paper"
    css = source.theme.to_css_variables()

    # Dark mode uses the amber accent; light mode uses the burnt ember.
    assert "--vd-color-secondary: #E8A33D;" in css
    assert "--vd-color-secondary: #B45309;" in css
    # On-color contrast inverts with the accent brightness.
    assert "--vd-color-on-secondary: #0F0D0B;" in css
    assert "--vd-color-on-secondary: #FFFFFF;" in css


def test_ember_paper_editorial_typography():
    source = resolve_theme("ember-paper")
    css = source.theme.to_css_variables()
    assert "Fraunces" in css
    assert "IBM Plex Mono" in css
    assert "Schibsted Grotesk" in css
    # The display face is exposed as its own token.
    assert "--vd-font-display:" in css


def test_ember_paper_extra_glow_token():
    source = resolve_theme("ember-paper")
    css = source.theme.to_css_variables()
    assert "--vd-glow:" in css


# ---------------------------------------------------------------------------
# JSON round-trip
# ---------------------------------------------------------------------------


def test_preset_round_trips_through_json():
    preset = resolve_theme("ember-paper")
    data = ThemePreset(
        name="ember-paper",
        description="round trip",
        theme=preset.theme,
    )
    raw = data.model_dump_json()
    restored = ThemePreset.model_validate_json(raw)
    assert restored.theme == preset.theme
    # The JSON is plain and editor-friendly (no non-serializable values).
    parsed = json.loads(raw)
    assert parsed["theme"]["mode"] == "dark"
    assert parsed["theme"]["colors"]["secondary"] == "#E8A33D"
