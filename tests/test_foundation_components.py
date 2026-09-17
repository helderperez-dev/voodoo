import pytest

from voodoo.adapters import TailwindAdapter, VoodooCSSAdapter
from voodoo.ui import (
    Accordion,
    AccordionItem,
    Alert,
    AspectRatio,
    Breadcrumb,
    BreadcrumbItem,
    Button,
    ButtonGroup,
    Img,
    Kbd,
    Progress,
    Spinner,
    Text,
    set_style_adapter,
)
from voodoo.ui.styles import current_adapter


@pytest.fixture(params=[VoodooCSSAdapter, TailwindAdapter])
def adapter(request):
    original = current_adapter()
    set_style_adapter(request.param())
    yield request.param
    set_style_adapter(original)


def test_alert_uses_semantic_live_region_and_composable_content(adapter):
    html = Alert(
        Text("The deployment finished."),
        title="Ready",
        tone="success",
    ).render()
    assert 'role="status"' in html
    assert "Ready" in html
    assert "The deployment finished." in html
    assert "success" in html

    danger = Alert("Could not save", tone="danger").render()
    assert 'role="alert"' in danger


def test_alert_validates_tone_and_variant():
    with pytest.raises(ValueError, match="invalid Alert tone"):
        Alert("Message", tone="loud")
    with pytest.raises(ValueError, match="invalid Alert variant"):
        Alert("Message", variant="glass")


def test_progress_supports_determinate_and_indeterminate_states(adapter):
    determinate = Progress(72, label="Upload progress", tone="success").render()
    assert "<progress" in determinate
    assert 'value="72"' in determinate
    assert 'max="100"' in determinate
    assert 'aria-label="Upload progress"' in determinate

    indeterminate = Progress(label="Preparing").render()
    assert " value=" not in indeterminate


def test_progress_validates_numeric_contract():
    with pytest.raises(ValueError, match="greater than zero"):
        Progress(0, max=0)
    with pytest.raises(ValueError, match="between zero and max"):
        Progress(101)
    with pytest.raises(ValueError, match="finite"):
        Progress(max=float("inf"))
    with pytest.raises(ValueError, match="between zero and max"):
        Progress(float("nan"))


def test_spinner_has_visible_motion_and_screen_reader_label(adapter):
    html = Spinner("Saving", size="lg").render()
    assert 'role="status"' in html
    assert 'aria-live="polite"' in html
    assert "Saving" in html
    assert "spinner" in html or "animate-spin" in html


def test_breadcrumb_marks_last_item_as_current(adapter):
    html = Breadcrumb(
        BreadcrumbItem("Projects", "/projects"),
        BreadcrumbItem("Voodoo", "/projects/voodoo"),
        BreadcrumbItem("Settings"),
    ).render()
    assert '<nav' in html
    assert 'aria-label="Breadcrumb"' in html
    assert 'href="/projects"' in html
    assert 'aria-current="page"' in html


def test_button_group_has_group_semantics_and_layout(adapter):
    html = ButtonGroup(
        Button("List"),
        Button("Grid"),
        label="View",
        orientation="horizontal",
    ).render()
    assert 'role="group"' in html
    assert 'aria-label="View"' in html
    assert html.count("<button") == 2


def test_button_group_rejects_non_component_children():
    with pytest.raises(TypeError, match="Component"):
        ButtonGroup("Not a button")


def test_accordion_uses_native_disclosure_elements(adapter):
    html = Accordion(
        AccordionItem("Account", Text("Profile settings"), open=True),
        AccordionItem("Security", Text("Passkeys")),
        variant="contained",
    ).render()
    assert html.count("<details") == 2
    assert "<summary" in html
    assert "Account" in html
    assert "open" in html


def test_accordion_rejects_non_item_children():
    with pytest.raises(TypeError, match="AccordionItem"):
        Accordion(Text("Not an item"))


def test_kbd_and_aspect_ratio_render_content_helpers(adapter):
    assert "<kbd" in Kbd("Cmd+K").render()
    media = AspectRatio(Img(src="/cover.jpg", alt="Cover"), ratio="4:3").render()
    assert "aspect-ratio: 4 / 3" in media
    assert 'alt="Cover"' in media


def test_aspect_ratio_rejects_unsafe_or_invalid_values():
    with pytest.raises(ValueError, match="must look like"):
        AspectRatio(Text("No"), ratio="16/9; display:none")
