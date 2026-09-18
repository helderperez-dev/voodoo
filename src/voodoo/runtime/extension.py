"""Stable vendor-neutral extension API.

Extensions declare semantic surfaces. Installation, activation and authority are
separate concerns: an installed provider is never implicitly enabled or trusted.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from voodoo.runtime.application_graph import (
    ApplicationGraph,
    Extension,
    ExtensionManifest,
)


class ExtensionState(StrEnum):
    DISCOVERED = "discovered"
    CONFIGURED = "configured"
    ACTIVE = "active"
    UNHEALTHY = "unhealthy"
    INACTIVE = "inactive"


@dataclass(frozen=True, slots=True)
class ExtensionStatus:
    name: str
    state: ExtensionState
    healthy: bool | None = None
    reason: str | None = None


class RuntimeExtensionRegistry:
    """Explicit extension lifecycle without package-import magic."""

    def __init__(self) -> None:
        self._extensions: dict[str, Extension] = {}
        self._status: dict[str, ExtensionStatus] = {}

    def discover(self, extension: Extension) -> ExtensionStatus:
        name = extension.manifest.name
        existing = self._extensions.get(name)
        if existing is not None and existing is not extension:
            raise ValueError(f"Extension {name!r} is already discovered")
        self._extensions[name] = extension
        status = ExtensionStatus(name, ExtensionState.DISCOVERED)
        self._status[name] = status
        return status

    def configure(self, name: str) -> ExtensionStatus:
        self._require(name)
        return self._set(name, ExtensionState.CONFIGURED)

    def activate(self, name: str) -> ExtensionStatus:
        self._require(name)
        current = self._status[name].state
        if current not in {ExtensionState.CONFIGURED, ExtensionState.INACTIVE}:
            raise RuntimeError(
                f"Extension {name!r} must be configured before activation"
            )
        return self._set(name, ExtensionState.ACTIVE, healthy=True)

    def health(
        self, name: str, *, healthy: bool, reason: str | None = None
    ) -> ExtensionStatus:
        self._require(name)
        state = ExtensionState.ACTIVE if healthy else ExtensionState.UNHEALTHY
        return self._set(name, state, healthy=healthy, reason=reason)

    def deactivate(self, name: str) -> ExtensionStatus:
        self._require(name)
        return self._set(name, ExtensionState.INACTIVE)

    def active(self) -> tuple[Extension, ...]:
        return tuple(
            self._extensions[name]
            for name, status in self._status.items()
            if status.state is ExtensionState.ACTIVE
        )

    def contribute(self, graph: ApplicationGraph) -> None:
        for extension in self.active():
            extension.contribute(graph)

    def status(self, name: str) -> ExtensionStatus:
        self._require(name)
        return self._status[name]

    def _require(self, name: str) -> Extension:
        try:
            return self._extensions[name]
        except KeyError as exc:
            raise KeyError(f"Unknown extension {name!r}") from exc

    def _set(
        self,
        name: str,
        state: ExtensionState,
        *,
        healthy: bool | None = None,
        reason: str | None = None,
    ) -> ExtensionStatus:
        status = ExtensionStatus(name, state, healthy=healthy, reason=reason)
        self._status[name] = status
        return status


__all__ = [
    "Extension",
    "ExtensionManifest",
    "ExtensionState",
    "ExtensionStatus",
    "RuntimeExtensionRegistry",
]
