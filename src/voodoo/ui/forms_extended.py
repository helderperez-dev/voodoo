"""Priority 2 — Complete Forms.

OTP input, range slider, standalone autocomplete, and form-level
validation summary.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from voodoo.ui.component import Component
from voodoo.ui.controls import _control_id
from voodoo.ui.events import bind_event
from voodoo.ui.interactive import Input

EventHandler = Callable[..., Any] | str


# ── OTPInput ─────────────────────────────────────────────────────────────────


class OTPInput(Component):
    """One-time password / verification code input with auto-advance.

    Renders individual character fields that advance focus automatically.
    Supports paste from clipboard and configurable length.

    Example::

        OTPInput(
            name="code",
            length=6,
            label="Verification code",
            on_complete=verify_code,
        )
    """

    style = "otp-input"

    def __init__(
        self,
        *,
        name: str = "otp",
        length: int = 6,
        value: str = "",
        label: str = "Verification code",
        on_change: EventHandler | None = None,
        on_complete: EventHandler | None = None,
        disabled: bool = False,
        mask: bool = False,
        **kwargs: Any,
    ) -> None:
        if length < 1 or length > 12:
            raise ValueError("OTPInput length must be between 1 and 12")
        super().__init__(**kwargs)
        self.props = {"length": length, "mask": mask}

        attrs: dict[str, Any] = {
            "data_vd_otp": True,
            "data_vd_otp_length": str(length),
            "data_vd_otp_name": name,
        }
        if on_change is not None:
            attrs["data_vd_event_change"] = bind_event(on_change)
        if on_complete is not None:
            attrs["data_vd_event_complete"] = bind_event(on_complete)
        self.attrs.update(attrs)

        fields: list[Component] = []
        for i in range(length):
            char_value = value[i] if i < len(value) else ""
            field = _OTPField(
                id=f"{self.id or _control_id('otp')}-{i}",
                type="text" if not mask else "password",
                inputmode="numeric",
                maxlength="1",
                name=f"{name}_{i}",
                value=char_value,
                aria_label=f"Digit {i + 1} of {length}",
                autocomplete="one-time-code" if i == 0 else "off",
                data_vd_otp_field=True,
                data_vd_otp_index=str(i),
                disabled=disabled,
            )
            fields.append(field)

        label_component = _OTPLabel(label, id=f"{self.id or _control_id('otp')}-label")
        self.children = (label_component, _OTPFields(*fields))


class _OTPLabel(Component):
    tag = "label"
    style = "otp-input.label"
    auto_id = False


class _OTPFields(Component):
    style = "otp-input.fields"
    auto_id = False


class _OTPField(Component):
    tag = "input"
    style = "otp-input.field"
    auto_id = False


# ── RangeSlider ──────────────────────────────────────────────────────────────


class RangeSlider(Component):
    """Dual-thumb range slider for selecting a value span.

    Renders two native range inputs stacked for selecting a minimum and
    maximum value. The visual track is styled by the CSS adapter.

    Example::

        RangeSlider(
            name="price",
            min_value=10,
            max_value=90,
            minimum=0,
            maximum=100,
            step=5,
            label="Price range",
            on_change=filter_by_price,
        )
    """

    style = "range-slider"

    def __init__(
        self,
        *,
        name: str,
        min_value: int | float = 0,
        max_value: int | float = 100,
        minimum: int | float = 0,
        maximum: int | float = 100,
        step: int | float = 1,
        label: str | None = None,
        min_label: str | None = None,
        max_label: str | None = None,
        on_change: EventHandler | None = None,
        disabled: bool = False,
        **kwargs: Any,
    ) -> None:
        if maximum <= minimum:
            raise ValueError("RangeSlider maximum must be greater than minimum")
        if min_value < minimum or max_value > maximum:
            raise ValueError("RangeSlider values must be within bounds")
        if min_value > max_value:
            raise ValueError("RangeSlider min_value must not exceed max_value")
        if step <= 0:
            raise ValueError("RangeSlider step must be greater than zero")

        slider_id = _control_id("range-slider")
        track_id = f"{slider_id}-track"
        binding = bind_event(on_change) if on_change is not None else None

        min_field = Input(
            id=f"{slider_id}-min",
            type="range",
            name=f"{name}_min",
            value=min_value,
            min=minimum,
            max=maximum,
            step=step,
            aria_label=min_label or f"Minimum {label or name}",
            aria_describedby=track_id,
            on_input=binding,
            data_vd_range_min=True,
            disabled=disabled,
        )
        max_field = Input(
            id=f"{slider_id}-max",
            type="range",
            name=f"{name}_max",
            value=max_value,
            min=minimum,
            max=maximum,
            step=step,
            aria_label=max_label or f"Maximum {label or name}",
            aria_describedby=track_id,
            on_input=binding,
            data_vd_range_max=True,
            disabled=disabled,
        )

        children: list[Any] = [
            _RangeLabel(label, class_="vd-range-slider-label") if label else None,
            _RangeTrack(
                _RangeMinOutput(str(min_value), id=f"{slider_id}-min-output"),
                _RangeMaxOutput(str(max_value), id=f"{slider_id}-max-output"),
                id=track_id,
            ),
            _RangeFields(min_field, max_field),
        ]
        children = [c for c in children if c is not None]
        super().__init__(*children, data_vd_range_slider=True, **kwargs)
        self.props = {"minimum": minimum, "maximum": maximum, "step": step}


class _RangeLabel(Component):
    tag = "span"
    style = "range-slider.label"
    auto_id = False


class _RangeTrack(Component):
    style = "range-slider.track"
    auto_id = False


class _RangeMinOutput(Component):
    tag = "output"
    style = "range-slider.output"
    auto_id = False


class _RangeMaxOutput(Component):
    tag = "output"
    style = "range-slider.output"
    auto_id = False


class _RangeFields(Component):
    style = "range-slider.fields"
    auto_id = False


# ── Autocomplete ─────────────────────────────────────────────────────────────


class Autocomplete(Component):
    """Free-text input with filtered suggestion dropdown.

    Unlike :class:`Combobox` (which is a select replacement), ``Autocomplete``
    allows arbitrary text entry and shows matching suggestions as the user types.

    Example::

        Autocomplete(
            name="country",
            suggestions=[
                "United States",
                "United Kingdom",
                "Canada",
                "Australia",
            ],
            placeholder="Start typing a country…",
            label="Country",
        )
    """

    style = "autocomplete"

    def __init__(
        self,
        *,
        name: str,
        suggestions: Sequence[str] = (),
        value: str = "",
        placeholder: str = "Start typing…",
        label: str | None = None,
        empty_text: str = "No suggestions.",
        on_change: EventHandler | None = None,
        on_select: EventHandler | None = None,
        disabled: bool = False,
        **kwargs: Any,
    ) -> None:
        root_id = kwargs.get("id") or _control_id("autocomplete")
        input_id = f"{root_id}-input"
        listbox_id = f"{root_id}-listbox"

        attrs: dict[str, Any] = {
            "id": root_id,
            "data_vd_autocomplete": True,
        }
        if on_select is not None:
            attrs["data_vd_event_select"] = bind_event(on_select)
        super().__init__(**attrs, **kwargs)

        field = Input(
            id=input_id,
            type="text",
            name=name,
            value=value,
            placeholder=placeholder,
            autocomplete="off",
            role="combobox",
            aria_label=label or name.replace("_", " ").title(),
            aria_autocomplete="list",
            aria_controls=listbox_id,
            aria_expanded="false",
            on_input=on_change,
            data_vd_autocomplete_input=True,
            disabled=disabled,
        )

        options = tuple(
            _AutocompleteOption(
                suggestion,
                id=f"{listbox_id}-option-{i}",
                role="option",
                aria_selected="false",
                data_vd_autocomplete_option=True,
                data_vd_value=suggestion,
            )
            for i, suggestion in enumerate(suggestions)
        )

        listbox = _AutocompleteList(
            *options,

            id=listbox_id,
            role="listbox",
            hidden=True,
            data_vd_autocomplete_list=True,
        )

        self.children = (field, listbox)


class _AutocompleteList(Component):
    style = "autocomplete.list"
    auto_id = False


class _AutocompleteOption(Component):
    tag = "button"
    style = "autocomplete.option"
    auto_id = False

    def __init__(self, *children: Any, **kwargs: Any) -> None:
        super().__init__(*children, type="button", tabindex="-1", **kwargs)


class _AutocompleteEmpty(Component):
    style = "autocomplete.empty"
    auto_id = False


# ── FormValidationSummary ────────────────────────────────────────────────────


class FormValidationSummary(Component):
    """Aggregated form-level validation error display.

    Collects validation errors from multiple fields and renders them as a
    single accessible error summary with anchor links to the offending fields.

    Example::

        FormValidationSummary(
            errors=[
                FormError("Email is required", field_id="email-input"),
                FormError("Password must be at least 8 characters", field_id="password-input"),
            ],
        )
    """

    style = "form-validation-summary"

    def __init__(
        self,
        *,
        errors: Sequence[FormError] | None = None,
        title: str | None = None,
        **kwargs: Any,
    ) -> None:
        items = list(errors or [])
        if not items:
            super().__init__(hidden=True, **kwargs)
            return

        heading = _ValidationHeading(
            title or f"{len(items)} error{'s' if len(items) != 1 else ''} found",
        )
        error_list = _ValidationList(
            *items,
            role="list",
        )
        super().__init__(
            heading,
            error_list,
            role="alert",
            aria_live="assertive",
            data_vd_validation_summary=True,
            **kwargs,
        )


class _ValidationHeading(Component):
    tag = "h2"
    style = "form-validation-summary.heading"
    auto_id = False


class _ValidationList(Component):
    tag = "ul"
    style = "form-validation-summary.list"
    auto_id = False


class FormError(Component):
    """A single validation error with an optional link to the source field."""

    tag = "li"
    style = "form-validation-summary.error"

    def __init__(
        self,
        message: str,
        *,
        field_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        if field_id:
            link = _ErrorLink(
                message,
                href=f"#{field_id}",
                data_vd_error_anchor=True,
            )
            super().__init__(link, **kwargs)
        else:
            super().__init__(message, **kwargs)


class _ErrorLink(Component):
    tag = "a"
    style = "form-validation-summary.link"
    auto_id = False


# ── Checkbox (standalone enhanced) ──────────────────────────────────────────


class CheckboxInput(Component):
    """Enhanced checkbox with label, description, and indeterminate support.

    Example::

        CheckboxInput(
            label="Accept terms",
            description="You must accept the terms to continue.",
            checked=False,
            required=True,
        )
    """

    style = "checkbox-input"

    def __init__(
        self,
        *,
        label: str,
        description: str | None = None,
        name: str | None = None,
        checked: bool = False,
        indeterminate: bool = False,
        disabled: bool = False,
        required: bool = False,
        on_change: EventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        field_id = _control_id("checkbox")
        attrs: dict[str, Any] = {
            "id": field_id,
            "type": "checkbox",
            "role": "checkbox",

            "name": name,
        }
        if checked:
            attrs["checked"] = True
        if indeterminate:
            attrs["data_vd_indeterminate"] = True
        if disabled:
            attrs["disabled"] = True
            attrs["aria_disabled"] = "true"
        if required:
            attrs["required"] = True
        if on_change is not None:
            attrs["data_vd_event_change"] = bind_event(on_change)

        input_el = Input(**attrs)
        copy_children: list[Any] = [
            Component(label, class_="vd-checkbox-label"),
        ]
        if description:
            copy_children.append(
                Component(description, class_="vd-checkbox-description")
            )
        super().__init__(
            input_el,
            _CheckboxCopy(*copy_children, for_=field_id),
            data_vd_checkbox=True,
            **kwargs,
        )



class _CheckboxCopy(Component):
    tag = "label"
    style = "checkbox-input.copy"
    auto_id = False


# ── RadioInput (standalone enhanced) ────────────────────────────────────────


class RadioInput(Component):
    """Enhanced radio button with label and description."""

    style = "radio-input"

    def __init__(
        self,
        *,
        label: str,
        description: str | None = None,
        name: str | None = None,
        value: str = "",
        checked: bool = False,
        disabled: bool = False,
        on_change: EventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        field_id = _control_id("radio")
        attrs: dict[str, Any] = {
            "id": field_id,
            "type": "radio",
            "name": name,
            "value": value,
        }
        if checked:
            attrs["checked"] = True
        if disabled:
            attrs["disabled"] = True
            attrs["aria_disabled"] = "true"
        if on_change is not None:
            attrs["data_vd_event_change"] = bind_event(on_change)

        input_el = Input(**attrs)
        copy_children: list[Any] = [
            Component(label, class_="vd-radio-label"),
        ]
        if description:

        super().__init__(
            input_el,
            _RadioCopy(*copy_children, for_=field_id),
            data_vd_radio=True,
            **kwargs,
        )
        self.props = {"checked": checked, "disabled": disabled}


class _RadioCopy(Component):
    tag = "label"
    style = "radio-input.copy"
    auto_id = False
