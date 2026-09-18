"""Tests for Priority 2: Complete Forms components."""

import pytest

from voodoo.adapters import TailwindAdapter, VoodooCSSAdapter
from voodoo.ui import set_style_adapter
from voodoo.ui.forms_extended import (
    Autocomplete,
    CheckboxInput,
    FormError,
    FormValidationSummary,
    OTPInput,
    RadioInput,
    RangeSlider,
)
from voodoo.ui.styles import current_adapter


@pytest.fixture(params=[VoodooCSSAdapter, TailwindAdapter])
def adapter(request):
    original = current_adapter()
    set_style_adapter(request.param())
    yield request.param
    set_style_adapter(original)


# ── OTP Input ───────────────────────────────────────────────────────────────


def test_otp_input_renders_correct_number_of_fields(adapter):
    html = OTPInput(name="code", length=6, label="Verification code").render()
    assert "Verification code" in html
    assert html.count("vd-otp-field") == 6


def test_otp_input_masked(adapter):
    html = OTPInput(name="code", length=4, mask=True).render()
    assert 'type="password"' in html


def test_otp_input_custom_length(adapter):
    html = OTPInput(name="code", length=8).render()
    assert html.count("vd-otp-field") == 8


def test_otp_input_with_event(adapter):
    html = OTPInput(name="code", length=4, on_complete=lambda v: v).render()
    assert "data-vd-event-complete" in html


def test_otp_input_disabled(adapter):
    html = OTPInput(name="code", length=4, disabled=True).render()
    assert "disabled" in html


# ── Range Slider ────────────────────────────────────────────────────────────


def test_range_slider_renders(adapter):
    html = RangeSlider(name="price", min_value=0, max_value=100, label="Price range").render()
    assert "Price range" in html
    assert 'type="range"' in html


def test_range_slider_shows_values(adapter):
    html = RangeSlider(name="x", min_value=20, max_value=80, minimum=0, maximum=100).render()
    assert "20" in html
    assert "80" in html


def test_range_slider_with_event(adapter):
    html = RangeSlider(
        name="x", min_value=0, max_value=100,
        on_change=lambda v: v,
    ).render()
    assert "data-vd-event-input" in html


# ── Autocomplete ────────────────────────────────────────────────────────────


def test_autocomplete_renders(adapter):
    html = Autocomplete(
        name="fruit",
        suggestions=["Apple", "Banana", "Cherry"],
        label="Fruit",
    ).render()
    assert 'role="combobox"' in html
    assert 'aria-autocomplete="list"' in html
    assert "Apple" in html
    assert "Banana" in html
    assert "Cherry" in html
    assert "Fruit" in html


def test_autocomplete_custom_placeholder(adapter):
    html = Autocomplete(
        name="f",
        suggestions=["A"],
        placeholder="Search fruits…",
    ).render()
    assert "Search fruits…" in html


def test_autocomplete_with_event(adapter):
    html = Autocomplete(
        name="f",
        suggestions=["A", "B"],
        on_select=lambda v: v,
    ).render()
    assert "data-vd-event-select" in html


def test_autocomplete_options_have_correct_role(adapter):
    html = Autocomplete(name="f", suggestions=["A", "B"]).render()
    assert 'role="option"' in html


# ── Form Validation Summary ─────────────────────────────────────────────────


def test_form_validation_summary_renders_errors(adapter):
    html = FormValidationSummary(
        errors=[
            FormError("Email is required", field_id="email"),
            FormError("Password too short", field_id="password"),
        ],
    ).render()
    assert 'role="alert"' in html
    assert 'aria-live="assertive"' in html
    assert "Email is required" in html
    assert "Password too short" in html


def test_form_validation_summary_empty(adapter):
    html = FormValidationSummary(errors=[]).render()
    assert "hidden" in html or html.strip() == ""


def test_form_validation_summary_custom_title(adapter):
    html = FormValidationSummary(
        errors=[FormError("err", field_id="x")],
        title="Oops!",
    ).render()
    assert "Oops!" in html


# ── Checkbox Input ──────────────────────────────────────────────────────────


def test_checkbox_input_renders(adapter):
    html = CheckboxInput(label="Accept terms").render()
    assert 'role="checkbox"' in html
    assert 'aria-checked="false"' in html
    assert "Accept terms" in html


def test_checkbox_input_checked(adapter):
    html = CheckboxInput(label="On", checked=True).render()
    assert 'aria-checked="true"' in html


def test_checkbox_input_indeterminate(adapter):
    html = CheckboxInput(label="Partial", indeterminate=True).render()
    assert 'aria-checked="mixed"' in html


def test_checkbox_input_with_description(adapter):
    html = CheckboxInput(
        label="Subscribe",
        description="Get weekly emails",
    ).render()
    assert "Subscribe" in html
    assert "Get weekly emails" in html


def test_checkbox_input_disabled(adapter):
    html = CheckboxInput(label="X", disabled=True).render()
    assert "disabled" in html


# ── Radio Input ─────────────────────────────────────────────────────────────


def test_radio_input_renders(adapter):
    html = RadioInput(label="Option A", value="a", name="choice").render()
    assert 'type="radio"' in html
    assert "Option A" in html


def test_radio_input_checked(adapter):
    html = RadioInput(label="Selected", value="s", name="x", checked=True).render()
    assert 'checked' in html


def test_radio_input_with_description(adapter):
    html = RadioInput(
        label="Pro",
        value="pro",
        name="plan",
        description="$9/month",
    ).render()
    assert "Pro" in html
    assert "$9/month" in html


def test_radio_input_disabled(adapter):
    html = RadioInput(label="X", value="x", name="y", disabled=True).render()
    assert "disabled" in html
