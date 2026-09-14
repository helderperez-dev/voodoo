"""Durable orchestration checkpoints for Voodoo Workflows.

Workflow persistence records orchestration progress only. Canonical Executions
remain owned by :class:`ExecutionEngine`; this module never executes work and
never creates a second execution lifecycle.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from voodoo.core.errors import ConfigurationError
from voodoo.runtime.store import acquire_runtime_store

__all__ = ["WorkflowStore", "VoodooStoreWorkflowStore"]

_PREFIX = b"voodoo:runtime:workflow:"
_TERMINAL = {"completed", "failed", "cancelled"}


class WorkflowStore(Protocol):
    """Durable checkpoint boundary for Workflow orchestration state."""

    def save(self, workflow_id: str, payload: dict[str, Any]) -> None: ...

    def load(self, workflow_id: str) -> dict[str, Any] | None: ...

    def load_unfinished(self) -> list[dict[str, Any]]: ...


class VoodooStoreWorkflowStore:
    """Persist Workflow checkpoints in the process-owned Voodoo Store."""

    provider = "voodoo"

    def __init__(self) -> None:
        self._runtime_store = acquire_runtime_store()
        provider = self._runtime_store.provider or self._runtime_store.start()
        if provider is None:
            raise ConfigurationError(
                "Workflow durability requires Voodoo Store to be enabled."
            )
        native = getattr(provider, "native", None)
        if native is None or not all(
            hasattr(native, name) for name in ("get", "put", "scan_prefix")
        ):
            raise ConfigurationError(
                "The active Voodoo Store binding does not expose the KV primitives "
                "required for Workflow checkpoints."
            )
        self._store = native

    @property
    def path(self):
        return self._runtime_store.config.path

    def save(self, workflow_id: str, payload: dict[str, Any]) -> None:
        body = dict(payload)
        body["workflow_id"] = workflow_id
        self._store.put(
            self._key(workflow_id),
            json.dumps(body, separators=(",", ":"), default=str).encode("utf-8"),
        )

    def load(self, workflow_id: str) -> dict[str, Any] | None:
        raw = self._store.get(self._key(workflow_id))
        if raw is None:
            return None
        return json.loads(bytes(raw).decode("utf-8"))

    def load_unfinished(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for _key, raw in self._store.scan_prefix(_PREFIX):
            payload = json.loads(bytes(raw).decode("utf-8"))
            if payload.get("status") not in _TERMINAL:
                records.append(payload)
        records.sort(key=lambda item: (item.get("updated_at", ""), item["workflow_id"]))
        return records

    def close(self) -> None:
        """No-op: RuntimeStore owns the shared Store lifecycle."""

    @staticmethod
    def _key(workflow_id: str) -> bytes:
        return _PREFIX + workflow_id.encode("utf-8")
