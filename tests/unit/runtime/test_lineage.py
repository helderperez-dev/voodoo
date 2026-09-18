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


def test_lineage_chain_orders_root_cause_to_subject():
    lineage = RuntimeLineage()
    lineage.record_transition(
        "observation", "obs-1", parent_id=None, reason="metric observed"
    )
    lineage.record_transition(
        "goal.evaluated", "goal-1", parent_id="obs-1", reason="target unmet"
    )
    lineage.record_transition(
        "intent.proposed", "intent-1", parent_id="goal-1", reason="adjust target"
    )
    lineage.record_transition(
        "execution", "exec-1", parent_id="intent-1", reason="executed"
    )

    assert lineage.chain("exec-1") == ("obs-1", "goal-1", "intent-1", "exec-1")


def test_lineage_clear_resets_in_process_inspection_state():
    lineage = RuntimeLineage()
    lineage.record_transition("intent", "intent-1", parent_id=None, reason="created")

    lineage.clear()

    assert lineage.events() == ()
