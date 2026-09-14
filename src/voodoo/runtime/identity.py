"""Runtime-native identity semantics.

Identity answers *who or what exists*. AuthenticationEvidence records how that
identity was authenticated. Principal is the authenticated Runtime subject that
enters an ExecutionContext. None of these objects grant Capability by
themselves: authority remains Capability + Policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

__all__ = [
    "IdentityKind",
    "IdentityStatus",
    "Identity",
    "AuthenticationEvidence",
    "Principal",
]


def _now() -> datetime:
    return datetime.now(UTC)


class IdentityKind(StrEnum):
    USER = "user"
    AGENT = "agent"
    SERVICE = "service"
    DEVICE = "device"
    NODE = "node"


class IdentityStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    REVOKED = "revoked"


@dataclass(frozen=True)
class Identity:
    """Stable Runtime identity independent of credentials or authority."""

    id: str
    kind: IdentityKind
    display_name: str | None = None
    status: IdentityStatus = IdentityStatus.ACTIVE
    attributes: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    @property
    def active(self) -> bool:
        return self.status is IdentityStatus.ACTIVE

    @property
    def actor(self) -> str:
        """Canonical actor representation used by existing Execution surfaces."""
        return self.id

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "display_name": self.display_name,
            "status": self.status.value,
            "attributes": dict(self.attributes),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> Identity:
        return cls(
            id=str(record["id"]),
            kind=IdentityKind(record["kind"]),
            display_name=record.get("display_name"),
            status=IdentityStatus(record.get("status", IdentityStatus.ACTIVE.value)),
            attributes=dict(record.get("attributes") or {}),
            created_at=datetime.fromisoformat(record["created_at"]),
            updated_at=datetime.fromisoformat(record["updated_at"]),
        )


@dataclass(frozen=True)
class AuthenticationEvidence:
    """Non-secret evidence describing one successful authentication event.

    Passwords, raw API keys, private keys and bearer tokens must never be placed
    here. Evidence records mechanism/issuer/subject and bounded public metadata.
    """

    method: str
    subject: str
    issuer: str | None = None
    authenticated_at: datetime = field(default_factory=_now)
    expires_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def valid(self) -> bool:
        return self.expires_at is None or self.expires_at > _now()

    def describe(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "subject": self.subject,
            "issuer": self.issuer,
            "authenticated_at": self.authenticated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class Principal:
    """Authenticated identity projected into Runtime execution semantics.

    A Principal is identity + authentication evidence. It intentionally carries
    no Capability grants. Authentication and authorization remain separate.
    """

    identity: Identity
    evidence: tuple[AuthenticationEvidence, ...] = ()
    claims: dict[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return self.identity.id

    @property
    def kind(self) -> IdentityKind:
        return self.identity.kind

    @property
    def actor(self) -> str:
        return self.identity.actor

    @property
    def authenticated(self) -> bool:
        return (
            self.identity.active
            and bool(self.evidence)
            and all(item.valid for item in self.evidence)
        )

    def describe(self) -> dict[str, Any]:
        return {
            "identity": self.identity.describe(),
            "authenticated": self.authenticated,
            "evidence": [item.describe() for item in self.evidence],
            "claims": dict(self.claims),
        }
