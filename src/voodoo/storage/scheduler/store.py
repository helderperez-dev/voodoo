"""Voodoo Store-backed durable scheduler adapter.

The adapter preserves the existing Framework schedule-management surface while
letting Store own the critical temporal-work transition. Native Store ticks
advance schedule/cron state and create the durable Job themselves, so the
Runtime must not enqueue the same occurrence a second time.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from voodoo.core.errors import ConfigurationError
from voodoo.runtime.store import get_active_runtime_store

_META_PREFIX = b"voodoo:scheduler:meta:"
_REQUIRED_API = (
    "create_schedule",
    "get_schedule",
    "set_schedule_enabled",
    "tick_schedules",
    "create_cron_schedule",
    "get_cron_schedule",
    "set_cron_schedule_enabled",
    "tick_cron_schedules",
)


def _now_ms() -> int:
    return int(datetime.now(UTC).timestamp() * 1000)


def _to_ms(value: datetime) -> int:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return int(value.timestamp() * 1000)


def _from_ms(value: int | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(int(value) / 1000, tz=UTC)


def _metadata_key(schedule_id: str) -> bytes:
    digest = hashlib.sha256(schedule_id.encode("utf-8")).hexdigest().encode("ascii")
    return _META_PREFIX + digest


def _job_payload(payload: Any) -> bytes:
    return json.dumps(
        {"payload": payload, "trace_id": None}, separators=(",", ":"), default=str
    ).encode("utf-8")


class VoodooStoreScheduleStore:
    """Framework schedule facade over the active application RuntimeStore."""

    provider = "voodoo"
    creates_jobs_natively = True

    def __init__(self) -> None:
        runtime_store = get_active_runtime_store()
        if runtime_store is None:
            raise ConfigurationError(
                "The Voodoo Store scheduler requires the active application RuntimeStore."
            )
        provider = runtime_store.provider or runtime_store.start()
        if provider is None:
            raise ConfigurationError(
                "The Voodoo Store scheduler cannot run while Store is disabled."
            )
        native = getattr(provider, "native", None)
        if native is None:
            raise ConfigurationError(
                "The active Store provider does not expose native scheduler storage."
            )
        missing = [name for name in _REQUIRED_API if not hasattr(native, name)]
        if missing:
            raise ConfigurationError(
                "The installed voodoo-store binding is too old for the native "
                "scheduler; missing: " + ", ".join(missing)
            )
        self._store = native

    def create(
        self,
        schedule_id: str,
        name: str,
        kind: str,
        spec: str,
        next_run_at: datetime,
        task_type: str,
        payload: Any = None,
    ) -> None:
        """Create a Framework schedule backed by a native Store schedule."""
        existing = self.get(schedule_id)
        if existing is not None:
            raise ValueError(f"schedule {schedule_id!r} already exists")

        encoded_payload = _job_payload(payload)
        first_run_ms = _to_ms(next_run_at)
        if kind == "cron":
            native_id = bytes(
                self._store.create_cron_schedule(
                    spec,
                    task_type.encode("utf-8"),
                    encoded_payload,
                    first_run_ms - 1,
                    max_attempts=1,
                )
            )
            native_kind = "cron"
        elif kind in {"at", "after"}:
            native_id = bytes(
                self._store.create_schedule(
                    task_type.encode("utf-8"),
                    encoded_payload,
                    first_run_ms,
                    mode="once",
                    max_attempts=1,
                )
            )
            native_kind = "schedule"
        elif kind == "interval":
            every_ms = max(1, int(float(spec) * 1000))
            native_id = bytes(
                self._store.create_schedule(
                    task_type.encode("utf-8"),
                    encoded_payload,
                    first_run_ms,
                    mode="interval",
                    every_ms=every_ms,
                    max_attempts=1,
                )
            )
            native_kind = "schedule"
        else:
            raise ValueError(f"unsupported schedule kind: {kind!r}")

        metadata = {
            "id": schedule_id,
            "name": name,
            "kind": kind,
            "spec": spec,
            "task_type": task_type,
            "payload": payload,
            "native_kind": native_kind,
            "native_id": native_id.hex(),
            "created_at": datetime.now(UTC).isoformat(),
        }
        self._store.put(
            _metadata_key(schedule_id),
            json.dumps(metadata, separators=(",", ":"), default=str).encode("utf-8"),
        )

    def get(self, schedule_id: str) -> dict[str, Any] | None:
        metadata = self._read_metadata(schedule_id)
        if metadata is None:
            return None
        native = self._get_native(metadata)
        if native is None:
            return None
        return self._record(metadata, native)

    def list_all(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for _key, raw in self._store.scan_prefix(_META_PREFIX):
            metadata = json.loads(bytes(raw).decode("utf-8"))
            native = self._get_native(metadata)
            if native is not None:
                records.append(self._record(metadata, native))
        records.sort(key=lambda record: record["created_at"])
        return records

    def pause(self, schedule_id: str) -> bool:
        metadata = self._read_metadata(schedule_id)
        if metadata is None:
            return False
        return self._set_enabled(metadata, False)

    def resume(self, schedule_id: str, next_run_at: datetime | None = None) -> bool:
        metadata = self._read_metadata(schedule_id)
        if metadata is None:
            return False
        if next_run_at is not None:
            # Current native Store binding can enable/disable a schedule but
            # cannot yet reposition an existing cursor. Refuse rather than
            # silently changing the semantics of the public API.
            current = self._get_native(metadata)
            current_next = (
                None if current is None else _from_ms(current.get("next_run_ms"))
            )
            if current_next != next_run_at:
                raise ConfigurationError(
                    "The active voodoo-store binding cannot reposition an existing "
                    "schedule cursor yet. Upgrade the Store binding before using "
                    "resume(..., next_run_at=...)."
                )
        return self._set_enabled(metadata, True)

    def schedule_from_timespec(
        self,
        schedule_id: str,
        time_spec: Any,
        task_type: str,
        payload: Any = None,
    ) -> bool:
        record = time_spec.to_schedule_record(schedule_id, task_type)
        if record is None:
            return False
        self.create(
            schedule_id=schedule_id,
            name=record["name"],
            kind=record["kind"],
            spec=record["spec"],
            next_run_at=record["next_run_at"],
            task_type=task_type,
            payload=payload,
        )
        return True

    def tick(self, now: datetime | None = None, *, limit: int = 100) -> int:
        """Advance native schedules and atomically create their durable Jobs."""
        now_ms = _to_ms(now or datetime.now(UTC))
        _scanned, scheduled = self._store.tick_schedules(now_ms, limit)
        remaining = max(0, limit - int(scheduled))
        _cron_scanned, cron = self._store.tick_cron_schedules(now_ms, remaining)
        return int(scheduled) + int(cron)

    def close(self) -> None:
        """No-op: RuntimeStore owns the shared native Store lifecycle."""

    def _read_metadata(self, schedule_id: str) -> dict[str, Any] | None:
        raw = self._store.get(_metadata_key(schedule_id))
        if raw is None:
            return None
        metadata = json.loads(bytes(raw).decode("utf-8"))
        if metadata.get("id") != schedule_id:
            raise RuntimeError("Voodoo Store scheduler metadata hash collision")
        return metadata

    def _get_native(self, metadata: dict[str, Any]) -> dict[str, Any] | None:
        native_id = bytes.fromhex(metadata["native_id"])
        if metadata["native_kind"] == "cron":
            return self._store.get_cron_schedule(native_id)
        return self._store.get_schedule(native_id)

    def _set_enabled(self, metadata: dict[str, Any], enabled: bool) -> bool:
        native_id = bytes.fromhex(metadata["native_id"])
        if metadata["native_kind"] == "cron":
            return bool(self._store.set_cron_schedule_enabled(native_id, enabled))
        return bool(self._store.set_schedule_enabled(native_id, enabled))

    def _record(
        self, metadata: dict[str, Any], native: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "id": metadata["id"],
            "name": metadata["name"],
            "kind": metadata["kind"],
            "spec": metadata["spec"],
            "next_run_at": _from_ms(native.get("next_run_ms")).isoformat(),
            "last_run_at": (
                _from_ms(native.get("last_fired_at_ms")).isoformat()
                if native.get("last_fired_at_ms") is not None
                else None
            ),
            "task_type": metadata["task_type"],
            "payload": (
                json.dumps(metadata["payload"])
                if metadata.get("payload") is not None
                else None
            ),
            "active": 1 if native.get("enabled") else 0,
            "created_at": metadata["created_at"],
        }


__all__ = ["VoodooStoreScheduleStore"]
