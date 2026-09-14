"""Governed Voodoo Node fabric semantics.

This module closes the Sprint 28 distributed-runtime boundary without pretending
that node-local Stores form a distributed database. Membership/discovery,
placement, ownership and bounded failover are Runtime concerns. Each node keeps
its own Store; transport remains replaceable; remote effects still have to enter
Capability + Policy + canonical Execution on the receiving node.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import uuid4

from voodoo.runtime.membership import (
    MemberStatus,
    NodeMembership,
    VoodooStoreMembershipStore,
)
from voodoo.runtime.store import (
    RuntimeStore,
    StoreProviderError,
    get_active_runtime_store,
)

__all__ = [
    "FabricRoutingError",
    "NoEligibleNodeError",
    "WorkNotFailoverSafeError",
    "PlacementRequirement",
    "PlacementDecision",
    "FabricWork",
    "FabricLease",
    "FabricExecutor",
    "RuntimeFabric",
]

_LEASE_PREFIX = b"runtime:fabric:lease:"


def _now() -> datetime:
    return datetime.now(UTC)


class FabricRoutingError(RuntimeError):
    """Base error for governed Runtime fabric routing."""


class NoEligibleNodeError(FabricRoutingError):
    """No active member can satisfy the declared placement contract."""


class WorkNotFailoverSafeError(FabricRoutingError):
    """Failover was requested for work that does not permit reassignment."""


@dataclass(frozen=True, slots=True)
class PlacementRequirement:
    """Topology-neutral placement constraints for one unit of work."""

    capability: str | None = None
    service: str | None = None
    owner: str | None = None
    location: str | None = None
    preferred_node: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PlacementDecision:
    node_id: str
    score: float
    reasons: tuple[str, ...]
    membership: NodeMembership


@dataclass(frozen=True, slots=True)
class FabricWork:
    """Transport-neutral work description.

    ``retryable`` means the Runtime is allowed to *attempt* execution on another
    node after bounded failure detection. It is not an exactly-once promise.
    ``idempotency_key`` is stable across attempts so receiving nodes can dedupe
    where their operation semantics support it.
    """

    operation: str
    payload: dict[str, Any] = field(default_factory=dict)
    requirement: PlacementRequirement = field(default_factory=PlacementRequirement)
    id: str = field(default_factory=lambda: uuid4().hex)
    idempotency_key: str = field(default_factory=lambda: uuid4().hex)
    retryable: bool = True
    max_attempts: int = 2


@dataclass(frozen=True, slots=True)
class FabricLease:
    work_id: str
    node_id: str
    generation: int
    acquired_at: datetime
    expires_at: datetime

    @property
    def active(self) -> bool:
        return self.expires_at > _now()

    def describe(self) -> dict[str, Any]:
        return {
            "work_id": self.work_id,
            "node_id": self.node_id,
            "generation": self.generation,
            "acquired_at": self.acquired_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> FabricLease:
        return cls(
            work_id=str(record["work_id"]),
            node_id=str(record["node_id"]),
            generation=int(record["generation"]),
            acquired_at=datetime.fromisoformat(record["acquired_at"]),
            expires_at=datetime.fromisoformat(record["expires_at"]),
        )


class FabricExecutor(Protocol):
    """Replaceable transport boundary used after a governed route is chosen."""

    async def execute(
        self,
        node_id: str,
        work: FabricWork,
        *,
        attempt: int,
    ) -> Any: ...


PolicyPredicate = Callable[[NodeMembership, FabricWork], bool]


class RuntimeFabric:
    """Discovery, placement, ownership, leases and bounded failover.

    Routing never grants authority. Node advertisements are descriptive. The
    receiving node remains responsible for authenticating the caller and running
    Capability + Policy + canonical Execution before effects occur.
    """

    def __init__(
        self,
        membership: VoodooStoreMembershipStore | None = None,
        *,
        runtime_store: RuntimeStore | None = None,
        policy: PolicyPredicate | None = None,
        lease_seconds: float = 30.0,
    ) -> None:
        self.runtime_store = runtime_store or get_active_runtime_store()
        if self.runtime_store is None:
            raise StoreProviderError("No active RuntimeStore for Runtime fabric")
        provider = self.runtime_store.provider
        if provider is None or not provider.opened:
            raise StoreProviderError("RuntimeStore must be started for Runtime fabric")
        if provider.name != "voodoo":
            raise StoreProviderError("RuntimeFabric currently requires Voodoo Store")
        self._native = getattr(provider, "native", None)
        if self._native is None:
            raise StoreProviderError("Active Voodoo Store has no native handle")
        self.membership = membership or VoodooStoreMembershipStore(self.runtime_store)
        self.policy = policy
        self.lease_seconds = lease_seconds

    def sweep_health(
        self,
        *,
        suspect_after_seconds: float = 30.0,
        now: datetime | None = None,
    ) -> list[str]:
        """Mark stale ACTIVE members SUSPECT and return affected node ids."""
        current = now or _now()
        changed: list[str] = []
        for member in self.membership.list():
            if member.status is not MemberStatus.ACTIVE:
                continue
            age = (current - member.last_seen_at).total_seconds()
            if age > suspect_after_seconds:
                self.membership.mark_suspect(member.node_id)
                changed.append(member.node_id)
        return changed

    def candidates(
        self,
        requirement: PlacementRequirement,
        *,
        exclude: set[str] | None = None,
    ) -> list[NodeMembership]:
        """Return ACTIVE nodes satisfying hard placement constraints."""
        excluded = exclude or set()
        result: list[NodeMembership] = []
        for member in self.membership.list():
            if member.node_id in excluded or member.status is not MemberStatus.ACTIVE:
                continue
            ad = member.advertisement
            if requirement.capability and requirement.capability not in ad.capabilities:
                continue
            if requirement.service and requirement.service not in ad.services:
                continue
            if requirement.owner and requirement.owner not in ad.store_ownership:
                continue
            if self.policy is not None:
                probe = FabricWork(operation="placement.probe", requirement=requirement)
                if not self.policy(member, probe):
                    continue
            result.append(member)
        return result

    @staticmethod
    def _load(member: NodeMembership) -> float:
        raw = member.advertisement.resources.get("load", 0.0)
        try:
            return max(0.0, min(1.0, float(raw)))
        except (TypeError, ValueError):
            return 0.0

    def place(
        self,
        requirement: PlacementRequirement,
        *,
        exclude: set[str] | None = None,
    ) -> PlacementDecision:
        candidates = self.candidates(requirement, exclude=exclude)
        if not candidates:
            raise NoEligibleNodeError(
                "No ACTIVE Voodoo Node satisfies placement requirements"
            )

        ranked: list[PlacementDecision] = []
        for member in candidates:
            score = 100.0 * (1.0 - self._load(member))
            reasons = ["active", f"load={self._load(member):.3f}"]
            ad = member.advertisement
            if requirement.preferred_node == member.node_id:
                score += 1000.0
                reasons.append("preferred-node")
            if requirement.owner and requirement.owner in ad.store_ownership:
                score += 500.0
                reasons.append("data-owner")
            if requirement.location and requirement.location == ad.location:
                score += 100.0
                reasons.append("locality")
            if requirement.capability:
                reasons.append(f"capability:{requirement.capability}")
            if requirement.service:
                reasons.append(f"service:{requirement.service}")
            ranked.append(
                PlacementDecision(
                    node_id=member.node_id,
                    score=score,
                    reasons=tuple(reasons),
                    membership=member,
                )
            )
        ranked.sort(key=lambda item: (-item.score, item.node_id))
        return ranked[0]

    @staticmethod
    def _lease_key(work_id: str) -> bytes:
        return _LEASE_PREFIX + work_id.encode("utf-8")

    def get_lease(self, work_id: str) -> FabricLease | None:
        raw = self._native.get(self._lease_key(work_id))
        if raw is None:
            return None
        return FabricLease.from_record(json.loads(bytes(raw).decode("utf-8")))

    def acquire_lease(
        self,
        work_id: str,
        node_id: str,
        *,
        now: datetime | None = None,
    ) -> FabricLease:
        current = now or _now()
        previous = self.get_lease(work_id)
        generation = 1 if previous is None else previous.generation + 1
        lease = FabricLease(
            work_id=work_id,
            node_id=node_id,
            generation=generation,
            acquired_at=current,
            expires_at=current + timedelta(seconds=self.lease_seconds),
        )
        self._native.put(
            self._lease_key(work_id),
            json.dumps(
                lease.describe(), sort_keys=True, separators=(",", ":")
            ).encode(),
        )
        return lease

    def release_lease(self, work_id: str) -> None:
        self._native.delete(self._lease_key(work_id))

    async def execute(self, work: FabricWork, executor: FabricExecutor) -> Any:
        """Route and execute with bounded, explicit failover semantics."""
        if work.max_attempts < 1:
            raise ValueError("FabricWork.max_attempts must be at least 1")
        excluded: set[str] = set()
        last_error: Exception | None = None

        for attempt in range(1, work.max_attempts + 1):
            decision = self.place(work.requirement, exclude=excluded)
            lease = self.acquire_lease(work.id, decision.node_id)
            try:
                result = await executor.execute(decision.node_id, work, attempt=attempt)
            except Exception as error:
                last_error = error
                excluded.add(decision.node_id)
                if not work.retryable:
                    raise WorkNotFailoverSafeError(
                        f"Work '{work.id}' failed on {decision.node_id} and is not failover-safe"
                    ) from error
                if attempt >= work.max_attempts:
                    raise FabricRoutingError(
                        f"Work '{work.id}' exhausted {work.max_attempts} fabric attempts"
                    ) from error
                continue
            finally:
                current = self.get_lease(work.id)
                if current is not None and current.generation == lease.generation:
                    self.release_lease(work.id)
            return result

        raise FabricRoutingError(
            f"Work '{work.id}' could not be routed"
        ) from last_error
