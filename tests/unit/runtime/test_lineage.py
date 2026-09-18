from voodoo.runtime.lineage import LineageEvent, RuntimeLineage


def test_lineage_explains_causal_parent_chain():
    lineage = RuntimeLineage()
    lineage.record(LineageEvent("goal", "goal:growth", "target unmet"))
    lineage.record(
        LineageEvent("intent", "intent:adjust", "proposed", parent_id="goal:growth")
    )
    lineage.record(
        LineageEvent("execution", "exec:1", "authorized", parent_id="intent:adjust")
    )

    events = lineage.why("exec:1")

    assert tuple(event.subject_id for event in events) == (
        "exec:1",
        "intent:adjust",
        "goal:growth",
    )
