"""Compatibility facade for distributed remote execution semantics."""

from voodoo.runtime.distributed.remote import (
    REMOTE_SCHEMA_VERSION,
    ExposedOperation,
    RemoteAuthorityRegistry,
    RemoteExecutionOutcome,
    RemoteExecutionRequest,
    normalize_remote_actor,
)

__all__ = [
    "REMOTE_SCHEMA_VERSION",
    "RemoteExecutionRequest",
    "RemoteExecutionOutcome",
    "RemoteAuthorityRegistry",
    "ExposedOperation",
    "normalize_remote_actor",
]
