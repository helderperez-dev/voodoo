from voodoo.runtime.application_graph import (
    ApplicationGraph,
    ApplicationNodeKind,
)


def test_application_graph_registers_nodes_and_relationships():
    graph = ApplicationGraph()
    goal = graph.node(ApplicationNodeKind.GOAL, "growth")
    capability = graph.node(ApplicationNodeKind.CAPABILITY, "email.send")

    graph.connect(goal.id, "requires", capability.id)

    assert graph.dependencies(goal.id) == (capability,)
    assert graph.dependents(capability.id) == (goal,)
    assert graph.validate() == []


def test_application_graph_rejects_relationship_to_unknown_node():
    graph = ApplicationGraph()
    goal = graph.node(ApplicationNodeKind.GOAL, "growth")

    try:
        graph.connect(goal.id, "requires", "capability:missing")
    except KeyError as exc:
        assert "capability:missing" in str(exc)
    else:
        raise AssertionError("expected unknown graph target to fail")


def test_application_graph_is_idempotent_for_same_semantic_node():
    graph = ApplicationGraph()
    first = graph.node(ApplicationNodeKind.RESOURCE, "payments")
    second = graph.node(ApplicationNodeKind.RESOURCE, "payments")

    assert first is second


def test_application_graph_describes_tool_capability_relationship():
    from voodoo.ai.tools.registry import ToolSpec, default_registry
    from voodoo.runtime.application_graph import build_application_graph

    previous = dict(default_registry._tools)
    default_registry._tools.clear()
    try:
        default_registry.register(
            ToolSpec(
                name="refund",
                description="Refund payment",
                input_schema={},
                output_schema={},
                permissions=["payment.refund"],
                source="tests:test_refund:1",
            )
        )

        class EmptyApp:
            routes = []

        graph = build_application_graph(EmptyApp())
        tool = graph.get("tool:refund")
        capability = graph.get("capability:payment.refund")

        assert tool is not None
        assert capability is not None
        assert graph.dependencies(tool.id, "requires") == (capability,)
    finally:
        default_registry._tools.clear()
        default_registry._tools.update(previous)


def test_application_graph_describes_registered_models():
    from voodoo.data.base import _models
    from voodoo.data.model import Model
    from voodoo.runtime.application_graph import build_application_graph

    previous = list(_models)
    try:

        class Customer(Model):
            email: str

        class EmptyApp:
            routes = []

        graph = build_application_graph(EmptyApp())
        model = graph.get("model:Customer")

        assert model is not None
        assert model.metadata["table"] == "customer"
    finally:
        _models[:] = previous


def test_application_graph_fingerprint_is_deterministic():
    first = ApplicationGraph()
    first.node(ApplicationNodeKind.RESOURCE, "store")
    second = ApplicationGraph()
    second.node(ApplicationNodeKind.RESOURCE, "store")

    assert first.fingerprint == second.fingerprint
    assert first.snapshot()["fingerprint"] == first.fingerprint


def test_application_graph_diff_reports_semantic_changes():
    from voodoo.runtime.application_graph import diff_application_graph

    previous = ApplicationGraph()
    current = ApplicationGraph()
    task = current.node(ApplicationNodeKind.TASK, "sync")
    current.connect(current.application_id, "contains", task.id)

    change = diff_application_graph(previous, current)

    assert change.changed is True
    assert change.added_nodes == ("task:sync",)
    assert change.added_edges == (("application", "contains", "task:sync"),)


def test_application_graph_affected_walks_transitive_dependents():
    graph = ApplicationGraph()
    resource = graph.node(ApplicationNodeKind.RESOURCE, "payments")
    capability = graph.node(ApplicationNodeKind.CAPABILITY, "payment.read")
    goal = graph.node(ApplicationNodeKind.GOAL, "growth")
    graph.connect(capability.id, "requires", resource.id)
    graph.connect(goal.id, "requires", capability.id)

    assert tuple(node.id for node in graph.affected(resource.id)) == (
        "capability:payment.read",
        "goal:growth",
    )


def test_extension_contributes_provider_without_granting_authority():
    from voodoo.runtime.application_graph import Extension, ExtensionManifest

    class Payments(Extension):
        manifest = ExtensionManifest(
            name="payments",
            version="1.0.0",
            capabilities=("payment.refund",),
        )

    graph = ApplicationGraph()
    Payments().contribute(graph)

    extension = graph.get("extension:payments")
    capability = graph.get("capability:payment.refund")
    assert extension is not None
    assert capability is not None
    assert graph.dependencies(extension.id, "provides") == (capability,)


def test_extension_registry_requires_explicit_activation():
    from voodoo.runtime.application_graph import (
        Extension,
        ExtensionManifest,
        ExtensionRegistry,
    )

    class Analytics(Extension):
        manifest = ExtensionManifest(name="analytics", version="1.0.0")

    registry = ExtensionRegistry()
    extension = Analytics()
    registry.use(extension)

    graph = ApplicationGraph()
    registry.contribute(graph)

    assert graph.get("extension:analytics") is not None


def test_invalidation_records_reason_revision_and_affected_nodes():
    from voodoo.runtime.application_graph import (
        ChangeReason,
        InvalidationEngine,
    )

    graph = ApplicationGraph()
    resource = graph.node(ApplicationNodeKind.RESOURCE, "analytics")
    goal = graph.node(ApplicationNodeKind.GOAL, "conversion")
    graph.connect(goal.id, "observes", resource.id)

    invalidation = InvalidationEngine(graph).invalidate(
        resource.id,
        reason=ChangeReason.OBSERVATION,
        revision="obs-42",
    )

    assert invalidation.source == resource.id
    assert invalidation.affected == (goal.id,)
    assert invalidation.reason is ChangeReason.OBSERVATION
    assert invalidation.revision == "obs-42"


def test_extension_contract_has_no_vendor_dependency():
    from voodoo.runtime.application_graph import Extension, ExtensionManifest

    class ExternalAnalytics(Extension):
        manifest = ExtensionManifest(
            name="external-analytics",
            version="1.0.0",
            capabilities=("analytics.events.read",),
        )

    graph = ApplicationGraph()
    ExternalAnalytics().contribute(graph)

    assert graph.get("extension:external-analytics") is not None
    assert graph.get("capability:analytics.events.read") is not None


def test_canonical_goal_contributes_requirements_to_graph():
    from voodoo.runtime.application_graph import contribute_goal
    from voodoo.runtime.goal import Goal

    goal = Goal(
        id="goal_growth",
        name="growth",
        objective="Increase conversion",
        requires=["campaign.adjust"],
    )
    graph = ApplicationGraph()
    node = contribute_goal(graph, goal)

    assert node.id == "goal:goal_growth"
    assert tuple(item.id for item in graph.dependencies(node.id, "requires")) == (
        "capability:campaign.adjust",
    )


def test_application_graph_diff_detects_same_id_metadata_change():
    from voodoo.runtime.application_graph import diff_application_graph

    previous = ApplicationGraph()
    previous.node(ApplicationNodeKind.RESOURCE, "store", metadata={"version": 1})
    current = ApplicationGraph()
    current.node(ApplicationNodeKind.RESOURCE, "store", metadata={"version": 2})

    change = diff_application_graph(previous, current)

    assert change.changed_nodes == ("resource:store",)
    assert change.changed is True


def test_application_graph_diff_detects_edge_metadata_change():
    from voodoo.runtime.application_graph import diff_application_graph

    previous = ApplicationGraph()
    p_resource = previous.node(ApplicationNodeKind.RESOURCE, "store")
    p_goal = previous.node(ApplicationNodeKind.GOAL, "durable")
    previous.connect(p_goal.id, "observes", p_resource.id, metadata={"mode": "poll"})

    current = ApplicationGraph()
    c_resource = current.node(ApplicationNodeKind.RESOURCE, "store")
    c_goal = current.node(ApplicationNodeKind.GOAL, "durable")
    current.connect(c_goal.id, "observes", c_resource.id, metadata={"mode": "event"})

    change = diff_application_graph(previous, current)

    assert change.changed_edges == (("goal:durable", "observes", "resource:store"),)


def test_extension_contributes_generic_runtime_surfaces():
    from voodoo.runtime.application_graph import Extension, ExtensionManifest

    class Commerce(Extension):
        manifest = ExtensionManifest(
            name="commerce",
            version="1.0.0",
            capabilities=("payment.read",),
            resources=("orders",),
            effects=("refund",),
            observers=("order-events",),
            services=("payments",),
        )

    graph = ApplicationGraph()
    Commerce().contribute(graph)
    extension = graph.get("extension:commerce")

    assert extension is not None
    assert graph.get("resource:orders") is not None
    assert graph.get("effect:refund") is not None
    assert graph.get("observer:order-events") is not None
    assert graph.get("service:payments") is not None


def test_application_graph_classifies_websocket_route_as_api():
    from voodoo.runtime.application_graph import build_application_graph

    class WebSocketRoute:
        path = "/events"
        methods = None

    class App:
        routes = [WebSocketRoute()]

    graph = build_application_graph(App())

    assert graph.get("api:/events") is not None
    assert graph.get("page:/events") is None
