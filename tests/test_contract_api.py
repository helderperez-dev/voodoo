"""Public API contract tests.

These pin `voodoo.__all__` exactly: CI fails if an export is added or removed
without a deliberate update to EXPECTED_EXPORTS. Legacy names must keep
resolving through the deprecation shims.

Semver: 1.0 — no new exports without a version bump.
"""

import pytest

import voodoo

EXPECTED_EXPORTS = {
    # Core runtime
    "App",
    "create_app",
    "page",
    "api",
    "trace",
    # Reactive state & events
    "state",
    "event",
    "State",
    # Realtime
    "mesh",
    "register_event",
    "ws_manager",
    # Workers
    "task",
    # AI
    "Agent",
    "AgentRun",
    "tool",
    "ToolSpec",
    "ToolRegistry",
    "LLMProvider",
    # Data
    "BaseModel",
    "Model",
    # Theming & configuration
    "Theme",
    "ThemeColors",
    "create_theme",
    "config",
    # Styling seam
    "StyleAdapter",
    "NoopAdapter",
    "TailwindAdapter",
    "VoodooCSSAdapter",
    "set_style_adapter",
    "current_adapter",
    # UI — layout
    "Component",
    "Div",
    "Flex",
    "Stack",
    "Grid",
    "Box",
    "Container",
    "Page",
    "A",
    "Link",
    # UI — core components
    "Button",
    "Card",
    "Text",
    "Heading",
    "Badge",
    "Avatar",
    "Divider",
    "Dialog",
    "Modal",
    # UI — forms
    "Form",
    "Label",
    "Input",
    "Textarea",
    "Select",
    "Option",
    "Checkbox",
    "Radio",
    # UI — collections
    "Table",
    "List",
    "ListItem",
    # UI — semantic structure
    "Nav",
    "Header",
    "Footer",
    "Main",
    "Section",
    "Article",
}


def test_public_api_pinned():
    """__all__ must match the frozen contract exactly."""
    assert set(voodoo.__all__) == EXPECTED_EXPORTS
    assert len(voodoo.__all__) == len(EXPECTED_EXPORTS)  # no duplicates


def test_all_exports_resolve():
    for name in voodoo.__all__:
        assert getattr(voodoo, name, None) is not None, name


def test_naming_law():
    """Classes are PascalCase; functions/decorators/namespaces are snake_case."""
    for name in voodoo.__all__:
        obj = getattr(voodoo, name)
        if isinstance(obj, type):
            assert name[0].isupper(), f"class {name} must be PascalCase"
        else:
            assert name[0].islower() or name == "_", (
                f"non-class {name} must be snake_case"
            )


def test_no_overlap_between_all_and_deprecated():
    assert not set(voodoo.__all__) & set(voodoo._DEPRECATED_EXPORTS)


@pytest.mark.parametrize(
    "name",
    [
        "hash_password",
        "AuthMiddleware",
        "LoginForm",
        "SEO",
        "enqueue",
        "telemetry_store",
        "set_theme",
        "GEO",
    ],
)
def test_deprecated_names_resolve_with_warning(name):
    with pytest.warns(DeprecationWarning, match="deprecated"):
        value = getattr(voodoo, name)
    assert value is not None


def test_deprecated_values_match_submodule():
    from voodoo.auth import hash_password as real_hash_password

    with pytest.warns(DeprecationWarning):
        shimmed = voodoo.hash_password
    assert shimmed is real_hash_password


def test_unknown_attribute_raises():
    with pytest.raises(AttributeError):
        getattr(voodoo, "this_does_not_exist")  # noqa: B009


def test_version_is_string():
    assert isinstance(voodoo.__version__, str)
    assert voodoo.__version__.count(".") == 2


def test_version_is_1_0():
    """The public API is frozen at semver 1.0."""
    major = voodoo.__version__.split(".")[0]
    assert major == "1", f"Expected major version 1, got {major}"
