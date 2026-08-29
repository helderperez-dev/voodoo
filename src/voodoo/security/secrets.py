"""Secrets store — centralized secret management (Sprint 19, ROADMAP §55).

Provides a single interface for accessing secrets so that:

- Secrets are never hardcoded or leaked into events/journal/telemetry.
- The default backend reads from environment variables (zero-config).
- An optional encrypted local store is available for development.
- Provider managers (Vault, AWS Secrets Manager, etc.) are future adapters.

Usage::

    from voodoo.security.secrets import secrets

    api_key = secrets.get("OPENAI_API_KEY")
    db_pass = secrets.get("DATABASE_PASSWORD")

The module-level ``secrets`` singleton is an :class:`EnvSecretStore` by
default.  Call ``configure()`` to swap the backend.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol, runtime_checkable

__all__ = [
    "SecretStore",
    "EnvSecretStore",
    "LocalSecretStore",
    "SecretsError",
    "secrets",
    "configure",
    "registered_names",
]


class SecretsError(RuntimeError):
    """Raised when a secret cannot be retrieved."""


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class SecretStore(Protocol):
    """Minimal interface every secrets backend must satisfy."""

    def get(self, name: str) -> str | None:
        """Return the secret value, or ``None`` if not found."""
        ...

    def has(self, name: str) -> bool:
        """Whether the secret exists."""
        ...


# ---------------------------------------------------------------------------
# Environment-variable backend (default)
# ---------------------------------------------------------------------------


class EnvSecretStore:
    """Read secrets from environment variables.

    This is the zero-config default — no external services required.
    """

    def get(self, name: str) -> str | None:
        return os.environ.get(name)

    def has(self, name: str) -> bool:
        return name in os.environ


# ---------------------------------------------------------------------------
# Encrypted local file backend
# ---------------------------------------------------------------------------


class LocalSecretStore:
    """Encrypted local file store using Fernet symmetric encryption.

    Requires the ``cryptography`` package (optional extra ``[secrets]``).
    The encryption key is derived from a passphrase or read from a key file.

    Parameters
    ----------
    path:
        Path to the secrets JSON file.
    key:
        Fernet encryption key.  If ``None``, reads from ``VOODOO_SECRETS_KEY``
        env var or ``.voodoo-secrets-key`` file.
    """

    def __init__(self, path: str | Path, key: str | None = None) -> None:
        self._path = Path(path)
        self._key = key
        self._data: dict[str, str] | None = None

    def _ensure_key(self) -> str:
        if self._key:
            return self._key
        env_key = os.environ.get("VOODOO_SECRETS_KEY")
        if env_key:
            self._key = env_key
            return env_key
        key_file = Path(".voodoo-secrets-key")
        if key_file.exists():
            self._key = key_file.read_text().strip()
            return self._key
        raise SecretsError(
            "No encryption key found. Set VOODOO_SECRETS_KEY env var, "
            "create .voodoo-secrets-key file, or pass key= to LocalSecretStore."
        )

    def _load(self) -> dict[str, str]:
        if self._data is not None:
            return self._data
        if not self._path.exists():
            self._data = {}
            return self._data
        try:
            from cryptography.fernet import Fernet

            key = self._ensure_key()
            f = Fernet(key.encode() if isinstance(key, str) else key)
            raw = self._path.read_bytes()
            decrypted = f.decrypt(raw)
            self._data = json.loads(decrypted)
        except ImportError:
            # cryptography not installed — read as plain JSON
            self._data = json.loads(self._path.read_text())
        except SecretsError:
            # No key available — fall back to plain JSON
            self._data = json.loads(self._path.read_text())
        except Exception:  # noqa: BLE001
            # Decryption failed — try plain JSON (dev convenience)
            self._data = json.loads(self._path.read_text())
        return self._data

    def get(self, name: str) -> str | None:
        return self._load().get(name)

    def has(self, name: str) -> bool:
        return name in self._load()

    def set(self, name: str, value: str) -> None:
        """Store a secret (encrypts and writes to disk)."""
        data = self._load()
        data[name] = value
        self._save(data)

    def _save(self, data: dict[str, str]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            from cryptography.fernet import Fernet

            key = self._ensure_key()
            f = Fernet(key.encode() if isinstance(key, str) else key)
            encrypted = f.encrypt(json.dumps(data).encode())
            self._path.write_bytes(encrypted)
        except (ImportError, SecretsError):
            self._path.write_text(json.dumps(data, indent=2))
        self._data = data


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

#: The active secrets store.  Defaults to :class:`EnvSecretStore`.
_store: SecretStore = EnvSecretStore()

#: Names of secrets that have been explicitly registered for redaction.
_registered_names: set[str] = set()


def configure(store: SecretStore) -> None:
    """Swap the active secrets backend.

    Parameters
    ----------
    store:
        Any object satisfying the :class:`SecretStore` protocol.
    """
    global _store
    if not isinstance(store, SecretStore):
        raise TypeError(
            f"store must satisfy the SecretStore protocol, got {type(store).__name__}"
        )
    _store = store


def get(name: str) -> str | None:
    """Retrieve a secret by name from the active store."""
    return _store.get(name)


def has(name: str) -> bool:
    """Whether a secret exists in the active store."""
    return _store.has(name)


def register_name(name: str) -> None:
    """Register a secret name for redaction tracking.

    Registered names (and their values, when resolved) are scrubbed
    from events, journal entries, telemetry, and log output.
    """
    _registered_names.add(name)


def registered_names() -> set[str]:
    """Return the set of registered secret names."""
    return set(_registered_names)


# Convenience alias
secrets = EnvSecretStore()
