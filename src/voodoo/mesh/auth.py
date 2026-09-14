"""Authentication seam for distributed Mesh participants.

Authentication is deliberately separate from capability authority. Transport
adapters present credential/session evidence to a resolver; the resolver returns
an immutable participant identity. The resolved participant, never an actor
label supplied by the application payload, becomes the runtime actor.

Production PKI/OIDC/mTLS adapters are intentionally outside the core. The
in-memory resolver provides a zero-infrastructure implementation for local
systems and the Sprint 26/28 acceptance suites.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from typing import Any, Protocol

from voodoo.runtime.identity import (
    AuthenticationEvidence,
    Identity,
    IdentityKind,
    Principal,
)


class ParticipantAuthenticationError(Exception):
    """Raised when transport evidence cannot be bound to a participant."""


@dataclass(frozen=True)
class ParticipantEvidence:
    """Credential/session evidence supplied by a transport adapter."""

    credential: str | None = None
    transport: str = "unknown"
    peer: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParticipantIdentity:
    """Immutable identity resolved from transport evidence."""

    participant_id: str
    kind: IdentityKind = IdentityKind.SERVICE
    session_id: str | None = None
    authenticated: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def runtime_actor(self) -> str:
        actor = self.participant_id.strip() or "anonymous"
        if actor.startswith("remote:"):
            return actor
        return f"remote:{actor}"

    def to_principal(self) -> Principal:
        """Project trusted transport identity into Runtime-native identity semantics."""
        evidence: tuple[AuthenticationEvidence, ...] = ()
        if self.authenticated:
            evidence = (
                AuthenticationEvidence(
                    method=f"mesh:{self.metadata.get('transport', 'unknown')}",
                    subject=self.participant_id,
                    issuer="voodoo-mesh",
                    metadata={
                        key: value
                        for key, value in self.metadata.items()
                        if key not in {"credential", "token", "secret"}
                    },
                ),
            )
        return Principal(
            identity=Identity(
                id=self.participant_id,
                kind=self.kind,
                attributes={"remote": True},
            ),
            evidence=evidence,
            claims={"mesh_session_id": self.session_id} if self.session_id else {},
        )


class ParticipantResolver(Protocol):
    """Transport-independent participant authentication contract."""

    async def resolve(self, evidence: ParticipantEvidence) -> ParticipantIdentity: ...


class InMemoryParticipantResolver:
    """Zero-infrastructure credential resolver for local/development systems."""

    def __init__(self) -> None:
        self._participants: dict[
            str, tuple[str, IdentityKind, dict[str, Any]]
        ] = {}

    @staticmethod
    def _hash(credential: str) -> str:
        return hashlib.sha256(credential.encode("utf-8")).hexdigest()

    def register(
        self,
        participant_id: str,
        *,
        credential: str | None = None,
        kind: IdentityKind | str = IdentityKind.SERVICE,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        raw = credential or f"vmp_{secrets.token_urlsafe(32)}"
        resolved_kind = kind if isinstance(kind, IdentityKind) else IdentityKind(kind)
        self._participants[self._hash(raw)] = (
            participant_id,
            resolved_kind,
            dict(metadata or {}),
        )
        return raw

    def register_node(
        self,
        node_id: str,
        *,
        credential: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Register an authenticated Voodoo Node identity without granting authority."""
        return self.register(
            node_id,
            credential=credential,
            kind=IdentityKind.NODE,
            metadata=metadata,
        )

    def revoke(self, credential: str) -> None:
        self._participants.pop(self._hash(credential), None)

    async def resolve(self, evidence: ParticipantEvidence) -> ParticipantIdentity:
        if not evidence.credential:
            raise ParticipantAuthenticationError("missing participant credential")
        record = self._participants.get(self._hash(evidence.credential))
        if record is None:
            raise ParticipantAuthenticationError("invalid participant credential")
        participant_id, kind, metadata = record
        return ParticipantIdentity(
            participant_id=participant_id,
            kind=kind,
            authenticated=True,
            metadata={
                **metadata,
                **evidence.metadata,
                "transport": evidence.transport,
                "peer": evidence.peer,
            },
        )


__all__ = [
    "ParticipantAuthenticationError",
    "ParticipantEvidence",
    "ParticipantIdentity",
    "ParticipantResolver",
    "InMemoryParticipantResolver",
]
