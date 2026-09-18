from voodoo.runtime.dependency_graph import DependencyGraph
from voodoo.ui.state import (
    start_dependency_tracking,
    state,
    stop_dependency_tracking,
)


def test_state_reads_can_feed_runtime_dependency_overlay():
    graph = DependencyGraph()
    value = state(1)
    token = start_dependency_tracking(graph, "goal:growth")
    try:
        assert value.get() == 1
    finally:
        stop_dependency_tracking(token)

    assert graph.dependencies("goal:growth") == (value.dependency_id,)


def test_state_revision_advances_on_mutation():
    value = state(1)

    assert value.revision == "0"
    value.set(2)
    assert value.revision == "1"
    value.update(lambda current: current + 1)
    assert value.revision == "2"
