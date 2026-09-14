"""Stable protocol schemas for Voodoo Node fabric semantics.

These schemas describe membership and routed work without exposing Python Runtime
classes or a specific transport. They do not imply consensus, replication, or
global exactly-once execution.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

FABRIC_SCHEMA_VERSION = 1


class NodeAdvertisement(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: int = Field(default=FABRIC_SCHEMA_VERSION, ge=1)
    node_id: str = Field(min_length=1)
    runtime_version: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    resources: dict[str, Any] = Field(default_factory=dict)
    services: list[str] = Field(default_factory=list)
    location: str | None = None
    store_ownership: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class NodeMembership(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: int = Field(default=FABRIC_SCHEMA_VERSION, ge=1)
    node_id: str = Field(min_length=1)
    status: Literal["joining", "active", "suspect", "left"]
    advertisement: NodeAdvertisement
    joined_at: str
    last_seen_at: str
    updated_at: str


class FabricWorkRequest(BaseModel):
    """Transport-neutral request after the Runtime has selected a target node."""

    model_config = ConfigDict(extra="ignore")

    schema_version: int = Field(default=FABRIC_SCHEMA_VERSION, ge=1)
    work_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    required_capability: str | None = None
    attempt: int = Field(default=1, ge=1)
    source_node_id: str | None = None
    target_node_id: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class FabricWorkOutcome(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: int = Field(default=FABRIC_SCHEMA_VERSION, ge=1)
    work_id: str
    target_node_id: str
    execution_id: str | None = None
    status: Literal["completed", "failed", "rejected"]
    result: Any = None
    error: dict[str, Any] | None = None


FABRIC_PROTOCOL_ENTITIES = {
    "NodeAdvertisement": NodeAdvertisement,
    "NodeMembership": NodeMembership,
    "FabricWorkRequest": FabricWorkRequest,
    "FabricWorkOutcome": FabricWorkOutcome,
}

__all__ = [
    "FABRIC_SCHEMA_VERSION",
    "NodeAdvertisement",
    "NodeMembership",
    "FabricWorkRequest",
    "FabricWorkOutcome",
    "FABRIC_PROTOCOL_ENTITIES",
]
