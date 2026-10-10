from voodoo.ui import (
    Action,
    Button,
    Calendar,
    Checkbox,
    Combobox,
    DatePicker,
    DropdownMenu,
    Input,
    ListBox,
    ListOption,
    MenuCheckboxItem,
    MenuItem,
    MenuRadioItem,
    MultiSelect,
    Radio,
    RadioGroup,
    Step,
    Stepper,
    Switch,
    TimePicker,
    ToggleGroup,
    ToggleItem,
)


def test_checkbox_and_radio_share_control_state_attributes():
    for control in (Checkbox(disabled=True), Radio(loading=True, error=True)):
        html = control.render()
        assert "disabled" in html
    assert 'aria-busy="true"' in Radio(loading=True).render()
    assert 'aria-invalid="true"' in Radio(error=True).render()


def test_native_date_and_time_pickers_share_control_state_contract():
    date_html = DatePicker(name="start", disabled=True, read_only=True).render()
    time_html = TimePicker(name="start", loading=True, error=True).render()
    assert 'type="date"' in date_html
    assert "disabled" in date_html and 'aria-readonly="true"' in date_html
    assert 'type="time"' in time_html
    assert 'aria-busy="true"' in time_html
    assert 'aria-invalid="true"' in time_html


def test_switch_exposes_loading_read_only_and_error_states():
    html = Switch(
        "Notifications", loading=True, read_only=True, error="invalid"
    ).render()
    assert "disabled" in html
    assert 'aria-readonly="true"' in html
    assert 'aria-busy="true"' in html
    assert 'aria-invalid="true"' in html


def test_switch_does_not_bind_changes_when_unavailable():
    def toggle(_event):
        return None

    for state in ("disabled", "read_only", "loading"):
        html = Switch(on_change=toggle, **{state: True}).render()
        assert "data-vd-event-change" not in html


def test_native_controls_do_not_bind_changes_when_unavailable():
    def changed(_event):
        return None

    for control in (
        Input(on_change=changed, disabled=True),
        Input(on_input=changed, read_only=True),
        Input(on_change=changed, loading=True),
    ):
        assert "data-vd-event-" not in control.render()


def test_composite_controls_do_not_bind_changes_when_unavailable():
    def changed(_event):
        return None

    options = [("one", "One"), ("two", "Two")]
    controls = (
        Combobox(options, name="choice", on_change=changed, disabled=True),
        MultiSelect(options, name="choices", on_change=changed, read_only=True),
        RadioGroup(options, name="choice", label="Choice", on_change=changed, loading=True),
        Calendar(year=2026, month=10, on_change=changed, disabled=True),
        ListBox(ListOption("One"), on_select=changed, error="Unavailable"),
    )
    for control in controls:
        assert "data-vd-event-change" not in control.render()


def test_action_controls_fail_closed_on_error():
    def selected(_event):
        return None

    controls = (
        MenuItem("Delete", on_select=selected, error="Unavailable"),
        DropdownMenu(
            Button("Open"),
            MenuItem("Delete", on_select=selected),
            error="Unavailable",
        ),
        Action("Delete", on_select=selected, error="Unavailable"),
        Stepper(
            Step("One"),
            Step("Two"),
            on_step_click=selected,
            error="Unavailable",
        ),
    )
    for control in controls:
        html = control.render()
        assert 'aria-invalid="true"' in html
        assert "data-vd-event-click" not in html


def test_interaction_kernel_actions_fail_closed_on_error():
    def selected(_event):
        return None

    controls = (
        ToggleGroup(
            ToggleItem(value="one", label="One"),
            on_change=selected,
            error="Unavailable",
        ),
        MenuCheckboxItem("Flag", on_select=selected, error="Unavailable"),
        MenuRadioItem("Choice", value="one", on_select=selected, error="Unavailable"),
    )
    for control in controls:
        html = control.render()
        assert 'aria-invalid="true"' in html
        assert "data-vd-event-" not in html
