"""Voodoo 3.0 package-root API contract."""

import voodoo

EXPECTED_EXPORTS = {
    "Agent",
    "App",
    "Model",
    "page",
    "state",
    "task",
    "tool",
}


def test_public_api_pinned() -> None:
    assert set(voodoo.__all__) == EXPECTED_EXPORTS
    assert len(voodoo.__all__) == len(EXPECTED_EXPORTS)


def test_all_exports_resolve() -> None:
    for name in voodoo.__all__:
        assert getattr(voodoo, name, None) is not None, name


def test_root_has_no_deprecation_registry() -> None:
    assert not hasattr(voodoo, "_DEPRECATED_EXPORTS")


def test_catalog_symbols_are_not_root_exports() -> None:
    catalog_symbols = {
        "AgentRun",
        "Button",
        "Card",
        "LLMProvider",
        "State",
        "Theme",
        "ToolRegistry",
        "ToolSpec",
        "api",
        "config",
        "event",
        "mesh",
        "trace",
    }
    assert not (set(voodoo.__all__) & catalog_symbols)


def test_version_is_string() -> None:
    assert isinstance(voodoo.__version__, str)
    assert voodoo.__version__.count(".") == 2
    assert voodoo.__version__.split(".")[0] == "3"
