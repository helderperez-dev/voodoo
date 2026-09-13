"""Trusted remote participant/session seam for Voodoo Mesh.

Authentication is deliberately separate from authority. A session proves which
remote participant is speaking; :class:`RemoteAuthorityRegistry` separately
decides which capabilities that participant may exercise.

This module provides a zero-infrastructure local implementation and a small
protocol seam for future certificate/signature/identity-provider adapters. Raw
session tokens are shown to callers but never stored; only SHA-256 hashes are
kept in memory by the built-in registry.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4

from pydantic import BaseModel, Field

from voodoo.mesh.remote import normalize_remote_actor


class RemoteAuthenticationError(Exception):
    """A remote participant could not be authenticated."""


class RemotePrincipal(BaseModel):
    """Trusted participant identity produced by an authentication adapter."""

    actor: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    authenticated: bool = True
    metadata: dict[str, str] = Field(default_factory=dict)

    @property
    def runtime_actor(self) -> str:
        return normalize_remote_actor(self.actor)


class RemoteAuthenticator(Protocol):
    """Adapter seam for resolving an opaque session token to a trusted actor."""

    def authenticate(self, token: str) -> RemotePrincipal: ...


@dataclass
class _SessionRecord:
    session_id: str
    actor: str
    token_hash: str
    expires_at: datetime | None
    revoked: bool = False
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def valid(self) -> bool:
        if self.revoked:
            return False
        if self.expires_at is None:
            return True
        return datetime.now(UTC) < self.expires_at


class InMemoryRemoteSessionRegistry:
    """Local-first trusted-session registry.

    This is suitable for tests, local deployments and as the reference contract
    for production authentication adapters. It intentionally does not pretend
    to be a PKI or distributed identity provider.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, _SessionRecord] = {}

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def issue(
        self,
        actor: str,
        *,
        expires_in_seconds: float | None = 3600,
        metadata: dict[str, str] | None = None,
    ) -> tuple[str, RemotePrincipal]:
        """Issue a new opaque session token and return it exactly once."""
        clean_actor = actor.strip()
        if not clean_actor:
            raise ValueError("remote session actor must not be empty")
        raw_token = f"vms_{secrets.token_urlsafe(32)}"
        session_id = str(uuid4())
        expires_at = (
            datetime.now(UTC) + timedelta(seconds=expires_in_seconds)
            if expires_in_seconds is not None
            else None
        )
        record = _SessionRecord(
            session_id=session_id,
            actor=clean_actor,
            token_hash=self._hash(raw_token),
            expires_at=expires_at,
            metadata=dict(metadata or {}),
        )
        self._sessions[record.token_hash] = record
        return raw_token, self._principal(record)

    def authenticate(self, token: str) -> RemotePrincipal:
        """Resolve an opaque token or reject invalid/expired/revoked sessions."""
        if not token:
            raise RemoteAuthenticationError("remote session token is required")
        record = self._sessions.get(self._hash(token))
        if record is None:
            raise RemoteAuthenticationError("invalid remote session")
        if record.revoked:
            raise RemoteAuthenticationError("remote session has been revoked")
        if not record.valid:
            raise RemoteAuthenticationError("remote session has expired")
        return self._principal(record)

    def revoke(self, session_id: str) -> bool:
        """Revoke one session by its public session identifier."""
        for record in self._sessions.values():
            if record.session_id == session_id:
                record.revoked = True
                return True
        return False

    def revoke_actor(self, actor: str) -> int:
        """Revoke every active session for one participant."""
        count = 0
        for record in self._sessions.values():
            if record.actor == actor and not record.revoked:
                record.revoked = True
                count += 1
        return count

    @staticmethod
    def _principal(record: _SessionRecord) -> RemotePrincipal:
        return RemotePrincipal(
            actor=record.actor,
            session_id=record.session_id,
            metadata=dict(record.metadata),
        )


__all__ = [
    "RemoteAuthenticationError",
    "RemoteAuthenticator",
    "RemotePrincipal",
    "InMemoryRemoteSessionRegistry",
]
