"""Durable Voodoo Node membership semantics.

Authentication establishes who a node is. Membership records whether that
node currently belongs to a Runtime fabric and what it advertises. Advertised
capabilities are descriptive placement metadata only; they never become
Capability grants.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from voodoo.runtime.identity import IdentityKind, Principal
from voodoo.runtime.store import (
    RuntimeStore,
    StoreProviderError,
    get_active_runtime_store,
)

__all__ = [
    "MemberStatus",
    "NodeAdvertisement",
    "NodeMembership",
    "VoodooStoreMembershipStore",
]

_MEMBERSHIP_PREFIX = b"runtime:membership:node:"
_MEMBERSHIP_COLLECTION = b"runtime.membership"
_SCHEMA_KEY = "_schema_version"
_SCHEMA_VERSION = 1


def _now() -> datetime:
    return datetime.now(UTC)


class MemberStatus(StrEnum):
    JOINING = "joining"
    ACTIVE = "active"
    SUSPECT = "suspect"
    LEFT = "left"


@dataclass(frozen=True, slots=True)
class NodeAdvertisement:
    """Descriptive node placement/health metadata, never authority."""

    runtime_version: str | None = None
    capabilities: tuple[str, ...] = ()
    resources: dict[str, Any] = field(default_factory=dict)
    services: tuple[str, ...] = ()
    location: str | None = None
    store_ownership: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def describe(self) -> dict[str, Any]:
        return {
            "runtime_version": self.runtime_version,
            "capabilities": list(self.capabilities),
            "resources": dict(self.resources),
            "services": list(self.services),
            "location": self.location,
            "store_ownership": list(self.store_ownership),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> NodeAdvertisement:
        return cls(
            runtime_version=record.get("runtime_version"),
            capabilities=tuple(record.get("capabilities") or ()),
            resources=dict(record.get("resources") or {}),
            services=tuple(record.get("services") or ()),
            location=record.get("location"),
            store_ownership=tuple(record.get("store_ownership") or ()),
            metadata=dict(record.get("metadata") or {}),
        )


@dataclass(frozen=True, slots=True)
class NodeMembership:
    node_id: str
    status: MemberStatus
    advertisement: NodeAdvertisement
    joined_at: datetime
    last_seen_at: datetime
    updated_at: datetime

    @property
    def active(self) -> bool:
        return self.status is MemberStatus.ACTIVE

    def describe(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "status": self.status.value,
            "advertisement": self.advertisement.describe(),
            "joined_at": self.joined_at.isoformat(),
            "last_seen_at": self.last_seen_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> NodeMembership:
        version = record.pop(_SCHEMA_KEY, 0)
        if isinstance(version, bool) or not isinstance(version, int):
            raise ValueError("membership schema version must be an integer")
        if version > _SCHEMA_VERSION:
            raise ValueError(f"unsupported membership schema version: {version}")
        return cls(
            node_id=str(record["node_id"]),
            status=MemberStatus(record["status"]),
            advertisement=NodeAdvertisement.from_record(record["advertisement"]),
            joined_at=datetime.fromisoformat(record["joined_at"]),
            last_seen_at=datetime.fromisoformat(record["last_seen_at"]),
            updated_at=datetime.fromisoformat(record["updated_at"]),
        )


class VoodooStoreMembershipStore:
    """Persist node membership in the Runtime-owned application Store."""

    def __init__(self, runtime_store: RuntimeStore | None = None) -> None:
        self.runtime_store = runtime_store or get_active_runtime_store()
        if self.runtime_store is None:
            raise StoreProviderError("No active RuntimeStore for node membership")
        provider = self.runtime_store.provider
        if provider is None or not provider.opened:
            raise StoreProviderError("RuntimeStore must be started for node membership")
        if provider.name != "voodoo":
            raise StoreProviderError(
                "VoodooStoreMembershipStore requires the Voodoo Store provider"
            )
        self._native: Any = getattr(provider, "native", None)
        if self._native is None:
            raise StoreProviderError("Active Voodoo Store has no native handle")

    @staticmethod
    def _native_collections(store: Any) -> bool:
        return all(
            hasattr(store, method)
            for method in (
                "create_collection",
                "upsert_record",
                "get_record",
                "scan_collection",
            )
        )

    def _ensure_collection(self) -> None:
        if self._native_collections(self._native):
            self._native.create_collection(
                _MEMBERSHIP_COLLECTION, schema_version=1, codec=b"json"
            )

    @staticmethod
    def _key(node_id: str) -> bytes:
        return _MEMBERSHIP_PREFIX + node_id.encode("utf-8")

    @staticmethod
    def _require_node(principal: Principal) -> None:
        if not principal.authenticated:
            raise PermissionError("Node membership requires an authenticated Principal")
        if principal.kind is not IdentityKind.NODE:
            raise PermissionError("Only node identities may join Runtime membership")

    def _save(self, membership: NodeMembership) -> NodeMembership:
        self._ensure_collection()
        encoded = json.dumps(
            {**membership.describe(), _SCHEMA_KEY: _SCHEMA_VERSION},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if self._native_collections(self._native):
            self._native.upsert_record(
                _MEMBERSHIP_COLLECTION,
                membership.node_id.encode("utf-8"),
                encoded,
            )
            self._native.delete(self._key(membership.node_id))
        else:
            self._native.put(self._key(membership.node_id), encoded)
        return membership

    def join(
        self,
        principal: Principal,
        advertisement: NodeAdvertisement | None = None,
    ) -> NodeMembership:
        """Create or reactivate authenticated node membership."""
        self._require_node(principal)
        now = _now()
        existing = self.get(principal.id)
        membership = NodeMembership(
            node_id=principal.id,
            status=MemberStatus.ACTIVE,
            advertisement=advertisement
            or (
                existing.advertisement if existing is not None else NodeAdvertisement()
            ),
            joined_at=existing.joined_at if existing is not None else now,
            last_seen_at=now,
            updated_at=now,
        )
        return self._save(membership)

    def heartbeat(
        self,
        principal: Principal,
        advertisement: NodeAdvertisement | None = None,
    ) -> NodeMembership:
        """Refresh liveness and optionally replace descriptive advertisement."""
        self._require_node(principal)
        existing = self.get(principal.id)
        if existing is None or existing.status is MemberStatus.LEFT:
            raise KeyError(f"Node '{principal.id}' is not an active member")
        now = _now()
        return self._save(
            replace(
                existing,
                status=MemberStatus.ACTIVE,
                advertisement=advertisement or existing.advertisement,
                last_seen_at=now,
                updated_at=now,
            )
        )

    def mark_suspect(self, node_id: str) -> NodeMembership:
        existing = self.get(node_id)
        if existing is None:
            raise KeyError(f"Unknown node '{node_id}'")
        return self._save(
            replace(existing, status=MemberStatus.SUSPECT, updated_at=_now())
        )

    def leave(self, principal: Principal) -> NodeMembership:
        self._require_node(principal)
        existing = self.get(principal.id)
        if existing is None:
            raise KeyError(f"Unknown node '{principal.id}'")
        return self._save(
            replace(existing, status=MemberStatus.LEFT, updated_at=_now())
        )

    def get(self, node_id: str) -> NodeMembership | None:
        self._ensure_collection()
        raw = None
        if self._native_collections(self._native):
            record = self._native.get_record(
                _MEMBERSHIP_COLLECTION, node_id.encode("utf-8")
            )
            if record is not None:
                raw = record[1]
        if raw is None:
            raw = self._native.get(self._key(node_id))
        if raw is None:
            return None
        record = json.loads(bytes(raw).decode("utf-8"))
        if not isinstance(record, dict):
            raise ValueError("membership record must be a JSON object")
        membership = NodeMembership.from_record(record)
        if membership.node_id != node_id:
            raise ValueError("membership key does not match record node_id")
        return membership

    def list(self, *, include_left: bool = False) -> list[NodeMembership]:
        memberships: list[NodeMembership] = []
        self._ensure_collection()
        records: dict[str, bytes] = {}
        if self._native_collections(self._native):
            records.update(
                {
                    bytes(key).decode("utf-8"): raw
                    for key, raw, _indexes in self._native.scan_collection(
                        _MEMBERSHIP_COLLECTION
                    )
                }
            )
        for key, raw in self._native.scan_prefix(_MEMBERSHIP_PREFIX):
            expected_id = bytes(key)[len(_MEMBERSHIP_PREFIX) :].decode("utf-8")
            records.setdefault(expected_id, raw)
        for expected_id, raw in records.items():
            try:
                record = json.loads(bytes(raw).decode("utf-8"))
                if not isinstance(record, dict):
                    continue
                item = NodeMembership.from_record(record)
                if item.node_id == expected_id:
                    memberships.append(item)
            except ValueError as error:
                if str(error).startswith("unsupported membership schema"):
                    raise
                continue
            except (TypeError, json.JSONDecodeError):
                continue
        if include_left:
            return memberships
        return [item for item in memberships if item.status is not MemberStatus.LEFT]
