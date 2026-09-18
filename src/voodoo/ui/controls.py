"""Advanced form controls with native-first browser behavior."""

from __future__ import annotations

import calendar as calendar_module
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import uuid4

from voodoo.ui.component import Component
from voodoo.ui.events import bind_event
from voodoo.ui.interactive import Button, Input

EventHandler = Callable[..., Any] | str


def _control_id(prefix: str) -> str:
    return f"vd-{prefix}-{uuid4().hex[:8]}"


class InputGroup(Component):
    """One input with optional leading and trailing content."""

    style = "input-group"

    def __init__(
        self,
        control: Component,
        *,
        leading: Any | None = None,
        trailing: Any | None = None,
        **kwargs: Any,
    ) -> None:
        if control.tag not in {"input", "select", "textarea"}:
            raise TypeError("InputGroup control must be an input, select, or textarea")
        children: list[Any] = []
        if leading is not None:
            children.append(_InputAdornment(leading, position="leading"))
        children.append(control)
        if trailing is not None:
            children.append(_InputAdornment(trailing, position="trailing"))
        super().__init__(*children, **kwargs)


class _InputAdornment(Component):
    tag = "span"
    style = "input-adornment"
    auto_id = False

    def __init__(self, *children: Any, position: str) -> None:
        super().__init__(*children)
        self.props = {"position": position}


class SearchInput(Component):
    """Search field with an optional clear action."""

    tag = "label"
    style = "search-input"

    def __init__(
        self,
        *,
        name: str = "search",
        value: str = "",
        placeholder: str = "Search",
        label: str = "Search",
        on_input: EventHandler | None = None,
        clearable: bool = True,
        **kwargs: Any,
    ) -> None:
        field = Input(
            type="search",
            name=name,
            value=value,
            placeholder=placeholder,
            aria_label=label,
            autocomplete="off",
            on_input=on_input,
            data_vd_search_field=True,
        )
        children: list[Any] = [
            _ControlGlyph("search"),
            field,
        ]
        if clearable:
            children.append(
                Button(
                    "Clear",
                    type="button",
                    variant="ghost",
                    aria_label=f"Clear {label.lower()}",
                    data_vd_clear_input=True,
                )
            )
        super().__init__(*children, **kwargs)


class PasswordInput(Component):
    """Password field with an accessible visibility toggle."""

    style = "password-input"

    def __init__(
        self,
        *,
        name: str = "password",
        value: str = "",
        placeholder: str = "",
        label: str = "Password",
        on_input: EventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        field_id = _control_id("password")
        super().__init__(
            Input(
                id=field_id,
                type="password",
                name=name,
                value=value,
                placeholder=placeholder,
                aria_label=label,
                on_input=on_input,
                data_vd_password_field=True,
            ),
            Button(
                "Show",
                type="button",
                variant="ghost",
                aria_label=f"Show {label.lower()}",
                aria_controls=field_id,
                aria_pressed="false",
                data_vd_password_toggle=field_id,
            ),
            **kwargs,
        )


class NumberInput(Component):
    """Numeric input with keyboard-safe stepper controls."""

    style = "number-input"

    def __init__(
        self,
        *,
        name: str,
        value: int | float = 0,
        minimum: int | float | None = None,
        maximum: int | float | None = None,
        step: int | float = 1,
        label: str | None = None,
        on_change: EventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        if step <= 0:
            raise ValueError("NumberInput step must be greater than zero")
        field_id = _control_id("number")
        field_attrs: dict[str, Any] = {
            "id": field_id,
            "type": "number",
            "name": name,
            "value": value,
            "step": step,
            "aria_label": label or name.replace("_", " ").title(),
            "on_change": on_change,
            "data_vd_number_field": True,
        }
        if minimum is not None:
            field_attrs["min"] = minimum
        if maximum is not None:
            field_attrs["max"] = maximum
        super().__init__(
            Button(
                "-",
                type="button",
                variant="ghost",
                aria_label="Decrease value",
                data_vd_number_step=field_id,
                data_vd_step_direction="-1",
            ),
            Input(**field_attrs),
            Button(
                "+",
                type="button",
                variant="ghost",
                aria_label="Increase value",
                data_vd_number_step=field_id,
                data_vd_step_direction="1",
            ),
            **kwargs,
        )


@dataclass(frozen=True, slots=True)
class Choice:
    """A label/value pair used by selection controls."""

    value: str
    label: str
    disabled: bool = False
    description: str | None = None


class Combobox(Component):
    """Filterable single-select listbox."""

    style = "combobox"

    def __init__(
        self,
        options: Sequence[Choice | tuple[str, str] | str],
        *,
        name: str,
        value: str | None = None,
        placeholder: str = "Select an option",
        label: str | None = None,
        empty_text: str = "No matching options",
        on_change: EventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        choices = _choices(options)
        if not choices:
            raise ValueError("Combobox requires at least one option")
        root_id = kwargs.get("id") or _control_id("combobox")
        input_id = f"{root_id}-input"
        listbox_id = f"{root_id}-listbox"
        selected = next((item for item in choices if item.value == value), None)
        attrs: dict[str, Any] = {
            "id": root_id,
            "data_vd_combobox": True,
            "data_vd_combobox_value": value or "",
        }
        if on_change is not None:
            attrs["data_vd_event_change"] = bind_event(on_change)
        super().__init__(
            Input(
                id=input_id,
                type="text",
                name=name,
                value=selected.label if selected else "",
                placeholder=placeholder,
                autocomplete="off",
                role="combobox",
                aria_label=label or name.replace("_", " ").title(),
                aria_autocomplete="list",
                aria_controls=listbox_id,
                aria_expanded="false",
                data_vd_combobox_input=True,
            ),
            Button(
                "Open",
                type="button",
                variant="ghost",
                aria_label="Show options",
                aria_controls=listbox_id,
                data_vd_combobox_toggle=True,
            ),
            _ComboboxList(
                *(
                    _ComboboxOption(
                        choice.label,
                        id=f"{listbox_id}-option-{index}",
                        role="option",
                        aria_selected="true" if choice.value == value else "false",
                        aria_disabled="true" if choice.disabled else None,
                        data_vd_value=choice.value,
                        data_vd_label=choice.label,
                        data_vd_combobox_option=True,
                    )
                    for index, choice in enumerate(choices)
                ),
                _ComboboxEmpty(empty_text, data_vd_combobox_empty=True, hidden=True),
                id=listbox_id,
                role="listbox",
                hidden=True,
            ),
            **attrs,
        )


class _ComboboxList(Component):
    style = "combobox.list"


class _ComboboxOption(Component):
    tag = "button"
    style = "combobox.option"
    auto_id = False

    def __init__(self, *children: Any, **kwargs: Any) -> None:
        super().__init__(*children, type="button", tabindex="-1", **kwargs)


class _ComboboxEmpty(Component):
    style = "combobox.empty"
    auto_id = False


class MultiSelect(Component):
    """Native multiple-selection control with semantic Python events."""

    tag = "select"
    style = "multi-select"

    def __init__(
        self,
        options: Sequence[Choice | tuple[str, str] | str],
        *,
        name: str,
        values: Iterable[str] = (),
        label: str | None = None,
        size: int = 5,
        on_change: EventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        selected = set(values)
        children = tuple(
            _SelectOption(
                choice.label,
                value=choice.value,
                selected=choice.value in selected,
                disabled=choice.disabled,
            )
            for choice in _choices(options)
        )
        attrs: dict[str, Any] = {
            "name": name,
            "multiple": True,
            "size": max(2, size),
            "aria_label": label or name.replace("_", " ").title(),
            "data_vd_multi_select": True,
        }
        if on_change is not None:
            attrs["data_vd_event_change"] = bind_event(on_change)
        super().__init__(*children, **attrs, **kwargs)


class _SelectOption(Component):
    tag = "option"
    auto_id = False


class RadioGroup(Component):
    """A labelled native radio group."""

    style = "choice-group"

    def __init__(
        self,
        options: Sequence[Choice | tuple[str, str] | str],
        *,
        name: str,
        value: str | None = None,
        label: str,
        orientation: str = "vertical",
        on_change: EventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        if orientation not in {"horizontal", "vertical"}:
            raise ValueError("RadioGroup orientation must be horizontal or vertical")
        binding = bind_event(on_change) if on_change is not None else None
        children = tuple(
            _ChoiceLabel(
                Input(
                    type="radio",
                    name=name,
                    value=choice.value,
                    checked=choice.value == value,
                    disabled=choice.disabled,
                    data_vd_event_change=binding,
                ),
                _ChoiceCopy(choice.label, choice.description),
            )
            for choice in _choices(options)
        )
        super().__init__(*children, role="radiogroup", aria_label=label, **kwargs)
        self.props = {"orientation": orientation}


class CheckboxGroup(Component):
    """A labelled group of independent native checkboxes."""

    style = "choice-group"

    def __init__(
        self,
        options: Sequence[Choice | tuple[str, str] | str],
        *,
        name: str,
        values: Iterable[str] = (),
        label: str,
        orientation: str = "vertical",
        on_change: EventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        if orientation not in {"horizontal", "vertical"}:
            raise ValueError("CheckboxGroup orientation must be horizontal or vertical")
        selected = set(values)
        binding = bind_event(on_change) if on_change is not None else None
        children = tuple(
            _ChoiceLabel(
                Input(
                    type="checkbox",
                    name=name,
                    value=choice.value,
                    checked=choice.value in selected,
                    disabled=choice.disabled,
                    data_vd_event_change=binding,
                ),
                _ChoiceCopy(choice.label, choice.description),
            )
            for choice in _choices(options)
        )
        super().__init__(*children, role="group", aria_label=label, **kwargs)
        self.props = {"orientation": orientation}


class _ChoiceLabel(Component):
    tag = "label"
    style = "choice-group.item"
    auto_id = False


class _ChoiceCopy(Component):
    style = "choice-group.copy"
    auto_id = False

    def __init__(self, label: str, description: str | None) -> None:
        children: list[Any] = [
            Component(label, class_="vd-choice-group-label"),
        ]
        if description:
            children.append(
                Component(description, class_="vd-choice-group-description")
            )
        super().__init__(*children)


class Slider(Component):
    """Range input with a synchronized visible value."""

    style = "slider"

    def __init__(
        self,
        *,
        name: str,
        value: int | float = 0,
        minimum: int | float = 0,
        maximum: int | float = 100,
        step: int | float = 1,
        label: str | None = None,
        on_input: EventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        if maximum <= minimum:
            raise ValueError("Slider maximum must be greater than minimum")
        field_id = _control_id("slider")
        output_id = f"{field_id}-output"
        super().__init__(
            Input(
                id=field_id,
                type="range",
                name=name,
                value=value,
                min=minimum,
                max=maximum,
                step=step,
                aria_label=label or name.replace("_", " ").title(),
                aria_describedby=output_id,
                on_input=on_input,
                data_vd_slider=True,
                data_vd_slider_output=output_id,
            ),
            _SliderOutput(str(value), id=output_id, for_=field_id),
            **kwargs,
        )


class _SliderOutput(Component):
    tag = "output"
    style = "slider.output"


class DatePicker(Input):
    """Native date picker that invokes the platform picker where available."""

    def __init__(
        self,
        *,
        name: str,
        value: str | date | None = None,
        minimum: str | date | None = None,
        maximum: str | date | None = None,
        on_change: EventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        attrs: dict[str, Any] = {"type": "date", "name": name}
        if value is not None:
            attrs["value"] = value.isoformat() if isinstance(value, date) else value
        if minimum is not None:
            attrs["min"] = minimum.isoformat() if isinstance(minimum, date) else minimum
        if maximum is not None:
            attrs["max"] = maximum.isoformat() if isinstance(maximum, date) else maximum
        super().__init__(on_change=on_change, **attrs, **kwargs)


class TimePicker(Input):
    """Native time picker with optional minute or second granularity."""

    def __init__(
        self,
        *,
        name: str,
        value: str | None = None,
        step: int = 60,
        on_change: EventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        if step <= 0:
            raise ValueError("TimePicker step must be greater than zero")
        super().__init__(
            type="time",
            name=name,
            value=value,
            step=step,
            on_change=on_change,
            **kwargs,
        )


class Calendar(Component):
    """Accessible month grid for choosing one date."""

    style = "calendar"

    def __init__(
        self,
        *,
        year: int,
        month: int,
        value: date | None = None,
        label: str | None = None,
        on_change: EventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        if not 1 <= month <= 12:
            raise ValueError("Calendar month must be between 1 and 12")
        binding = bind_event(on_change) if on_change is not None else None
        weeks = calendar_module.Calendar(firstweekday=0).monthdatescalendar(year, month)
        heading = label or f"{calendar_module.month_name[month]} {year}"
        header = _CalendarRow(
            *(
                _CalendarHeader(day)
                for day in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
            ),
            role="row",
        )
        rows = tuple(
            _CalendarRow(
                *(
                    _CalendarDay(
                        str(day.day),
                        type="button",
                        data_vd_calendar_day=day.isoformat(),
                        data_vd_event_change=binding,
                        aria_label=day.strftime("%B %d, %Y"),
                        aria_pressed="true" if value == day else "false",
                        data_outside_month=day.month != month,
                    )
                    for day in week
                ),
                role="row",
            )
            for week in weeks
        )
        super().__init__(
            _CalendarCaption(heading),
            _CalendarGrid(header, *rows, role="grid", aria_label=heading),
            data_vd_calendar=True,
            **kwargs,
        )


class _CalendarCaption(Component):
    style = "calendar.caption"
    auto_id = False


class _CalendarGrid(Component):
    style = "calendar.grid"
    auto_id = False


class _CalendarRow(Component):
    style = "calendar.row"
    auto_id = False


class _CalendarHeader(Component):
    style = "calendar.header"
    auto_id = False

    def __init__(self, *children: Any) -> None:
        super().__init__(*children, role="columnheader")


class _CalendarDay(Component):
    tag = "button"
    style = "calendar.day"
    auto_id = False


class FileUpload(Component):
    """Labelled native file selector."""

    style = "file-upload"

    def __init__(
        self,
        *,
        name: str,
        label: str = "Choose files",
        accept: str | None = None,
        multiple: bool = False,
        on_change: EventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        attrs: dict[str, Any] = {
            "type": "file",
            "name": name,
            "multiple": multiple,
            "aria_label": label,
            "on_change": on_change,
            "data_vd_file_input": True,
        }
        if accept:
            attrs["accept"] = accept
        super().__init__(
            Input(**attrs),
            _FileUploadCopy(label, data_vd_file_label=True),
            **kwargs,
        )


class DropZone(Component):
    """Drag-and-drop file target backed by a native file input."""

    tag = "label"
    style = "drop-zone"

    def __init__(
        self,
        *,
        name: str,
        label: str = "Drop files here or browse",
        description: str | None = None,
        accept: str | None = None,
        multiple: bool = False,
        on_change: EventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        attrs: dict[str, Any] = {
            "type": "file",
            "name": name,
            "multiple": multiple,
            "aria_label": label,
            "on_change": on_change,
            "data_vd_drop_input": True,
        }
        if accept:
            attrs["accept"] = accept
        copy: list[Any] = [_FileUploadCopy(label)]
        if description:
            copy.append(_FileUploadDescription(description))
        super().__init__(
            Input(**attrs),
            *copy,
            data_vd_drop_zone=True,
            **kwargs,
        )


class _FileUploadCopy(Component):
    style = "file-upload.label"
    auto_id = False


class _FileUploadDescription(Component):
    style = "file-upload.description"
    auto_id = False


class OTPInput(Component):
    """One-time-code input with paste distribution and mobile autofill."""

    style = "otp-input"

    def __init__(
        self,
        *,
        name: str = "code",
        length: int = 6,
        label: str = "Verification code",
        on_change: EventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        if not 4 <= length <= 10:
            raise ValueError("OTPInput length must be between 4 and 10")
        attrs: dict[str, Any] = {
            "role": "group",
            "aria_label": label,
            "data_vd_otp": True,
            "data_vd_otp_name": name,
        }
        if on_change is not None:
            attrs["data_vd_event_change"] = bind_event(on_change)
        inputs = tuple(
            Input(
                type="text",
                inputmode="numeric",
                pattern="[0-9]*",
                maxlength="1",
                autocomplete="one-time-code" if index == 0 else "off",
                aria_label=f"{label} digit {index + 1}",
                data_vd_otp_cell=True,
                data_vd_otp_index=index,
            )
            for index in range(length)
        )
        super().__init__(*inputs, **attrs, **kwargs)


class ValidationSummary(Component):
    """Focus target summarizing form validation errors."""

    style = "validation-summary"

    def __init__(
        self,
        errors: Mapping[str, str] | Sequence[str],
        *,
        title: str = "Please correct the following",
        **kwargs: Any,
    ) -> None:
        messages = (
            list(errors.values()) if isinstance(errors, Mapping) else list(errors)
        )
        super().__init__(
            _ValidationTitle(title),
            _ValidationList(
                *(_ValidationItem(message) for message in messages),
            ),
            role="alert",
            tabindex="-1",
            **kwargs,
        )


class _ValidationTitle(Component):
    style = "validation-summary.title"
    auto_id = False


class _ValidationList(Component):
    tag = "ul"
    style = "validation-summary.list"
    auto_id = False


class _ValidationItem(Component):
    tag = "li"
    auto_id = False


class _ControlGlyph(Component):
    tag = "span"
    style = "control-glyph"
    auto_id = False

    def __init__(self, name: str) -> None:
        super().__init__(data_vd_glyph=name, aria_hidden="true")


def _choices(
    options: Sequence[Choice | tuple[str, str] | str],
) -> tuple[Choice, ...]:
    normalized: list[Choice] = []
    for option in options:
        if isinstance(option, Choice):
            normalized.append(option)
        elif isinstance(option, tuple):
            normalized.append(Choice(option[0], option[1]))
        else:
            normalized.append(Choice(option, option))
    return tuple(normalized)


__all__ = [
    "Calendar",
    "CheckboxGroup",
    "Choice",
    "Combobox",
    "DatePicker",
    "DropZone",
    "FileUpload",
    "InputGroup",
    "MultiSelect",
    "NumberInput",
    "OTPInput",
    "PasswordInput",
    "RadioGroup",
    "SearchInput",
    "Slider",
    "TimePicker",
    "ValidationSummary",
]
