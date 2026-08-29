"""Redaction guard — prevent secrets from leaking into observability (Sprint 19).

Centralized redaction for all output channels: events, journal entries,
telemetry records, mesh payloads, and log output.

The guard scrubs:

1. Values of registered secrets (from :mod:`voodoo.security.secrets`).
2. Common secret patterns (API keys, bearer tokens, password URIs).
3. Keys named ``secret``, ``password``, ``token``, ``api_key``, etc.

Usage::

    from voodoo.security.redaction import redact

    safe = redact({"api_key": "sk-abc123", "name": "test"})
    # → {"api_key": "[REDACTED]", "name": "test"}
"""

from __future__ import annotations

import re
from typing import Any

__all__ = [
    "redact",
    "redact_string",
    "RedactionGuard",
]

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

#: Keys whose values are always redacted (case-insensitive partial match).
_SENSITIVE_KEY_PATTERNS: re.Pattern[str] = re.compile(
    r"(?i)(secret|password|passwd|token|api[_-]?key|auth|credential|private[_-]?key|"
    r"access[_-]?key|session[_-]?id|cookie)",
)

#: Value patterns that look like secrets regardless of key name.
_SENSITIVE_VALUE_PATTERNS: list[re.Pattern[str]] = [
    # Bearer tokens
    re.compile(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*"),
    # OpenAI-style keys
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    # Anthropic-style keys
    re.compile(r"sk-ant-[A-Za-z0-9\-]{20,}"),
    # AWS access keys
    re.compile(r"AKIA[0-9A-Z]{16}"),
    # Generic long hex tokens (32+ chars)
    re.compile(r"\b[A-Fa-f0-9]{32,}\b"),
    # JWT tokens (three base64 segments)
    re.compile(r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
    # Password in URI (scheme://user:password@host)
    re.compile(r"(?i)([a-z]+://[^:]+:)[^@\s]{4,}(@)"),
]

_REDACTED = "[REDACTED]"


def _is_sensitive_key(key: str) -> bool:
    """Whether a dict key name suggests a secret value."""
    return bool(_SENSITIVE_KEY_PATTERNS.search(key))


def _redact_value_pattern(value: str) -> str:
    """Replace known secret patterns inside a string."""
    result = value
    for pattern in _SENSITIVE_VALUE_PATTERNS:
        if pattern.pattern.startswith("(?i)([a-z]+://"):
            # URI password pattern — preserve scheme and host
            result = pattern.sub(rf"\1{_REDACTED}\2", result)
        else:
            result = pattern.sub(_REDACTED, result)
    return result


# ---------------------------------------------------------------------------
# Redaction guard
# ---------------------------------------------------------------------------


class RedactionGuard:
    """Centralized redaction engine.

    Maintains a set of known secret values (resolved from the secrets
    store) and applies key-name + value-pattern matching.
    """

    def __init__(self) -> None:
        self._known_values: set[str] = set()

    def load_secrets(self, names: set[str]) -> None:
        """Resolve secret values by name and cache them for redaction.

        Parameters
        ----------
        names:
            Secret names to resolve from the active secrets store.
        """
        from voodoo.security.secrets import get

        for name in names:
            value = get(name)
            if value and len(value) >= 4:
                self._known_values.add(value)

    def add_value(self, value: str) -> None:
        """Manually add a known secret value for redaction."""
        if value and len(value) >= 4:
            self._known_values.add(value)

    def redact(self, data: Any) -> Any:
        """Recursively redact secrets from a data structure.

        Handles dicts, lists, strings, and passthrough for other types.
        """
        if isinstance(data, dict):
            return {k: self._redact_field(k, v) for k, v in data.items()}
        if isinstance(data, list):
            return [self.redact(item) for item in data]
        if isinstance(data, str):
            return self.redact_string(data)
        return data

    def _redact_field(self, key: str, value: Any) -> Any:
        """Redact a single key-value pair."""
        if _is_sensitive_key(key):
            if isinstance(value, str) and value:
                return _REDACTED
            if value is not None:
                return _REDACTED
        return self.redact(value)

    def redact_string(self, value: str) -> str:
        """Redact known secret values and patterns inside a string."""
        result = value
        # Replace known secret values
        for secret_val in self._known_values:
            if secret_val in result:
                result = result.replace(secret_val, _REDACTED)
        # Replace common patterns
        result = _redact_value_pattern(result)
        return result


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_guard = RedactionGuard()


def redact(data: Any) -> Any:
    """Redact secrets from data using the global guard.

    Convenience wrapper around :meth:`RedactionGuard.redact`.
    """
    return _guard.redact(data)


def redact_string(value: str) -> str:
    """Redact secrets from a string using the global guard."""
    return _guard.redact_string(value)


def load_secrets(names: set[str]) -> None:
    """Load secret values into the global guard for redaction."""
    _guard.load_secrets(names)


def add_known_value(value: str) -> None:
    """Add a known secret value to the global guard."""
    _guard.add_value(value)
