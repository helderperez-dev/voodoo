"""Compatibility facade for distributed participant authentication."""

from voodoo.runtime.distributed.auth import (
    InMemoryParticipantResolver,
    ParticipantAuthenticationError,
    ParticipantEvidence,
    ParticipantIdentity,
    ParticipantResolver,
)

__all__ = [
    "ParticipantAuthenticationError",
    "ParticipantEvidence",
    "ParticipantIdentity",
    "ParticipantResolver",
    "InMemoryParticipantResolver",
]
