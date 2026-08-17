"""Resource — what the system consumes or depends upon.

Resources include:
    memory, CPU, GPU, NPU, network, storage, tokens, money,
    battery, time, bandwidth, external services, human attention

The runtime uses resources to reason about trade-offs:

    execution A: cost=$0, latency=30ms, energy=low, quality=medium
    execution B: cost=$0.03, latency=500ms, energy=high, quality=high

The application should not need to know which provider, hardware,
or infrastructure delivers the result.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Resource(BaseModel):
    """Resource consumption or requirements.

    Semantics:
        cost           — monetary cost
        latency_ms     — execution latency in milliseconds
        energy         — energy usage ("low", "medium", "high")
        memory_mb      — memory usage in MB
        tokens         — token count (for AI compute)
        bandwidth_mbps — bandwidth in Mbps
    """

    cost: float = 0.0
    latency_ms: float | None = None
    energy: str | None = None
    memory_mb: float | None = None
    tokens: int | None = None
    bandwidth_mbps: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    # -- composition -------------------------------------------------------

    def add(self, other: Resource) -> Resource:
        """Combine two resource specs (sum costs, take max latency)."""
        return Resource(
            cost=self.cost + other.cost,
            latency_ms=max(
                x for x in [self.latency_ms, other.latency_ms] if x is not None
            )
            if self.latency_ms is not None or other.latency_ms is not None
            else None,
            energy=other.energy or self.energy,
            memory_mb=max(x for x in [self.memory_mb, other.memory_mb] if x is not None)
            if self.memory_mb is not None or other.memory_mb is not None
            else None,
            tokens=(self.tokens or 0) + (other.tokens or 0) or None,
            bandwidth_mbps=max(
                x for x in [self.bandwidth_mbps, other.bandwidth_mbps] if x is not None
            )
            if self.bandwidth_mbps is not None or other.bandwidth_mbps is not None
            else None,
        )

    # -- inspectability ----------------------------------------------------

    def describe(self) -> dict[str, Any]:
        """Machine-readable description."""
        return {
            "cost": self.cost,
            "latency_ms": self.latency_ms,
            "energy": self.energy,
            "memory_mb": self.memory_mb,
            "tokens": self.tokens,
            "bandwidth_mbps": self.bandwidth_mbps,
        }
