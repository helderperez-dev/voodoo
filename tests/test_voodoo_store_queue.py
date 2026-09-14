"""Sprint 28.4 acceptance for the Runtime-owned Voodoo Store queue."""

from __future__ import annotations

from typing import Any

import pytest

from voodoo.core.errors import ConfigurationError
from voodoo.storage.queue import TaskStatus
from voodoo.storage.queue import voodoo as queue_module
from voodoo.storage.queue.voodoo import VoodooStoreQueue, _native_id, _public_id


class _FakeNativeJobs:
    def __init__(self) -> None:
        self.jobs: dict[bytes, dict[str, Any]] = {}
        self.history: dict[bytes, list[tuple[int, int, str, bytes]]] = {}
        self.next_id = 1

    def submit_job(
        self,
        handler,
        payload,
        now_ms,
        *,
        available_at_ms=0,
        deadline_ms=None,
        priority=0,
        max_attempts=3,
        retry_backoff_ms=1000,
        idempotency_key=None,
    ):
        if idempotency_key is not None:
            for job in self.jobs.values():
                if (
                    job["state"] in {"ready", "leased"}
                    and job["idempotency_key"] == idempotency_key
                ):
                    return job["id"]
        job_id = self.next_id.to_bytes(16, "big")
        self.next_id += 1
        self.jobs[job_id] = {
            "id": job_id,
            "state": "ready",
            "handler": bytes(handler),
            "payload": bytes(payload),
            "available_at_ms": int(available_at_ms),
            "deadline_ms": deadline_ms,
            "priority": int(priority),
            "attempts": 0,
            "max_attempts": int(max_attempts),
            "retry_backoff_ms": int(retry_backoff_ms),
            "lease_until_ms": 0,
            "lease_generation": 0,
            "idempotency_key": idempotency_key,
        }
        self.history[job_id] = [(0, int(now_ms), "submitted", b"")]
        return job_id

    def get_job(self, job_id):
        job = self.jobs.get(bytes(job_id))
        return dict(job) if job is not None else None

    def claim_job(self, now_ms, lease_duration_ms, *, handlers=()):
        candidates = []
        for job in self.jobs.values():
            if handlers and job["handler"] not in handlers:
                continue
            if job["state"] != "ready" or job["available_at_ms"] > now_ms:
                continue
            candidates.append(job)
        if not candidates:
            return None
        job = sorted(
            candidates,
            key=lambda item: (-item["priority"], item["available_at_ms"], item["id"]),
        )[0]
        job["attempts"] += 1
        job["state"] = "leased"
        job["lease_generation"] = job["attempts"]
        job["lease_until_ms"] = int(now_ms + lease_duration_ms)
        self._history(job, now_ms, "claimed")
        return dict(job)

    def heartbeat_job(self, job_id, generation, now_ms, lease_duration_ms):
        job = self.jobs.get(bytes(job_id))
        if (
            job is None
            or job["state"] != "leased"
            or job["lease_generation"] != generation
        ):
            return False
        job["lease_until_ms"] = int(now_ms + lease_duration_ms)
        return True

    def complete_job(self, job_id, generation, now_ms):
        job = self.jobs[bytes(job_id)]
        if job["state"] != "leased" or job["lease_generation"] != generation:
            raise RuntimeError("lease mismatch")
        job["state"] = "completed"
        job["lease_until_ms"] = 0
        self._history(job, now_ms, "completed")

    def fail_job(self, job_id, generation, now_ms, detail):
        job = self.jobs[bytes(job_id)]
        if job["state"] != "leased" or job["lease_generation"] != generation:
            raise RuntimeError("lease mismatch")
        job["lease_until_ms"] = 0
        if job["attempts"] >= job["max_attempts"]:
            job["state"] = "dead"
            self._history(job, now_ms, "dead", bytes(detail))
            return "dead"
        job["state"] = "ready"
        job["available_at_ms"] = int(
            now_ms + job["retry_backoff_ms"] * max(1, job["attempts"])
        )
        self._history(job, now_ms, "retry_scheduled", bytes(detail))
        return "ready"

    def release_job(self, job_id, generation, now_ms):
        job = self.jobs.get(bytes(job_id))
        if (
            job is None
            or job["state"] != "leased"
            or job["lease_generation"] != generation
        ):
            return False
        job["state"] = "ready"
        job["available_at_ms"] = int(now_ms)
        job["lease_until_ms"] = 0
        self._history(job, now_ms, "retry_scheduled", b"released")
        return True

    def release_expired_jobs(self, now_ms):
        released = 0
        for job in self.jobs.values():
            if job["state"] != "leased" or job["lease_until_ms"] > now_ms:
                continue
            released += 1
            job["lease_until_ms"] = 0
            if job["attempts"] >= job["max_attempts"]:
                job["state"] = "dead"
                self._history(job, now_ms, "dead", b"lease expired")
            else:
                job["state"] = "ready"
                job["available_at_ms"] = int(now_ms)
                self._history(job, now_ms, "retry_scheduled", b"lease expired")
        return released

    def retry_job(self, job_id, now_ms):
        job = self.jobs.get(bytes(job_id))
        if job is None or job["state"] != "dead":
            return None
        job["state"] = "ready"
        job["attempts"] = 0
        job["lease_generation"] = 0
        job["lease_until_ms"] = 0
        job["available_at_ms"] = int(now_ms)
        self._history(job, now_ms, "retry_scheduled", b"manual retry")
        return dict(job)

    def list_jobs(self):
        return [dict(job) for job in self.jobs.values()]

    def job_stats(self):
        return {"total": len(self.jobs)}

    def job_history(self, job_id):
        return list(self.history.get(bytes(job_id), ()))

    def _history(self, job, at_ms, kind, detail=b""):
        entries = self.history[job["id"]]
        entries.append((len(entries), int(at_ms), kind, bytes(detail)))


class _Provider:
    def __init__(self, native) -> None:
        self.native = native


class _RuntimeStore:
    def __init__(self, native) -> None:
        self.provider = _Provider(native)
        self.start_calls = 0

    def start(self):
        self.start_calls += 1
        return self.provider


@pytest.mark.asyncio
async def test_queue_requires_active_runtime_store(monkeypatch):
    monkeypatch.setattr(queue_module, "get_active_runtime_store", lambda: None)
    queue = VoodooStoreQueue()
    with pytest.raises(ConfigurationError, match="active RuntimeStore"):
        await queue.setup()


@pytest.mark.asyncio
async def test_queue_reuses_active_store_and_preserves_public_task_api(monkeypatch):
    native = _FakeNativeJobs()
    runtime = _RuntimeStore(native)
    monkeypatch.setattr(queue_module, "get_active_runtime_store", lambda: runtime)
    queue = VoodooStoreQueue()
    await queue.setup()

    task = await queue.enqueue(
        "email.send",
        {"to": "ada@example.com"},
        priority=7,
        max_attempts=2,
        idempotency_key="email:ada:1",
        trace_id="trace-1",
    )
    assert task.id == 1
    assert task.type == "email.send"
    assert task.payload == {"to": "ada@example.com"}
    assert task.trace_id == "trace-1"
    assert task.status is TaskStatus.PENDING
    assert runtime.start_calls == 0

    duplicate = await queue.enqueue(
        "email.send",
        {"to": "ada@example.com"},
        idempotency_key="email:ada:1",
    )
    assert duplicate.id == task.id

    assert await queue.claim("report-worker", types=("report.build",)) is None
    claimed = await queue.claim("email-worker", types=("email.send",), lease_seconds=30)
    assert claimed is not None
    assert claimed.id == task.id
    assert claimed.status is TaskStatus.RUNNING
    assert claimed.locked_by == "email-worker"
    assert claimed.attempts == 1
    assert await queue.heartbeat(claimed.id, "other-worker") is False
    assert await queue.heartbeat(claimed.id, "email-worker", lease_seconds=60) is True

    failed = await queue.fail(claimed.id, "email-worker", "temporary")
    assert failed is not None
    assert failed.status is TaskStatus.RETRYING
    assert failed.last_error == "temporary"

    stats = await queue.stats()
    assert stats.total == 1
    assert stats.retrying == 1


@pytest.mark.asyncio
async def test_queue_completion_release_reaper_and_manual_retry(monkeypatch):
    native = _FakeNativeJobs()
    runtime = _RuntimeStore(native)
    monkeypatch.setattr(queue_module, "get_active_runtime_store", lambda: runtime)
    queue = VoodooStoreQueue()
    await queue.setup()

    first = await queue.enqueue("work", {"n": 1}, max_attempts=2)
    claimed = await queue.claim("worker", types=("work",), lease_seconds=30)
    assert claimed is not None
    assert await queue.release(first.id, "worker") is True

    claimed = await queue.claim("worker", types=("work",), lease_seconds=30)
    assert claimed is not None
    assert await queue.complete(first.id, "worker") is True
    completed = await queue.list(status=TaskStatus.COMPLETED)
    assert [task.id for task in completed] == [first.id]

    second = await queue.enqueue("work", {"n": 2}, max_attempts=1)
    claimed_second = await queue.claim("worker-2", types=("work",), lease_seconds=1)
    assert claimed_second is not None
    native.jobs[_native_id(second.id)]["lease_until_ms"] = 0
    assert await queue.release_expired() == 1
    failed = await queue.list(status=TaskStatus.FAILED)
    assert [task.id for task in failed] == [second.id]

    retried = await queue.retry(second.id)
    assert retried is not None
    assert retried.status is TaskStatus.PENDING
    assert retried.attempts == 0


def test_store_job_ids_round_trip_through_public_integer_surface():
    values = [0, 1, 2**64, (1 << 128) - 1]
    for value in values:
        assert _public_id(_native_id(value)) == value
