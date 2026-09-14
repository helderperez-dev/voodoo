"""Durable orchestration checkpoints for Voodoo Workflows.

Workflow persistence records orchestration progress only. Canonical Executions
remain owned by :class:`ExecutionEngine`; this module never executes work and
never creates a second execution lifecycle.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from voodoo.runtime.store import RuntimeStore

__all__ = ["WorkflowStore", "VoodooStoreWorkflowStore"]

_PREFIX = b"runtime:workflows:checkpoint:"
_TERMINAL = {"completed", "failed", "cancelled"}


class WorkflowStore(Protocol):
    """Durable checkpoint boundary for Workflow orchestration state."""

    def save(self, workflow_id: str, payload: dict[str, Any]) -> None: ...

    def load(self, workflow_id: str) -> dict[str, Any] | None: ...

    def load_unfinished(self) -> list[dict[str, Any]]: ...


class VoodooStoreWorkflowStore:
    """Workflow checkpoints backed by the Runtime-owned Voodoo Store."""

    provider = "voodoo"

    def __init__(self, runtime_store: RuntimeStore | None = None) -> None:
        self._runtime_store = runtime_store

    def _runtime(self) -> RuntimeStore:
        if self._runtime_store is not None:
            return self._runtime_store
        from voodoo.runtime.store import acquire_runtime_store

        return acquire_runtime_store()

    def _store(self) -> Any:
        runtime = self._runtime()
        provider = runtime.provider or runtime.start()
        if provider is None:
            from voodoo.core.errors import ConfigurationError

            raise ConfigurationError(
                "Voodoo Store is disabled; durable Workflow checkpoints require "
                "an explicit WorkflowStore adapter or an enabled Runtime Store."
            )
        native = getattr(provider, "native", None)
        if native is None:
            from voodoo.core.errors import ConfigurationError

            raise ConfigurationError(
                "The active Voodoo Store provider does not expose durable KV storage."
            )
        return native

    @property
    def path(self):
        return self._runtime().config.path

    def save(self, workflow_id: str, payload: dict[str, Any]) -> None:
        body = dict(payload)
        body["workflow_id"] = workflow_id
        self._store().put(
            self._key(workflow_id),
            json.dumps(body, separators=(",", ":"), sort_keys=True, default=str).encode(
                "utf-8"
            ),
        )

    def load(self, workflow_id: str) -> dict[str, Any] | None:
        raw = self._store().get(self._key(workflow_id))
        if raw is None:
            return None
        return json.loads(bytes(raw).decode("utf-8"))

    def load_unfinished(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for _key, raw in self._store().scan_prefix(_PREFIX):
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
