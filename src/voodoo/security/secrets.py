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
import stat
import tempfile
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

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

    @staticmethod
    def _require_private(path: Path, *, label: str) -> None:
        """Reject Unix files that expose secret material to other users."""
        if os.name == "nt" or not path.exists():
            return
        if path.stat().st_mode & 0o077:
            raise SecretsError(
                f"{label} must not be readable by group or others: {path}. "
                "Run chmod 600 (or restrict the containing directory)."
            )

    def _ensure_key(self) -> str:
        if self._key:
            return self._key
        env_key = os.environ.get("VOODOO_SECRETS_KEY")
        if env_key:
            self._key = env_key
            return env_key
        key_file = Path(".voodoo-secrets-key")
        if key_file.exists():
            self._require_private(key_file, label=".voodoo-secrets-key")
            self._key = key_file.read_text().strip()
            return self._key
        raise SecretsError(
            "No encryption key found. Set VOODOO_SECRETS_KEY env var, "
            "create .voodoo-secrets-key file, or pass key= to LocalSecretStore."
        )

    def _fernet(self) -> Any:
        try:
            from cryptography.fernet import Fernet
        except ImportError as exc:
            raise SecretsError(
                "Encrypted local secrets require the 'secrets' extra. "
                "Install it with: pip install 'voodoo-framework[secrets]'"
            ) from exc

        try:
            key = self._ensure_key()
            return Fernet(key.encode())
        except (TypeError, ValueError) as exc:
            raise SecretsError("VOODOO_SECRETS_KEY is not a valid Fernet key.") from exc

    def _load(self) -> dict[str, str]:
        if self._data is not None:
            return self._data
        if not self._path.exists():
            self._data = {}
            return self._data
        self._require_private(self._path, label="encrypted secrets file")
        fernet = self._fernet()
        try:
            from cryptography.fernet import InvalidToken

            decrypted = fernet.decrypt(self._path.read_bytes())
            decoded = json.loads(decrypted)
        except (InvalidToken, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise SecretsError(
                f"Could not decrypt local secrets file '{self._path}'. "
                "Verify the key and file integrity."
            ) from exc
        if not isinstance(decoded, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in decoded.items()
        ):
            raise SecretsError("The decrypted secrets payload must be string pairs.")
        self._data = decoded
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
        self._path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != "nt":
            # mkdir(mode=...) does not tighten permissions on an existing
            # directory; refuse to write into a world-readable secrets dir.
            if self._path.parent.stat().st_mode & 0o077:
                raise SecretsError(
                    f"secrets directory must not be readable by group or others: "
                    f"{self._path.parent}. Run chmod 700."
                )
        encrypted = self._fernet().encrypt(json.dumps(data).encode())
        temp_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=self._path.parent,
                prefix=f".{self._path.name}.",
                delete=False,
            ) as temporary:
                temp_name = temporary.name
                temporary.write(encrypted)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.chmod(temp_name, stat.S_IRUSR | stat.S_IWUSR)
            os.replace(temp_name, self._path)
        except OSError as exc:
            if temp_name is not None:
                try:
                    os.unlink(temp_name)
                except FileNotFoundError:
                    pass
            raise SecretsError(
                f"Could not persist encrypted secrets file '{self._path}'."
            ) from exc
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
