from voodoo.adapters.voodoo_css import VoodooCSSAdapter
from voodoo.ui import (
    Button,
    Field,
    Form,
    Input,
    Page,
    Popover,
    Skeleton,
    Switch,
    Tooltip,
)
from voodoo.ui.rendering import render_page
from voodoo.ui.styles import current_adapter, set_style_adapter


def _with_native_adapter():
    original = current_adapter()
    set_style_adapter(VoodooCSSAdapter())
    return original


def test_field_wires_label_hint_and_error_accessibly():
    original = _with_native_adapter()
    try:
        field = Field(
            "Email",
            Input(name="email"),
            hint="Used for account notices",
            error="Enter a valid email",
            required=True,
        )
        html = field.render()
        assert "vd-field" in html
        assert "aria-describedby" in html
        assert 'aria-invalid="true"' in html
        assert 'role="alert"' in html
        assert "Enter a valid email" in html
    finally:
        set_style_adapter(original)


def test_input_group_state_contract_propagates_to_wrapped_control():
    from voodoo.ui import InputGroup

    original = _with_native_adapter()
    try:
        html = InputGroup(
            Input(name="domain", on_change=lambda value: value),
            leading="https://",
            read_only=True,
            loading=True,
            error="Domain unavailable",
        ).render()
        assert 'aria-disabled="true"' in html
        assert 'aria-readonly="true"' in html
        assert 'aria-busy="true"' in html
        assert 'aria-invalid="true"' in html
        assert 'data-vd-error="Domain unavailable"' in html
        assert "data-vd-event-change" not in html
        assert "disabled" in html
    finally:
        set_style_adapter(original)


def test_field_state_contract_propagates_to_native_control():
    original = _with_native_adapter()
    try:
        html = Field(
            "Domain",
            Input(name="domain", on_change=lambda value: value),
            read_only=True,
            loading=True,
            error="Domain unavailable",
        ).render()
        assert 'aria-disabled="true"' in html
        assert 'aria-readonly="true"' in html
        assert 'aria-busy="true"' in html
        assert 'aria-invalid="true"' in html
        assert 'data-vd-error="Domain unavailable"' in html
        assert "data-vd-event-change" not in html
    finally:
        set_style_adapter(original)


def test_field_associates_labels_with_nested_native_controls():
    from voodoo.ui import InputGroup

    original = _with_native_adapter()
    try:
        html = Field(
            "Domain",
            InputGroup(Input(name="domain"), leading="https://"),
        ).render()
        input_id = html.split('<input id="', 1)[1].split('"', 1)[0]
        assert f'for="{input_id}"' in html
    finally:
        set_style_adapter(original)


def test_form_generates_semantic_submit_action():
    original = _with_native_adapter()

    async def enroll(value):
        return value

    try:
        html = Form(
            Field("Device name", Input(name="name")),
            on_submit=enroll,
            submit="Enroll",
        ).render()
        assert "data-vd-event-submit=" in html
        assert 'type="submit"' in html
        assert "Enroll" in html
        assert "onsubmit=" not in html
        assert "onclick=" not in html
    finally:
        set_style_adapter(original)


def test_switch_uses_callable_binding_without_inline_js():
    original = _with_native_adapter()

    async def toggle(value):
        return value

    try:
        html = Switch("Live updates", checked=True, on_change=toggle).render()
        assert 'role="switch"' in html
        assert 'aria-checked="true"' in html
        assert "data-vd-event-change=" in html
        assert '<label class="vd-switch-track" for="' in html
        assert "onclick=" not in html
        assert "onchange=" not in html
    finally:
        set_style_adapter(original)


def test_tooltip_adds_accessible_description():
    original = _with_native_adapter()
    try:
        html = Tooltip(Button("Delete"), "Delete this item").render()
        assert 'role="tooltip"' in html
        assert "aria-describedby=" in html
        assert "Delete this item" in html
    finally:
        set_style_adapter(original)


def test_popover_uses_native_browser_contract():
    original = _with_native_adapter()
    try:
        html = Popover(Button("Options"), "Popover content").render()
        assert "popovertarget=" in html
        assert "popover" in html
        assert "Popover content" in html
        assert "onclick=" not in html
    finally:
        set_style_adapter(original)


def test_popover_state_contract_blocks_unavailable_trigger():
    original = _with_native_adapter()
    try:
        html = Popover(
            Button("Options"),
            "Popover content",
            read_only=True,
            loading=True,
            error="Popover unavailable",
        ).render()
        assert 'aria-disabled="true"' in html
        assert 'aria-readonly="true"' in html
        assert 'aria-busy="true"' in html
        assert 'aria-invalid="true"' in html
        assert 'data-vd-error="Popover unavailable"' in html
        assert "popovertarget=" not in html
    finally:
        set_style_adapter(original)


def test_skeleton_preserves_layout_without_semantic_noise():
    original = _with_native_adapter()
    try:
        html = Skeleton(lines=3, width="12rem").render()
        assert 'aria-hidden="true"' in html
        assert html.count("vd-skeleton-line") >= 3
    finally:
        set_style_adapter(original)


def test_page_exposes_density_as_semantic_api():
    original = _with_native_adapter()
    try:
        compact = Page("Dense", density="compact").render()
        comfortable = Page("Calm").render()
        assert 'data-vd-density="compact"' in compact
        assert "data-vd-density" not in comfortable
    finally:
        set_style_adapter(original)


def test_native_render_includes_design_system_layer():
    original = _with_native_adapter()
    try:
        html = render_page(Button("Deploy", loading=True))
        assert "Voodoo Design System 4" in html
        assert "Voodoo Design System 4 — Theme contract" in html
        assert "--vd-control-height-md" in html
        assert "prefers-reduced-motion" in html
        assert 'data-vd-loading="true"' in html
    finally:
        set_style_adapter(original)
