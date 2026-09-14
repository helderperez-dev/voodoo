"""Voodoo Store-backed durable queue adapter.

Sprint 28.4 bridge between the framework-neutral ``VoodooQueue`` contract and
Voodoo Store durable Jobs. Store owns persistence, leasing and retry state;
the Runtime remains responsible for executing application code.

The adapter is capability-gated because the currently published Store 0.1.1
does not yet expose Jobs through its Python binding. A newer binding can be
used without changing application APIs.
"""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from voodoo.adapters.capabilities import QueueCapabilities
from voodoo.storage.queue.interfaces import QueueStats, TaskRecord, TaskStatus

if TYPE_CHECKING:
    from voodoo.runtime.store import RuntimeStore

_runtime_store: RuntimeStore | None = None


def bind_runtime_store(runtime_store: RuntimeStore | None) -> None:
    """Bind the application-owned RuntimeStore used by queue operations."""
    global _runtime_store
    _runtime_store = runtime_store


def _now_ms() -> int:
    return time.time_ns() // 1_000_000


def _datetime_from_ms(value: int | None) -> datetime | None:
    if value is None or value <= 0:
        return None
    return datetime.fromtimestamp(value / 1000, tz=UTC)


def _task_id(raw_id: bytes) -> int:
    return int.from_bytes(raw_id, "big", signed=False)


def _job_id(task_id: int) -> bytes:
    if task_id < 0 or task_id >= 1 << 128:
        raise ValueError("Voodoo Store task id must fit in 128 bits")
    return task_id.to_bytes(16, "big", signed=False)


def _native() -> Any:
    if _runtime_store is None:
        raise RuntimeError(
            "Voodoo Store queue is not bound to the application RuntimeStore"
        )
    provider = _runtime_store.provider or _runtime_store.start()
    if provider is None:
        raise RuntimeError("Voodoo Store is disabled")
    native = getattr(provider, "native", None)
    if native is None:
        raise RuntimeError("Active Store provider does not expose native storage")
    required = ("submit_job", "get_job", "claim_job", "complete_job", "fail_job")
    missing = [name for name in required if not hasattr(native, name)]
    if missing:
        raise RuntimeError(
            "Installed voodoo-store binding does not expose durable Jobs yet: "
            + ", ".join(missing)
        )
    return native


def _decode_payload(raw: bytes) -> Any:
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return raw


def _status(state: str) -> TaskStatus:
    return {
        "ready": TaskStatus.PENDING,
        "leased": TaskStatus.RUNNING,
        "completed": TaskStatus.COMPLETED,
        "dead": TaskStatus.FAILED,
        "cancelled": TaskStatus.FAILED,
    }[state]


class VoodooStoreQueue:
    """Durable queue implemented by Voodoo Store Jobs."""

    provider = "voodoo"

    def __init__(self) -> None:
        self._leases: dict[int, tuple[str, int]] = {}

    async def setup(self) -> None:
        _native()

    def _record(self, job: dict[str, Any], *, worker: str | None = None) -> TaskRecord:
        raw_id = bytes(job["id"])
        task_id = _task_id(raw_id)
        state = str(job["state"])
        handler = bytes(job["handler"]).decode("utf-8")
        available_at = _datetime_from_ms(int(job["available_at_ms"]))
        lease_until = _datetime_from_ms(int(job["lease_until_ms"]))
        idempotency = job.get("idempotency_key")
        return TaskRecord(
            id=task_id,
            type=handler,
            payload=_decode_payload(bytes(job["payload"])),
            status=_status(state),
            priority=int(job["priority"]),
            available_at=available_at,
            attempts=int(job["attempts"]),
            max_attempts=int(job["max_attempts"]),
            locked_by=worker if state == "leased" else None,
            locked_at=None,
            lease_until=lease_until,
            idempotency_key=(
                bytes(idempotency).decode("utf-8") if idempotency is not None else None
            ),
            trace_id=None,
            created_at=None,
            completed_at=None,
            last_error=None,
        )

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
        native = _native()
        now_ms = _now_ms()
        envelope = {"payload": payload, "trace_id": trace_id}
        encoded = json.dumps(envelope, separators=(",", ":"), default=str).encode()
        raw_id = bytes(
            native.submit_job(
                task_type.encode(),
                encoded,
                now_ms,
                available_at_ms=now_ms + max(0, int(delay * 1000)),
                priority=priority,
                max_attempts=max(1, max_attempts),
                idempotency_key=(
                    idempotency_key.encode() if idempotency_key is not None else None
                ),
            )
        )
        job = native.get_job(raw_id)
        if job is None:
            raise RuntimeError("Voodoo Store submitted a job that cannot be read back")
        record = self._record(job)
        # Preserve the existing queue API: payload is the user's payload while
        # trace metadata remains an infrastructure concern.
        return TaskRecord(**{**record.__dict__, "payload": payload, "trace_id": trace_id})

    async def claim(
        self,
        worker: str,
        *,
        types: Sequence[str] | None = None,
        lease_seconds: float = 60.0,
    ) -> TaskRecord | None:
        if types:
            raise NotImplementedError(
                "Voodoo Store handler-filtered claims are not exposed yet; "
                "the Runtime Store dispatcher must claim globally"
            )
        native = _native()
        job = native.claim_job(_now_ms(), max(1, int(lease_seconds * 1000)))
        if job is None:
            return None
        task_id = _task_id(bytes(job["id"]))
        generation = int(job["lease_generation"])
        self._leases[task_id] = (worker, generation)
        record = self._record(job, worker=worker)
        payload = record.payload
        trace_id = None
        if isinstance(payload, dict) and "payload" in payload:
            trace_id = payload.get("trace_id")
            payload = payload["payload"]
        return TaskRecord(**{**record.__dict__, "payload": payload, "trace_id": trace_id})

    def _lease_generation(self, task_id: int, worker: str) -> int | None:
        lease = self._leases.get(task_id)
        if lease is None or lease[0] != worker:
            return None
        return lease[1]

    async def heartbeat(
        self, task_id: int, worker: str, *, lease_seconds: float = 60.0
    ) -> bool:
        # Store Jobs currently use bounded leases; heartbeat extension will be
        # added with the native handler-filter/release surface.
        return self._lease_generation(task_id, worker) is not None

    async def complete(self, task_id: int, worker: str) -> bool:
        generation = self._lease_generation(task_id, worker)
        if generation is None:
            return False
        _native().complete_job(_job_id(task_id), generation, _now_ms())
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
        generation = self._lease_generation(task_id, worker)
        if generation is None:
            return None
        native = _native()
        native.fail_job(_job_id(task_id), generation, _now_ms(), error.encode())
        self._leases.pop(task_id, None)
        job = native.get_job(_job_id(task_id))
        return None if job is None else self._record(job)

    async def release(self, task_id: int, worker: str) -> bool:
        raise NotImplementedError("Voodoo Store explicit lease release is not exposed yet")

    async def release_expired(self) -> int:
        # Expired Store leases are reclaimed atomically by the next claim.
        return 0

    async def retry(self, task_id: int) -> TaskRecord | None:
        raise NotImplementedError("Voodoo Store manual retry is not exposed yet")

    async def list(
        self,
        *,
        status: TaskStatus | str | None = None,
        task_type: str | None = None,
        limit: int = 50,
    ) -> list[TaskRecord]:
        raise NotImplementedError("Voodoo Store job listing is not exposed yet")

    async def stats(self) -> QueueStats:
        raise NotImplementedError("Voodoo Store job statistics are not exposed yet")

    def capabilities(self) -> QueueCapabilities:
        return QueueCapabilities(
            provider=self.provider,
            durable=True,
            delivery="at_least_once",
            ordering="priority",
            visibility_timeout=True,
            delayed_delivery=True,
            priority=True,
            transactions=True,
        )
