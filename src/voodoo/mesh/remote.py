"""Canonical remote-execution semantics for the Voodoo Mesh.

This module is deliberately transport-independent. WebSocket/JSON-RPC is only
one carrier for a :class:`RemoteExecutionRequest`; the semantic request is
normalized before it is allowed to reach application compute.

Sprint 26.1/26.2 does **not** claim authenticated remote identity. ``actor`` is
an asserted participant label until the trusted participant/session seam lands.
The runtime-facing actor is therefore namespaced as ``remote:<actor>`` so an
unverified network claim cannot be confused with a local actor identity.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from voodoo.primitives.intent import Intent
from voodoo.runtime.execution import Execution

REMOTE_SCHEMA_VERSION = 1


class RemoteExecutionRequest(BaseModel):
    """Transport-independent request to execute one exposed Mesh operation."""

    schema_version: int = Field(default=REMOTE_SCHEMA_VERSION, ge=1)
    request_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    operation: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
    actor: str = Field(default="anonymous", min_length=1)
    correlation_id: str | None = None
    parent_execution_id: str | None = None
    target_entity_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def runtime_actor(self) -> str:
        """Return an explicitly untrusted runtime actor label for this request."""
        actor = self.actor.strip() or "anonymous"
        if actor.startswith("remote:"):
            return actor
        return f"remote:{actor}"

    @classmethod
    def from_jsonrpc(
        cls,
        params: Any,
        *,
        message_id: str | None = None,
    ) -> "RemoteExecutionRequest":
        """Normalize canonical or legacy Mesh JSON-RPC ``call`` parameters.

        Legacy callers send ``{"name": ..., "arguments": ...}``. New callers
        may send ``operation`` plus lineage/actor metadata. In both cases the
        result is the same semantic request before application code is touched.
        """
        if not isinstance(params, dict):
            raise ValueError("Mesh call params must be an object")

        operation = params.get("operation", params.get("name"))
        if not isinstance(operation, str) or not operation.strip():
            raise ValueError("Mesh call requires a non-empty operation/name")

        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            raise ValueError("Mesh call arguments must be an object")

        raw_metadata = params.get("metadata", {})
        if raw_metadata is None:
            raw_metadata = {}
        if not isinstance(raw_metadata, dict):
            raise ValueError("Mesh call metadata must be an object")

        request_id = params.get("request_id") or message_id or str(uuid4())
        actor = params.get("actor") or params.get("source") or "anonymous"

        return cls(
            schema_version=params.get("schema_version", REMOTE_SCHEMA_VERSION),
            request_id=str(request_id),
            operation=operation.strip(),
            arguments=dict(arguments),
            actor=str(actor),
            correlation_id=(
                str(params["correlation_id"])
                if params.get("correlation_id") is not None
                else None
            ),
            parent_execution_id=(
                str(params["parent_execution_id"])
                if params.get("parent_execution_id") is not None
                else None
            ),
            target_entity_id=(
                str(params["target_entity_id"])
                if params.get("target_entity_id") is not None
                else None
            ),
            metadata=dict(raw_metadata),
        )


@dataclass(frozen=True)
class ExposedOperation:
    """Semantic registration metadata for a remotely callable operation."""

    name: str
    func: Callable[..., Any]
    capability: str | None = None
    intent_name: str | None = None
    description: str | None = None

    def intent_for(self, request: RemoteExecutionRequest) -> Intent:
        """Build the canonical Intent used by the Runtime for this request."""
        params: dict[str, Any] = {
            "arguments": dict(request.arguments),
            "_remote_request_id": request.request_id,
            "_remote_actor_asserted": request.actor,
        }
        if request.correlation_id is not None:
            params["_remote_correlation_id"] = request.correlation_id
        if request.parent_execution_id is not None:
            params["_remote_parent_execution_id"] = request.parent_execution_id
        if request.target_entity_id is not None:
            # Existing contextual Policy resolves this key before compute.
            params["_target_entity_id"] = request.target_entity_id
        if request.metadata:
            params["_remote_metadata"] = dict(request.metadata)

        intent = Intent(name=self.intent_name or f"mesh.call:{self.name}", params=params)
        if self.capability is not None:
            intent.require(self.capability)
        return intent


class RemoteExecutionOutcome(BaseModel):
    """Protocol projection of one governed remote request.

    ``Execution`` remains the source of truth. This object only carries enough
    information for the transport/client boundary to correlate the request with
    the canonical runtime lifecycle.
    """

    schema_version: int = Field(default=REMOTE_SCHEMA_VERSION, ge=1)
    request_id: str
    correlation_id: str | None = None
    execution_id: str | None = None
    trace_id: str | None = None
    status: str
    result: Any = None
    error: dict[str, Any] | None = None

    @classmethod
    def from_execution(
        cls,
        request: RemoteExecutionRequest,
        execution: Execution,
        *,
        error: dict[str, Any] | None = None,
    ) -> "RemoteExecutionOutcome":
        return cls(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            execution_id=execution.id,
            trace_id=execution.trace_id,
            status=execution.status.value,
            result=execution.result,
            error=error,
        )

    @classmethod
    def rejected(
        cls,
        request: RemoteExecutionRequest,
        *,
        error_type: str,
        message: str,
    ) -> "RemoteExecutionOutcome":
        return cls(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            status="rejected",
            error={"type": error_type, "message": message},
        )

    def transport_metadata(self) -> dict[str, Any]:
        """Small JSON-safe metadata projection for compatibility transports."""
        return {
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "execution_id": self.execution_id,
            "trace_id": self.trace_id,
            "status": self.status,
        }


__all__ = [
    "REMOTE_SCHEMA_VERSION",
    "RemoteExecutionRequest",
    "RemoteExecutionOutcome",
    "ExposedOperation",
]
