"""Adapter capability contracts & negotiation (Sprint 8, spec §9–§10).

Every adapter in the runtime — database, queue, event bus, object store —
declares what it guarantees through a ``*Capabilities`` dataclass returned by
``.capabilities()``. The runtime never assumes all providers are equivalent:
code that *requires* a guarantee calls :func:`require` and the negotiation
layer either proceeds, emulates it when a safe fallback is supplied, or fails
loudly with a :class:`CapabilityError`.

Rules (spec §10):

- never silently violate correctness;
- emulate a feature when safe;
- reject an unsupported required operation;
- degrade explicitly.

All capability models share a single base (:class:`AdapterCapabilities`) so a
provider matrix can be rendered uniformly by ``voodoo doctor`` and queried by
the runtime.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, fields
from typing import Any

__all__ = [
    "CapabilityError",
    "AdapterCapabilities",
    "DatabaseCapabilities",
    "QueueCapabilities",
    "EventBusCapabilities",
    "ObjectStoreCapabilities",
    "require",
    "negotiate",
    "capability_matrix",
]


class CapabilityError(RuntimeError):
    """Raised when an adapter cannot satisfy a required capability.

    Carries the adapter kind, provider name, and missing feature, so the
    surfaced error is actionable ("queue provider 'memory' does not support
    'delayed_delivery' — use a durable queue provider") rather than a
    generic ``NotImplementedError``.
    """

    def __init__(self, kind: str, provider: str, feature: str, hint: str = "") -> None:
        self.kind = kind
        self.provider = provider
        self.feature = feature
        self.hint = hint
        message = (
            f"{kind} provider {provider!r} does not support {feature!r}"
            f"{f' — {hint}' if hint else ''}"
        )
        super().__init__(message)


@dataclass(frozen=True)
class AdapterCapabilities:
    """Base capability declaration shared by every adapter kind (spec §9).

    ``provider`` names the backend; subclasses add kind-specific boolean
    flag fields. A flag of ``True`` means the adapter guarantees the behavior;
    ``False`` means the runtime must reject or emulate it (never silently
    ignore the gap).
    """

    provider: str

    def supports(self, feature: str) -> bool:
        """Whether a declared boolean capability flag is true."""
        value = getattr(self, feature, None)
        if value is None:
            raise AttributeError(
                f"{type(self).__name__} has no capability flag {feature!r}"
            )
        return bool(value)

    def describe(self) -> dict[str, Any]:
        """JSON-ready view for CLI/API output and ``voodoo doctor``."""
        return {f.name: getattr(self, f.name) for f in fields(self)}


@dataclass(frozen=True)
class DatabaseCapabilities(AdapterCapabilities):
    """Declarative contract of what a database adapter guarantees (spec §9)."""

    transactions: bool = True
    migrations: bool = True
    native_json: bool = False
    concurrent_writers: bool = False


@dataclass(frozen=True)
class QueueCapabilities(AdapterCapabilities):
    """Declarative contract of what a queue adapter guarantees (spec §9)."""

    durable: bool = True
    delivery: str = "at_least_once"
    ordering: str = "best_effort"  # priority-weighted, not FIFO across workers
    visibility_timeout: bool = True  # leases with expiry + reclaim
    delayed_delivery: bool = True
    priority: bool = True
    transactions: bool = True


@dataclass(frozen=True)
class EventBusCapabilities(AdapterCapabilities):
    """Declarative contract of what an event bus guarantees (Sprint 7)."""

    durable: bool = False
    replay: bool = False
    ordering: bool = True
    delivery: str = "at_most_once"


@dataclass(frozen=True)
class ObjectStoreCapabilities(AdapterCapabilities):
    """Declarative contract of what an object store guarantees (Sprint 6)."""

    presign_urls: bool = False
    checksums: bool = True
    metadata: bool = True
    multipart: bool = False


def require(
    caps: AdapterCapabilities,
    feature: str,
    *,
    hint: str = "",
) -> None:
    """Reject a required operation loudly when the adapter cannot honor it.

    ``feature`` is the capability flag name (e.g. ``delayed_delivery``).
    Raises :class:`CapabilityError` unless the flag is truthy.
    """
    if not caps.supports(feature):
        raise CapabilityError(
            type(caps).__name__.removesuffix("Capabilities").lower(),
            caps.provider,
            feature,
            hint,
        )


def negotiate(
    caps: AdapterCapabilities,
    feature: str,
    *,
    emulate: Callable[[], Any] | None = None,
    hint: str = "",
) -> Any:
    """Negotiate a capability: use it when supported, else emulate or fail.

    When the adapter declares ``feature`` true the operation proceeds.
    Otherwise the ``emulate`` fallback runs if provided (safe degradation);
    with no fallback the operation is rejected with :class:`CapabilityError`.

    Returns the result of the supported path (``None``) or of the emulation.
    """
    if caps.supports(feature):
        return None
    if emulate is not None:
        return emulate()
    require(caps, feature, hint=hint)
    return None  # pragma: no cover — require() always raises on unsupported


def capability_matrix(
    adapters: Iterable[AdapterCapabilities],
) -> dict[str, dict[str, Any]]:
    """Build a uniform provider matrix for reporting/``voodoo doctor``.

    Returns ``{provider: {feature: value, ...}}``.
    """
    return {caps.provider: caps.describe() for caps in adapters}
