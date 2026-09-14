"""Voodoo Store implementation of the durable queue contract.

The Runtime owns the active Store lifecycle. This adapter projects native
Store Jobs into the existing :class:`VoodooQueue` API without exposing
``voodoo_store`` objects to application code or opening a second ``.vstore``.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from voodoo.adapters.capabilities import QueueCapabilities
from voodoo.core.errors import ConfigurationError
from voodoo.runtime.store import get_active_runtime_store
from voodoo.storage.queue.interfaces import QueueStats, TaskRecord, TaskStatus

_REQUIRED_JOB_API = (
    "submit_job",
    "get_job",
    "claim_job",
    "heartbeat_job",
    "complete_job",
    "fail_job",
    "release_job",
    "release_expired_jobs",
    "retry_job",
    "list_jobs",
    "job_stats",
    "job_history",
)


def _now_ms() -> int:
    return int(datetime.now(UTC).timestamp() * 1000)


def _from_ms(value: Any) -> datetime | None:
    if value is None:
        return None
    number = int(value)
    if number <= 0:
        return None
    return datetime.fromtimestamp(number / 1000, tz=UTC)


def _public_id(job_id: bytes) -> int:
    """Project a 128-bit Store JobId into the existing integer task API."""
    raw = bytes(job_id)
    if len(raw) != 16:
        raise ValueError("Voodoo Store job ids must be exactly 16 bytes")
    return int.from_bytes(raw, "big", signed=False)


def _native_id(task_id: int) -> bytes:
    if task_id < 0 or task_id >= 1 << 128:
        raise ValueError("task id is outside the 128-bit Voodoo Store job id range")
    return int(task_id).to_bytes(16, "big", signed=False)


def _status(job: dict[str, Any]) -> TaskStatus:
    state = str(job["state"])
    if state == "ready":
        return TaskStatus.RETRYING if int(job.get("attempts", 0)) > 0 else TaskStatus.PENDING
    if state == "leased":
        return TaskStatus.RUNNING
    if state == "completed":
        return TaskStatus.COMPLETED
    # The legacy TaskStatus surface has no cancelled state. Cancellation is a
    # terminal unsuccessful outcome, so it projects to FAILED together with
    # native dead-lettered jobs.
    return TaskStatus.FAILED


class VoodooStoreQueue:
    """Durable background work backed by the active Runtime Store."""

    provider = "voodoo"

    def __init__(self) -> None:
        self._native: Any | None = None
        self._leases: dict[int, tuple[str, int]] = {}

    async def setup(self) -> None:
        runtime_store = get_active_runtime_store()
        if runtime_store is None:
            raise ConfigurationError(
                "The 'voodoo' queue provider requires the active RuntimeStore. "
                "Start the queue inside the Voodoo application lifecycle."
            )
        provider = runtime_store.provider or runtime_store.start()
        if provider is None:
            raise ConfigurationError(
                "The 'voodoo' queue provider cannot run while Voodoo Store is disabled."
            )
        native = getattr(provider, "native", None)
        if native is None:
            raise ConfigurationError(
                "The active Store provider does not expose durable Jobs."
            )
        missing = [name for name in _REQUIRED_JOB_API if not hasattr(native, name)]
        if missing:
            names = ", ".join(missing)
            raise ConfigurationError(
                "The installed voodoo-store binding is too old for the native queue "
                f"provider; missing: {names}. Upgrade voodoo-store before setting "
                "queue.provider: voodoo."
            )
        self._native = native

    def _store(self) -> Any:
        if self._native is None:
            raise RuntimeError("VoodooStoreQueue.setup() must be called before use")
        return self._native

    async def enqueue(
        self,
        task_type: str,
        payload: Any,
        *,
        priority: int = 0,
        delay: float = 0.0,
        max_attempts: int = 1,
        idempotency_key: str | None = None,
        trace_id: str | None = None,
    ) -> TaskRecord:
        store = self._store()
        now_ms = _now_ms()
        available_at_ms = now_ms + max(0, int(delay * 1000))
        envelope = json.dumps(
            {"payload": payload, "trace_id": trace_id},
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        job_id = store.submit_job(
            task_type.encode("utf-8"),
            envelope,
            now_ms,
            available_at_ms=available_at_ms,
            priority=int(priority),
            max_attempts=max(1, int(max_attempts)),
            retry_backoff_ms=1_000,
            idempotency_key=(
                idempotency_key.encode("utf-8") if idempotency_key is not None else None
            ),
        )
        job = store.get_job(job_id)
        if job is None:  # pragma: no cover - native submit/get is atomic
            raise RuntimeError("Voodoo Store submitted a job that cannot be read back")
        return self._record(job)

    async def claim(
        self,
        worker: str,
        *,
        types: Sequence[str] | None = None,
        lease_seconds: float = 60.0,
    ) -> TaskRecord | None:
        store = self._store()
        handlers = [name.encode("utf-8") for name in types] if types else []
        job = store.claim_job(
            _now_ms(),
            max(1, int(lease_seconds * 1000)),
            handlers=handlers,
        )
        if job is None:
            return None
        task_id = _public_id(bytes(job["id"]))
        generation = int(job["lease_generation"])
        self._leases[task_id] = (worker, generation)
        return self._record(job, worker=worker)

    async def heartbeat(
        self, task_id: int, worker: str, *, lease_seconds: float = 60.0
    ) -> bool:
        lease = self._owned_lease(task_id, worker)
        if lease is None:
            return False
        ok = bool(
            self._store().heartbeat_job(
                _native_id(task_id),
                lease,
                _now_ms(),
                max(1, int(lease_seconds * 1000)),
            )
        )
        if not ok:
            self._leases.pop(task_id, None)
        return ok

    async def complete(self, task_id: int, worker: str) -> bool:
        generation = self._owned_lease(task_id, worker)
        if generation is None:
            return False
        try:
            self._store().complete_job(_native_id(task_id), generation, _now_ms())
        except Exception as exc:  # noqa: BLE001 - stale lease projects to False
            if "lease" in str(exc).lower() or "not found" in str(exc).lower():
                self._leases.pop(task_id, None)
                return False
            raise
        self._leases.pop(task_id, None)
        return True

    async def fail(
        self,
        task_id: int,
        worker: str,
        error: str,
        *,
        backoff_base: float = 1.0,
    ) -> TaskRecord | None:
        generation = self._owned_lease(task_id, worker)
        if generation is None:
            return None
        # Store Jobs persist retry policy at submit time. The current public
        # worker contract uses the same 1.0 second default, so native retry
        # timing remains equivalent while becoming process-crash durable.
        _ = backoff_base
        self._store().fail_job(
            _native_id(task_id), generation, _now_ms(), error.encode("utf-8")
        )
        self._leases.pop(task_id, None)
        job = self._store().get_job(_native_id(task_id))
        return self._record(job) if job is not None else None

    async def release(self, task_id: int, worker: str) -> bool:
        generation = self._owned_lease(task_id, worker)
        if generation is None:
            return False
        ok = bool(
            self._store().release_job(_native_id(task_id), generation, _now_ms())
        )
        if ok:
            self._leases.pop(task_id, None)
        return ok

    async def release_expired(self) -> int:
        now_ms = _now_ms()
        released = int(self._store().release_expired_jobs(now_ms))
        for task_id in tuple(self._leases):
            job = self._store().get_job(_native_id(task_id))
            if job is None or str(job["state"]) != "leased":
                self._leases.pop(task_id, None)
        return released

    async def retry(self, task_id: int) -> TaskRecord | None:
        job = self._store().retry_job(_native_id(task_id), _now_ms())
        return self._record(job) if job is not None else None

    async def list(
        self,
        *,
        status: TaskStatus | str | None = None,
        task_type: str | None = None,
        limit: int = 50,
    ) -> list[TaskRecord]:
        expected_status = TaskStatus(status) if status is not None else None
        records: list[TaskRecord] = []
        for job in self._store().list_jobs():
            record = self._record(job)
            if expected_status is not None and record.status != expected_status:
                continue
            if task_type is not None and record.type != task_type:
                continue
            records.append(record)
            if len(records) >= max(0, int(limit)):
                break
        return records

    async def stats(self) -> QueueStats:
        counts = {
            TaskStatus.PENDING: 0,
            TaskStatus.RUNNING: 0,
            TaskStatus.RETRYING: 0,
            TaskStatus.COMPLETED: 0,
            TaskStatus.FAILED: 0,
        }
        total = 0
        for job in self._store().list_jobs():
            total += 1
            counts[_status(job)] += 1
        return QueueStats(
            total=total,
            pending=counts[TaskStatus.PENDING],
            running=counts[TaskStatus.RUNNING],
            retrying=counts[TaskStatus.RETRYING],
            completed=counts[TaskStatus.COMPLETED],
            failed=counts[TaskStatus.FAILED],
        )

    def capabilities(self) -> QueueCapabilities:
        return QueueCapabilities(provider=self.provider)

    def _owned_lease(self, task_id: int, worker: str) -> int | None:
        lease = self._leases.get(task_id)
        if lease is None or lease[0] != worker:
            return None
        return lease[1]

    def _record(self, job: dict[str, Any], *, worker: str | None = None) -> TaskRecord:
        job_id = bytes(job["id"])
        task_id = _public_id(job_id)
        envelope = json.loads(bytes(job["payload"]).decode("utf-8"))
        history = self._store().job_history(job_id)
        created_at = None
        completed_at = None
        locked_at = None
        last_error = None
        for _sequence, at_ms, kind, detail in history:
            at = _from_ms(at_ms)
            if kind == "submitted" and created_at is None:
                created_at = at
            elif kind == "claimed":
                locked_at = at
            elif kind == "completed":
                completed_at = at
            elif kind in {"retry_scheduled", "dead"} and detail:
                last_error = bytes(detail).decode("utf-8", errors="replace")

        if worker is None:
            lease = self._leases.get(task_id)
            worker = lease[0] if lease is not None else None

        idempotency = job.get("idempotency_key")
        return TaskRecord(
            id=task_id,
            type=bytes(job["handler"]).decode("utf-8"),
            payload=envelope.get("payload"),
            status=_status(job),
            priority=int(job.get("priority", 0)),
            available_at=_from_ms(job.get("available_at_ms")),
            attempts=int(job.get("attempts", 0)),
            max_attempts=int(job.get("max_attempts", 1)),
            locked_by=worker,
            locked_at=locked_at if str(job["state"]) == "leased" else None,
            lease_until=_from_ms(job.get("lease_until_ms")),
            idempotency_key=(
                bytes(idempotency).decode("utf-8") if idempotency is not None else None
            ),
            trace_id=envelope.get("trace_id"),
            created_at=created_at,
            completed_at=completed_at,
            last_error=last_error,
        )


__all__ = ["VoodooStoreQueue", "_native_id", "_public_id"]
