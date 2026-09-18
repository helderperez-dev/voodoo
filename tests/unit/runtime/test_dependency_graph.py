from voodoo.runtime.application_graph import ChangeReason
from voodoo.runtime.dependency_graph import DependencyGraph


def test_dependency_graph_tracks_runtime_dependencies_and_transitive_dependents():
    graph = DependencyGraph()
    graph.observe("goal:growth", "state:conversion")
    graph.observe("page:dashboard", "goal:growth")

    assert graph.dependencies("goal:growth") == ("state:conversion",)
    assert graph.dependents("state:conversion", transitive=True) == (
        "goal:growth",
        "page:dashboard",
    )


def test_dependency_graph_replaces_stale_runtime_dependencies():
    graph = DependencyGraph()
    graph.observe("page:dashboard", "state:old")
    graph.replace("page:dashboard", {"state:new"})

    assert graph.dependencies("page:dashboard") == ("state:new",)
    assert graph.dependents("state:old") == ()


def test_invalidation_marks_affected_nodes_dirty_with_revision_and_reason():
    graph = DependencyGraph()
    graph.observe("goal:growth", "observation:conversion")
    graph.observe("page:dashboard", "goal:growth")

    invalidation = graph.invalidate(
        "observation:conversion",
        reason=ChangeReason.OBSERVATION,
        revision="obs-43",
    )

    assert invalidation.affected == ("goal:growth", "page:dashboard")
    assert graph.explain("goal:growth") == {
        "node_id": "goal:growth",
        "dependencies": ["observation:conversion"],
        "dirty": True,
        "sources": ["observation:conversion"],
        "reasons": ["observation"],
        "revision": "obs-43",
        "sequence": 1,
    }
    assert graph.revision("observation:conversion").revision == "obs-43"


def test_dirty_reasons_coalesce_until_consumed():
    graph = DependencyGraph()
    graph.observe("goal:growth", "state:conversion")

    graph.invalidate("state:conversion", reason=ChangeReason.STATE, revision="state-1")
    graph.invalidate(
        "state:conversion", reason=ChangeReason.CONFIGURATION, revision="config-2"
    )

    dirty = graph.consume("goal:growth")
    assert dirty is not None
    assert dirty.sources == ("state:conversion",)
    assert dirty.reasons == (ChangeReason.CONFIGURATION, ChangeReason.STATE)
    assert dirty.revision == "config-2"
    assert graph.consume("goal:growth") is None


def test_dependency_graph_returns_bounded_recomputation_batch():
    graph = DependencyGraph()
    graph.observe("goal:a", "state:value")
    graph.observe("goal:b", "state:value")
    graph.observe("page:c", "goal:a")
    graph.invalidate("state:value", revision="rev-1")

    batch = graph.next_dirty(limit=2)

    assert len(batch) == 2
    graph.acknowledge(tuple(item.node_id for item in batch))
    assert len(graph.dirty()) == 1


def test_dependency_graph_rejects_empty_recomputation_limit():
    graph = DependencyGraph()

    import pytest

    with pytest.raises(ValueError, match="at least 1"):
        graph.next_dirty(limit=0)


def test_dependency_recomputation_remains_bounded_at_scale():
    graph = DependencyGraph()
    for index in range(1000):
        graph.observe(f"consumer:{index:04d}", "state:shared")

    graph.invalidate("state:shared", revision="rev-scale")

    first = graph.next_dirty(limit=64)
    assert len(first) == 64
    graph.acknowledge(tuple(item.node_id for item in first))
    assert len(graph.dirty()) == 936
    assert all(item.revision == "rev-scale" for item in first)
