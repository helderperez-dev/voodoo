"""Sprint 28.5 acceptance for the Runtime-owned Store scheduler bridge."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from voodoo.core.errors import ConfigurationError
from voodoo.runtime.scheduler import ScheduleService
from voodoo.storage.scheduler import store as scheduler_module
from voodoo.storage.scheduler.store import VoodooStoreScheduleStore


class _FakeNativeScheduler:
    def __init__(self) -> None:
        self.kv: dict[bytes, bytes] = {}
        self.schedules: dict[bytes, dict[str, Any]] = {}
        self.cron: dict[bytes, dict[str, Any]] = {}
        self.jobs: list[dict[str, Any]] = []
        self.next_id = 1

    def _id(self) -> bytes:
        value = self.next_id.to_bytes(16, "big")
        self.next_id += 1
        return value

    def get(self, key):
        return self.kv.get(bytes(key))

    def put(self, key, value):
        self.kv[bytes(key)] = bytes(value)

    def scan_prefix(self, prefix):
        return [
            (key, value)
            for key, value in sorted(self.kv.items())
            if key.startswith(bytes(prefix))
        ]

    def create_schedule(
        self,
        handler,
        payload,
        first_run_ms,
        *,
        mode="once",
        every_ms=None,
        **_kwargs,
    ):
        schedule_id = self._id()
        self.schedules[schedule_id] = {
            "id": schedule_id,
            "job": {"handler": bytes(handler), "payload": bytes(payload)},
            "mode": mode,
            "every_ms": every_ms,
            "next_run_ms": int(first_run_ms),
            "enabled": True,
        }
        return schedule_id

    def get_schedule(self, schedule_id):
        schedule = self.schedules.get(bytes(schedule_id))
        return dict(schedule) if schedule is not None else None

    def set_schedule_enabled(self, schedule_id, enabled):
        schedule = self.schedules.get(bytes(schedule_id))
        if schedule is None:
            return False
        schedule["enabled"] = bool(enabled)
        return True

    def tick_schedules(self, now_ms, limit):
        scanned = len(self.schedules)
        fired = 0
        for schedule in self.schedules.values():
            if fired >= limit:
                break
            if not schedule["enabled"] or schedule["next_run_ms"] > now_ms:
                continue
            self.jobs.append(dict(schedule["job"]))
            fired += 1
            if schedule["mode"] == "once":
                schedule["enabled"] = False
            else:
                every_ms = int(schedule["every_ms"])
                while schedule["next_run_ms"] <= now_ms:
                    schedule["next_run_ms"] += every_ms
        return scanned, fired

    def create_cron_schedule(self, expression, handler, payload, after_ms, **_kwargs):
        schedule_id = self._id()
        self.cron[schedule_id] = {
            "id": schedule_id,
            "expression": expression.encode("utf-8"),
            "job": {"handler": bytes(handler), "payload": bytes(payload)},
            "next_run_ms": int(after_ms) + 60_000,
            "enabled": True,
            "fire_count": 0,
            "last_fired_at_ms": None,
        }
        return schedule_id

    def get_cron_schedule(self, schedule_id):
        schedule = self.cron.get(bytes(schedule_id))
        return dict(schedule) if schedule is not None else None

    def set_cron_schedule_enabled(self, schedule_id, enabled):
        schedule = self.cron.get(bytes(schedule_id))
        if schedule is None:
            return False
        schedule["enabled"] = bool(enabled)
        return True

    def tick_cron_schedules(self, now_ms, limit):
        scanned = len(self.cron)
        fired = 0
        for schedule in self.cron.values():
            if fired >= limit:
                break
            if not schedule["enabled"] or schedule["next_run_ms"] > now_ms:
                continue
            self.jobs.append(dict(schedule["job"]))
            schedule["fire_count"] += 1
            schedule["last_fired_at_ms"] = schedule["next_run_ms"]
            schedule["next_run_ms"] += 60_000
            fired += 1
        return scanned, fired


class _Provider:
    def __init__(self, native) -> None:
        self.native = native


class _RuntimeStore:
    def __init__(self, native) -> None:
        self.provider = _Provider(native)

    def start(self):
        return self.provider


def _bind(monkeypatch, native):
    runtime = _RuntimeStore(native)
    monkeypatch.setattr(scheduler_module, "get_active_runtime_store", lambda: runtime)
    return runtime


def test_store_scheduler_requires_active_runtime_store(monkeypatch):
    monkeypatch.setattr(scheduler_module, "get_active_runtime_store", lambda: None)
    with pytest.raises(ConfigurationError, match="active application RuntimeStore"):
        VoodooStoreScheduleStore()


def test_store_scheduler_preserves_management_surface(monkeypatch):
    native = _FakeNativeScheduler()
    _bind(monkeypatch, native)
    store = VoodooStoreScheduleStore()
    now = datetime.now(UTC)

    store.create("s1", "once", "at", now.isoformat(), now, "email.send", {"x": 1})
    record = store.get("s1")
    assert record is not None
    assert record["id"] == "s1"
    assert record["task_type"] == "email.send"
    assert json.loads(record["payload"]) == {"x": 1}
    assert record["active"] == 1

    assert [item["id"] for item in store.list_all()] == ["s1"]
    assert store.pause("s1") is True
    assert store.get("s1")["active"] == 0
    assert store.resume("s1") is True
    assert store.get("s1")["active"] == 1


def test_timespec_interval_creates_native_interval_schedule(monkeypatch):
    from voodoo.primitives.time import TimeSpec

    native = _FakeNativeScheduler()
    _bind(monkeypatch, native)
    store = VoodooStoreScheduleStore()

    assert store.schedule_from_timespec(
        "interval-1", TimeSpec.with_interval(30), "heartbeat", {"ok": True}
    )
    record = store.get("interval-1")
    assert record["kind"] == "interval"
    assert record["spec"] == "30"
    native_schedule = next(iter(native.schedules.values()))
    assert native_schedule["mode"] == "interval"
    assert native_schedule["every_ms"] == 30_000


@pytest.mark.asyncio
async def test_native_tick_creates_job_without_framework_enqueue(monkeypatch):
    native = _FakeNativeScheduler()
    _bind(monkeypatch, native)
    store = VoodooStoreScheduleStore()
    due = datetime.now(UTC) - timedelta(seconds=1)
    store.create("native", "native", "at", due.isoformat(), due, "work", {"n": 1})

    service = ScheduleService(store)

    async def forbidden_fire(_schedule):
        raise AssertionError("Store-native schedule must not call Framework enqueue")

    monkeypatch.setattr(service, "_fire", forbidden_fire)
    assert await service.tick_once() == 1
    assert len(native.jobs) == 1
    envelope = json.loads(native.jobs[0]["payload"].decode("utf-8"))
    assert envelope == {"payload": {"n": 1}, "trace_id": None}
    assert store.get("native")["active"] == 0


@pytest.mark.asyncio
async def test_legacy_tick_still_fires_returned_due_records(monkeypatch):
    class LegacyStore:
        creates_jobs_natively = False

        def claim_due(self):
            return [{"id": "legacy"}]

    service = ScheduleService(LegacyStore())
    fired = []

    async def fake_fire(schedule):
        fired.append(schedule["id"])

    monkeypatch.setattr(service, "_fire", fake_fire)
    assert await service.tick_once() == 1
    assert fired == ["legacy"]
