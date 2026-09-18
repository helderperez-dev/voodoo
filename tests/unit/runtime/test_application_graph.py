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
