import pytest

from voodoo.runtime.application_graph import ApplicationGraph, Extension, ExtensionManifest
from voodoo.runtime.extension import ExtensionState, RuntimeExtensionRegistry


class AnalyticsExtension(Extension):
    manifest = ExtensionManifest(
        name="analytics",
        version="1.0",
        capabilities=("analytics.read",),
        observers=("events",),
    )


def test_extension_installation_does_not_activate_or_grant_surface():
    registry = RuntimeExtensionRegistry()
    extension = AnalyticsExtension()

    status = registry.discover(extension)
    graph = ApplicationGraph()
    registry.contribute(graph)

    assert status.state is ExtensionState.DISCOVERED
    assert registry.active() == ()
    assert graph.get("extension:analytics") is None


def test_extension_requires_explicit_configuration_and_activation():
    registry = RuntimeExtensionRegistry()
    registry.discover(AnalyticsExtension())

    with pytest.raises(RuntimeError, match="configured"):
        registry.activate("analytics")

    registry.configure("analytics")
    status = registry.activate("analytics")
    graph = ApplicationGraph()
    registry.contribute(graph)

    assert status.state is ExtensionState.ACTIVE
    assert graph.get("extension:analytics") is not None
    assert graph.get("capability:analytics.read") is not None


def test_unhealthy_extension_is_removed_from_active_projection():
    registry = RuntimeExtensionRegistry()
    registry.discover(AnalyticsExtension())
    registry.configure("analytics")
    registry.activate("analytics")

    status = registry.health("analytics", healthy=False, reason="provider unavailable")

    assert status.state is ExtensionState.UNHEALTHY
    assert registry.active() == ()
