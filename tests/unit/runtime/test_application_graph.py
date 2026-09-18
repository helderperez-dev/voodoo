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
