"""Canonical remote-execution semantics for the Voodoo Mesh.

This module is deliberately transport-independent. WebSocket/JSON-RPC is only
one carrier for a :class:`RemoteExecutionRequest`; the semantic request is
normalized before it is allowed to reach application compute.

Sprint 26.1/26.2 does **not** claim authenticated remote identity. ``actor`` is
an asserted participant label until the trusted participant/session seam lands.
The runtime-facing actor is therefore namespaced as ``remote:<actor>`` so an
unverified network claim cannot be confused with a local actor identity.

Sprint 26.3 adds a server-side authority registry. Network payloads may identify
an asserted actor but they never carry authoritative capability grants. Those
are assigned by the receiving Voodoo node and injected into the canonical
ExecutionContext before capability/policy evaluation.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from voodoo.primitives.capability import Capability
from voodoo.primitives.intent import Intent
from voodoo.runtime.execution import Execution

REMOTE_SCHEMA_VERSION = 1


def normalize_remote_actor(actor: str) -> str:
    """Normalize an asserted participant label to the runtime remote namespace."""
    normalized = actor.strip() or "anonymous"
    if normalized.startswith("remote:"):
        return normalized
    return f"remote:{normalized}"


class RemoteExecutionRequest(BaseModel):
    """Transport-independent request to execute one exposed Mesh operation.

    Unknown transport fields are intentionally ignored. In particular, a
    caller cannot self-authorize by adding fields such as ``capabilities`` to
    the wire payload; authority is resolved exclusively by the receiving node.
    """

    model_config = ConfigDict(extra="ignore")

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
        return normalize_remote_actor(self.actor)

    @classmethod
    def from_jsonrpc(
        cls,
        params: Any,
        *,
        message_id: str | None = None,
    ) -> RemoteExecutionRequest:
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


@dataclass
class RemoteAuthorityRegistry:
    """Server-side capability assignment for remote participants.

    This is an authority seam, not an authentication system. Until Sprint 26.6
    binds actor labels to trusted sessions, grants are keyed by the asserted
    actor label. The important invariant introduced here is that grants can
    only originate on the receiving node; network request fields are never
    converted into runtime capabilities.
    """

    _grants: dict[str, dict[str, Capability]] = field(default_factory=dict)

    def grant(self, actor: str, *capabilities: str | Capability) -> None:
        """Grant one or more capabilities to a remote participant."""
        key = normalize_remote_actor(actor)
        bucket = self._grants.setdefault(key, {})
        for item in capabilities:
            capability = item if isinstance(item, Capability) else Capability(name=item)
            bucket[capability.name] = capability

    def revoke(self, actor: str, *capability_names: str) -> None:
        """Revoke named grants; with no names, revoke every grant for actor."""
        key = normalize_remote_actor(actor)
        if not capability_names:
            self._grants.pop(key, None)
            return
        bucket = self._grants.get(key)
        if bucket is None:
            return
        for name in capability_names:
            bucket.pop(name, None)
        if not bucket:
            self._grants.pop(key, None)

    def replace(self, actor: str, capabilities: Iterable[str | Capability]) -> None:
        """Replace the complete server-side authority set for one participant."""
        self.revoke(actor)
        self.grant(actor, *tuple(capabilities))

    def capabilities_for(self, actor: str) -> list[Capability]:
        """Return currently valid capability grants for an actor."""
        bucket = self._grants.get(normalize_remote_actor(actor), {})
        return [cap.model_copy(deep=True) for cap in bucket.values() if cap.valid]

    def names_for(self, actor: str) -> list[str]:
        return sorted(cap.name for cap in self.capabilities_for(actor))

    def describe(self) -> dict[str, list[str]]:
        return {
            actor: sorted(cap.name for cap in bucket.values() if cap.valid)
            for actor, bucket in sorted(self._grants.items())
        }


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

        intent = Intent(
            name=self.intent_name or f"mesh.call:{self.name}", params=params
        )
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
    ) -> RemoteExecutionOutcome:
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
    ) -> RemoteExecutionOutcome:
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
    "RemoteAuthorityRegistry",
    "ExposedOperation",
    "normalize_remote_actor",
]
