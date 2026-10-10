from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from voodoo.primitives.time import TimeSpec
from voodoo.schedule import Scheduler, _next_cron


class _Queue:
    async def enqueue(self, *args, **kwargs):
        return None


def test_next_cron_interprets_local_wall_clock_as_utc_instant() -> None:
    now = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    assert _next_cron("30 9 * * 1-5", now, "America/New_York") == datetime(
        2026, 1, 15, 14, 30, tzinfo=UTC
    )


def test_next_cron_handles_dst_offset() -> None:
    now = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
    assert _next_cron("30 9 * * *", now, "America/New_York") == datetime(
        2026, 7, 1, 13, 30, tzinfo=UTC
    )


def test_scheduler_persists_timezone_and_timespec_for_cron(tmp_path) -> None:
    scheduler = Scheduler(tmp_path / "schedule.db", _Queue())
    try:
        schedule_id = scheduler.cron(
            "0 9 * * *", "daily", {"ok": True}, timezone="Europe/Lisbon"
        )
        row = scheduler._conn.execute(
            "SELECT spec FROM schedules WHERE id = ?", (schedule_id,)
        ).fetchone()
        assert json.loads(row["spec"]) == {
            "cron": "0 9 * * *",
            "timezone": "Europe/Lisbon",
        }
        assert TimeSpec(schedule="0 9 * * *", timezone="Asia/Tokyo").timezone == (
            "Asia/Tokyo"
        )
    finally:
        scheduler.close()


def test_scheduler_rejects_unknown_timezone(tmp_path) -> None:
    scheduler = Scheduler(tmp_path / "schedule.db", _Queue())
    try:
        with pytest.raises(ValueError, match="unknown IANA scheduler timezone"):
            scheduler.cron("0 9 * * *", "daily", {}, timezone="Mars/Phobos")
    finally:
        scheduler.close()
