"""Durable execution persistence and recovery (Phase 11).

Execution state should be recoverable: a long-running workflow must
survive process restarts, worker restarts and temporary provider
failures.

The engine checkpoints every execution when it reaches an interesting
state (terminal or waiting) into an :class:`ExecutionStore`.
:class:`JSONFileExecutionStore` is the default durable implementation —
an append-only JSONL file of serialized executions. After a restart,
``engine.recover()`` reloads unfinished executions (``waiting`` /
``running`` / ``created``) so they remain inspectable and resumable
(e.g. pending human approvals survive the restart).

The architecture does not assume in-memory-only execution forever:
swapping in a database-backed store is a matter of implementing the
same three methods.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Protocol

from voodoo.runtime.execution import Execution, ExecutionStatus
from voodoo.security.redaction import redact_string

logger = logging.getLogger(__name__)

__all__ = ["ExecutionStore", "InMemoryExecutionStore", "JSONFileExecutionStore"]

# JSONL records are append-only and may outlive a framework process.  Keep an
# explicit envelope marker so readers can reject records they cannot safely
# interpret while still accepting pre-versioned (legacy) lines.
_SCHEMA_KEY = "_schema_version"
_SCHEMA_VERSION = 1

#: States considered unfinished (resumable) after a restart.
UNFINISHED_STATUSES = (
    ExecutionStatus.CREATED,
    ExecutionStatus.PLANNED,
    ExecutionStatus.AUTHORIZED,
    ExecutionStatus.RUNNING,
    ExecutionStatus.WAITING,
)


class ExecutionStore(Protocol):
    """The persistence seam for executions."""

    def save(self, execution: Execution) -> None: ...

    def load_all(self) -> list[Execution]: ...


class InMemoryExecutionStore:
    """Non-durable store — useful for tests and single-process workflows."""

    def __init__(self) -> None:
        self.records: dict[str, Execution] = {}

    def save(self, execution: Execution) -> None:
        self.records[execution.id] = execution

    def load_all(self) -> list[Execution]:
        return list(self.records.values())


class JSONFileExecutionStore:
    """Durable append-only JSONL store of serialized executions."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, execution: Execution) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(_safe_json(execution) + "\n")

    def load_all(self) -> list[Execution]:
        if not self.path.exists():
            return []
        executions: list[Execution] = []
        with self.path.open(encoding="utf-8") as fh:
            for line_number, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    executions.append(_decode_execution(line))
                except ValueError as error:
                    if str(error).startswith(
                        "unsupported execution persistence schema version"
                    ):
                        # A future durable schema must stop recovery rather
                        # than silently omitting state from a mixed-version
                        # deployment.
                        raise
                    logger.warning(
                        "execution persistence record could not be decoded line=%s error=%s",
                        line_number,
                        redact_string(str(error)),
                    )
                    continue
                except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as error:
                    logger.warning(
                        "execution persistence record could not be decoded line=%s error=%s",
                        line_number,
                        redact_string(str(error)),
                    )
                    continue
        return executions

    def load_latest(self) -> dict[str, Execution]:
        """Latest version of each execution (last write wins)."""
        latest: dict[str, Execution] = {}
        for ex in self.load_all():
            latest[ex.id] = ex
        return latest


def _safe_json(execution: Execution) -> str:
    """Serialize an execution, degrading non-JSON results to strings."""
    data = execution.model_dump(mode="json")
    data[_SCHEMA_KEY] = _SCHEMA_VERSION
    try:
        return json.dumps(data, default=str)
    except (TypeError, ValueError):
        data["result"] = str(execution.result)
        return json.dumps(data, default=str)


def _decode_execution(raw: str) -> Execution:
    """Decode a versioned execution record, accepting legacy JSONL lines."""
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("execution persistence record must be a JSON object")
    version = payload.pop(_SCHEMA_KEY, 0)
    if isinstance(version, bool) or not isinstance(version, int):
        raise ValueError("execution persistence schema version must be an integer")
    if version > _SCHEMA_VERSION:
        raise ValueError(
            f"unsupported execution persistence schema version: {version}"
        )
    return Execution.model_validate(payload)


def filter_unfinished(executions: list[Execution]) -> list[Execution]:
    """Return only executions whose latest state is unfinished."""
    return [e for e in executions if e.status in UNFINISHED_STATUSES]
