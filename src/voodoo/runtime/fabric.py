"""Compatibility facade for voodoo.runtime.distributed.fabric."""

from voodoo.runtime.distributed.fabric import (
    FabricExecutor,
    FabricLease,
    FabricRoutingError,
    FabricWork,
    NoEligibleNodeError,
    PlacementDecision,
    PlacementRequirement,
    RuntimeFabric,
    WorkNotFailoverSafeError,
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
