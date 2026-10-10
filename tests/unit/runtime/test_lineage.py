from voodoo.runtime.inspection import LineageEvent, RuntimeLineage


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


def test_lineage_survives_restart(tmp_path):
    path = tmp_path / "lineage.jsonl"
    first = RuntimeLineage(path)
    first.record_transition(
        "observation", "obs-1", parent_id=None, reason="metric observed"
    )
    first.record_transition(
        "intent", "intent-1", parent_id="obs-1", reason="goal unmet"
    )

    restarted = RuntimeLineage(path)

    assert restarted.chain("intent-1") == ("obs-1", "intent-1")
    assert len(restarted.events()) == 2


def test_lineage_inspection_is_stable_after_restart(tmp_path):
    path = tmp_path / "lineage.jsonl"
    first = RuntimeLineage(path)
    first.record_transition(
        "observation", "obs-1", parent_id=None, reason="conversion observed"
    )
    first.record_transition(
        "intent", "intent-1", parent_id="obs-1", reason="goal below target"
    )

    inspection = RuntimeLineage(path).inspect("intent-1")

    assert inspection["subject_id"] == "intent-1"
    assert inspection["chain"] == ["obs-1", "intent-1"]
    assert [event["kind"] for event in inspection["events"]] == [
        "intent",
        "observation",
    ]


def test_lineage_reads_legacy_unversioned_record(tmp_path):
    path = tmp_path / "legacy-lineage.jsonl"
    path.write_text(
        '{"kind":"goal","subject_id":"goal-legacy","reason":"old",'
        '"parent_id":null,"metadata":{},'
        '"recorded_at":"2026-01-01T00:00:00+00:00"}'
        "\n"
    )

    restored = RuntimeLineage(path)

    assert restored.events()[0].subject_id == "goal-legacy"
    assert restored.events()[0].schema_version == 1


def test_lineage_skips_future_schema_with_diagnostic(tmp_path, caplog):
    path = tmp_path / "future-lineage.jsonl"
    path.write_text(
        '{"_schema_version":99,"kind":"goal","subject_id":"future","reason":"old"}'
        "\n"
    )

    with caplog.at_level("WARNING", logger="voodoo.runtime.lineage"):
        restored = RuntimeLineage(path)

    assert restored.events() == ()
    assert "lineage record skipped" in caplog.text
