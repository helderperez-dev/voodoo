"""Sprint 5 — Durable scheduler tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from voodoo.storage.scheduler import SQLiteScheduleStore


def _make_store(tmp_path):
    return SQLiteScheduleStore(tmp_path / "schedules.db")


class TestScheduleStore:
    def test_create_and_list(self, tmp_path):
        store = _make_store(tmp_path)
        now = datetime.now(UTC)
        store.create("s1", "test", "at", now.isoformat(), now, "task_a", {"x": 1})
        schedules = store.list_all()
        assert len(schedules) == 1
        assert schedules[0]["id"] == "s1"
        assert schedules[0]["task_type"] == "task_a"
        store.close()

    def test_claim_due_one_shot(self, tmp_path):
        store = _make_store(tmp_path)
        past = datetime.now(UTC) - timedelta(minutes=1)
        store.create("s1", "oneshot", "at", past.isoformat(), past, "task_a")
        due = store.claim_due()
        assert len(due) == 1
        assert due[0]["id"] == "s1"
        # one-shot is now inactive
        assert store.get("s1")["active"] == 0
        store.close()

    def test_claim_due_interval(self, tmp_path):
        store = _make_store(tmp_path)
        past = datetime.now(UTC) - timedelta(seconds=1)
        store.create("s2", "periodic", "interval", "5", past, "task_b")
        due = store.claim_due()
        assert len(due) == 1
        # interval reschedules — still active
        sched = store.get("s2")
        assert sched["active"] == 1
        assert datetime.fromisoformat(sched["next_run_at"]) > past
        store.close()

    def test_claim_due_not_due(self, tmp_path):
        store = _make_store(tmp_path)
        future = datetime.now(UTC) + timedelta(hours=1)
        store.create("s3", "future", "at", future.isoformat(), future, "task_c")
        due = store.claim_due()
        assert len(due) == 0
        store.close()

    def test_pause_resume(self, tmp_path):
        store = _make_store(tmp_path)
        now = datetime.now(UTC)
        store.create("s4", "pause", "interval", "5", now, "task_d")
        assert store.pause("s4")
        assert store.get("s4")["active"] == 0
        assert store.resume("s4")
        assert store.get("s4")["active"] == 1
        store.close()

    def test_duplicate_claim_is_safe(self, tmp_path):
        store = _make_store(tmp_path)
        past = datetime.now(UTC) - timedelta(minutes=1)
        store.create("s5", "dup", "at", past.isoformat(), past, "task_e")
        # Two concurrent stores (simulating two scheduler instances)
        store2 = SQLiteScheduleStore(store.path)
        due1 = store.claim_due()
        due2 = store2.claim_due()
        # Only one should claim the one-shot
        assert len(due1) + len(due2) == 1
        store.close()
        store2.close()


class TestCronNext:
    def test_minimal_cron(self, tmp_path):
        store = _make_store(tmp_path)
        now = datetime.now(UTC)
        # Run every minute
        store.create("s6", "cron", "cron", "* * * * *", now, "task_f")
        due = store.claim_due()
        assert len(due) == 1
        # Still active (cron reschedules)
        assert store.get("s6")["active"] == 1
        store.close()


class TestScheduleSurvivesRestart:
    def test_schedule_from_timespec(self, tmp_path):
        from voodoo.primitives.time import TimeSpec

        store = _make_store(tmp_path)
        spec = TimeSpec.with_interval(30)
        ok = store.schedule_from_timespec("ts1", spec, "task_ts")
        assert ok is True
        sched = store.get("ts1")
        assert sched["kind"] == "interval"
        assert sched["spec"] == "30"
        assert sched["task_type"] == "task_ts"
        store.close()

    def test_schedule_from_timespec_without_schedule(self, tmp_path):
        from voodoo.primitives.time import TimeSpec

        store = _make_store(tmp_path)
        spec = TimeSpec()  # no schedule, no interval
        ok = store.schedule_from_timespec("ts2", spec, "task_ts")
        assert ok is False
        assert store.get("ts2") is None
        store.close()

    def test_schedule_persists(self, tmp_path):
        path = tmp_path / "schedules.db"
        store = SQLiteScheduleStore(path)
        now = datetime.now(UTC)
        store.create("persist", "survive", "interval", "10", now, "task_p")
        store.close()

        reopened = SQLiteScheduleStore(path)
        schedules = reopened.list_all()
        assert len(schedules) == 1
        assert schedules[0]["id"] == "persist"
        reopened.close()
