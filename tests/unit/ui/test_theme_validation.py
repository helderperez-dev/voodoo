"""Every shipped theme must be accessible; validation must be able to fail."""

import json

import pytest
from typer.testing import CliRunner

from voodoo.cli.theme import theme_app
from voodoo.ui.styles.presets import list_presets, resolve_theme
from voodoo.ui.styles.theme import Theme, create_theme
from voodoo.ui.styles.theme_validation import (
    contrast_ratio,
    ensure_contrast,
    validate_theme,
)

BUILTINS = [p["name"] for p in list_presets() if p["source"] == "builtin"]


def test_builtin_preset_set_is_complete() -> None:
    assert {"default", "ember-paper", "voodoo-purple"} <= set(BUILTINS)


@pytest.mark.parametrize("name", BUILTINS)
def test_every_builtin_preset_passes_contrast(name: str) -> None:
    theme = resolve_theme(name).theme

    assert [str(issue) for issue in validate_theme(theme)] == []


def test_validation_detects_low_contrast_text() -> None:
    theme = Theme()
    theme.colors.text_muted = "#222225"  # near the dark canvas

    issues = validate_theme(theme)

    assert any(i.mode == "dark" and i.foreground == "ink-muted" for i in issues)


def test_validation_detects_weak_accent_against_light_canvas() -> None:
    theme = create_theme(accent="#fde047")

    issues = validate_theme(theme)

    assert any(i.mode == "light" and i.foreground == "brand" for i in issues)


def test_non_hex_colors_are_reported_as_unverified_not_passed() -> None:
    theme = create_theme(accent="oklch(60% 0.2 250)")

    issues = validate_theme(theme)

    assert issues
    assert all(i.unverified for i in issues if i.foreground == "brand")


def test_contrast_ratio_matches_wcag_reference_values() -> None:
    assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0)
    assert contrast_ratio("#777777", "#ffffff") == pytest.approx(4.48, abs=0.01)
    assert contrast_ratio("red", "#ffffff") is None


def test_ensure_contrast_preserves_passing_colors_and_fixes_failing_ones() -> None:
    assert ensure_contrast("#111111", ("#ffffff",)) == "#111111"
    fixed = ensure_contrast("#0ea5e9", ("#ffffff", "#fafafa"))
    assert fixed != "#0ea5e9"
    ratio = contrast_ratio(fixed, "#fafafa")
    assert ratio is not None and ratio >= 3.0
    assert ensure_contrast("oklch(60% 0.2 250)", ("#ffffff",)) == ("oklch(60% 0.2 250)")


def test_cli_new_creates_valid_theme_that_resolves(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    created = runner.invoke(theme_app, ["new", "acme", "--accent", "#0ea5e9"])
    assert created.exit_code == 0, created.output

    data = json.loads((tmp_path / ".voodoo/theme/theme.json").read_text())
    assert data["name"] == "acme"
    assert data["theme"]["colors"]["accent"] == "#0ea5e9"
    assert data["theme"]["colors"]["light_accent"] != "#0ea5e9"

    validated = runner.invoke(theme_app, ["validate"])
    assert validated.exit_code == 0, validated.output
    assert resolve_theme(project_root=str(tmp_path)).theme.colors.accent == "#0ea5e9"


def test_cli_new_refuses_to_overwrite_without_force(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(theme_app, ["new", "acme"]).exit_code == 0

    again = runner.invoke(theme_app, ["new", "acme"])
    forced = runner.invoke(theme_app, ["new", "acme", "--force"])

    assert again.exit_code == 1
    assert forced.exit_code == 0


def test_cli_validate_fails_on_inaccessible_theme_and_emits_json(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    theme = Theme()
    theme.colors.light_text_muted = "#dddddd"
    from voodoo.cli.theme import _write_preset

    _write_preset(tmp_path / ".voodoo/theme", name="bad", theme=theme)

    result = runner.invoke(theme_app, ["validate", "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["valid"] is False
    assert any(i["mode"] == "light" for i in payload["issues"])
