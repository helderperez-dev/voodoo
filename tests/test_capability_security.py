"""Tests for Sprint 19 — Capability security & secrets.

Covers:
- Denied-by-default matrix for sensitive capabilities
- Redaction of known secret patterns
- Effect authorization context (actor, principal, resource, scope)
- Secrets store (EnvSecretStore, LocalSecretStore)
- RedactionGuard integration
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from voodoo.primitives.capability import Capability
from voodoo.primitives.effect import Effect
from voodoo.runtime.capability import (
    SENSITIVE_CAPABILITIES,
    CapabilityResolver,
    Resolution,
)
from voodoo.runtime.context import ExecutionContext
from voodoo.runtime.errors import CapabilityDenied

# ---------------------------------------------------------------------------
# Denied-by-default matrix
# ---------------------------------------------------------------------------


class TestSensitiveCapabilityMatrix:
    """Every sensitive capability is denied when not explicitly granted."""

    @pytest.mark.parametrize("cap_name", sorted(SENSITIVE_CAPABILITIES))
    def test_denied_without_grant(self, cap_name: str) -> None:
        resolver = CapabilityResolver()
        ctx = ExecutionContext(actor="agent-1")
        assert resolver.resolve(cap_name, context=ctx) is Resolution.DENIED

    @pytest.mark.parametrize("cap_name", sorted(SENSITIVE_CAPABILITIES))
    def test_allowed_with_context_grant(self, cap_name: str) -> None:
        resolver = CapabilityResolver()
        ctx = ExecutionContext(actor="agent-1")
        ctx.grant(Capability(name=cap_name))
        assert resolver.resolve(cap_name, context=ctx) is Resolution.ALLOWED

    @pytest.mark.parametrize("cap_name", sorted(SENSITIVE_CAPABILITIES))
    def test_allowed_with_registry_grant(self, cap_name: str) -> None:
        resolver = CapabilityResolver()
        resolver.register(Capability(name=cap_name))
        assert resolver.resolve(cap_name) is Resolution.ALLOWED

    @pytest.mark.parametrize("cap_name", sorted(SENSITIVE_CAPABILITIES))
    def test_authorize_raises_when_denied(self, cap_name: str) -> None:
        resolver = CapabilityResolver()
        ctx = ExecutionContext(actor="agent-1")
        with pytest.raises(CapabilityDenied) as exc_info:
            resolver.authorize(cap_name, context=ctx, execution_id="exec-1")
        assert cap_name in str(exc_info.value)
        assert "agent-1" in str(exc_info.value)

    def test_nonsensitive_capability_uses_default_rules(self) -> None:
        """Non-sensitive capabilities follow the normal registry rules."""
        resolver = CapabilityResolver()
        # "chat.read" is not sensitive — should be denied only because
        # it's not registered, not because of the sensitive guard.
        assert resolver.resolve("chat.read") is Resolution.DENIED
        resolver.register(Capability(name="chat.read"))
        assert resolver.resolve("chat.read") is Resolution.ALLOWED

    def test_sensitive_set_is_frozen(self) -> None:
        assert isinstance(SENSITIVE_CAPABILITIES, frozenset)
        assert len(SENSITIVE_CAPABILITIES) >= 6

    def test_describe_includes_sensitive(self) -> None:
        resolver = CapabilityResolver()
        desc = resolver.describe()
        assert "sensitive" in desc
        assert set(desc["sensitive"]) == SENSITIVE_CAPABILITIES


# ---------------------------------------------------------------------------
# Effect authorization context
# ---------------------------------------------------------------------------


class TestEffectAuthContext:
    """Effects carry actor/principal/resource/scope (ROADMAP §55)."""

    def test_effect_has_auth_fields(self) -> None:
        e = Effect(name="send_email")
        assert e.actor is None
        assert e.principal is None
        assert e.resource is None
        assert e.scope is None

    def test_effect_auth_fields_populated(self) -> None:
        e = Effect(
            name="write_file",
            actor="agent-1",
            principal="user-42",
            resource="/tmp/data.csv",
            scope="filesystem.write",
        )
        assert e.actor == "agent-1"
        assert e.principal == "user-42"
        assert e.resource == "/tmp/data.csv"
        assert e.scope == "filesystem.write"

    def test_describe_includes_auth_context(self) -> None:
        e = Effect(name="send_email", actor="agent-1", resource="user@example.com")
        desc = e.describe()
        assert desc["actor"] == "agent-1"
        assert desc["resource"] == "user@example.com"
        assert "principal" in desc
        assert "scope" in desc

    def test_effect_context_roundtrip(self) -> None:
        """Authorization context survives serialization."""
        e = Effect(
            name="api_call",
            actor="worker-1",
            principal="svc-account",
            resource="https://api.example.com",
            scope="network.request",
        )
        data = e.model_dump()
        e2 = Effect.model_validate(data)
        assert e2.actor == "worker-1"
        assert e2.principal == "svc-account"
        assert e2.resource == "https://api.example.com"
        assert e2.scope == "network.request"


# ---------------------------------------------------------------------------
# Secrets store
# ---------------------------------------------------------------------------


class TestEnvSecretStore:
    """EnvSecretStore reads from environment variables."""

    def test_get_existing_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from voodoo.security.secrets import EnvSecretStore

        monkeypatch.setenv("TEST_SECRET_VALUE", "hunter2")
        store = EnvSecretStore()
        assert store.get("TEST_SECRET_VALUE") == "hunter2"

    def test_get_missing_var(self) -> None:
        from voodoo.security.secrets import EnvSecretStore

        store = EnvSecretStore()
        assert store.get("NONEXISTENT_SECRET_XYZ_123") is None

    def test_has_existing_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from voodoo.security.secrets import EnvSecretStore

        monkeypatch.setenv("TEST_SECRET_EXISTS", "yes")
        store = EnvSecretStore()
        assert store.has("TEST_SECRET_EXISTS") is True

    def test_has_missing_var(self) -> None:
        from voodoo.security.secrets import EnvSecretStore

        store = EnvSecretStore()
        assert store.has("NONEXISTENT_SECRET_XYZ_123") is False


class TestLocalSecretStore:
    """LocalSecretStore reads/writes encrypted JSON files."""

    def test_get_from_plain_json(self, tmp_path: Path) -> None:
        """Without cryptography, falls back to plain JSON."""
        from voodoo.security.secrets import LocalSecretStore

        secrets_file = tmp_path / "secrets.json"
        secrets_file.write_text(json.dumps({"API_KEY": "sk-abc123"}))
        store = LocalSecretStore(secrets_file)
        assert store.get("API_KEY") == "sk-abc123"
        assert store.has("API_KEY") is True
        assert store.has("MISSING") is False

    def test_set_creates_file(self, tmp_path: Path) -> None:
        from voodoo.security.secrets import LocalSecretStore

        secrets_file = tmp_path / "secrets.json"
        store = LocalSecretStore(secrets_file)
        store.set("NEW_KEY", "new-value")
        assert store.get("NEW_KEY") == "new-value"

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        from voodoo.security.secrets import LocalSecretStore

        store = LocalSecretStore(tmp_path / "nope.json")
        assert store.get("anything") is None

    def test_get_missing_key(self, tmp_path: Path) -> None:
        from voodoo.security.secrets import LocalSecretStore

        secrets_file = tmp_path / "secrets.json"
        secrets_file.write_text(json.dumps({"KEY": "val"}))
        store = LocalSecretStore(secrets_file)
        assert store.get("OTHER") is None


class TestSecretsModuleAPI:
    """Module-level secrets.get() / secrets.has() convenience functions."""

    def test_module_get(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import sys

        secrets_mod = sys.modules["voodoo.security.secrets"]

        monkeypatch.setenv("VOODOO_TEST_MODULE_SECRET", "found")
        assert secrets_mod.get("VOODOO_TEST_MODULE_SECRET") == "found"

    def test_module_has(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import sys

        secrets_mod = sys.modules["voodoo.security.secrets"]

        monkeypatch.setenv("VOODOO_TEST_MODULE_HAS", "1")
        assert secrets_mod.has("VOODOO_TEST_MODULE_HAS") is True

    def test_configure_rejects_invalid(self) -> None:
        import sys

        secrets_mod = sys.modules["voodoo.security.secrets"]

        with pytest.raises(TypeError, match="SecretStore"):
            secrets_mod.configure("not a store")  # type: ignore[arg-type]

    def test_register_name(self) -> None:
        import sys

        secrets_mod = sys.modules["voodoo.security.secrets"]

        secrets_mod.register_name("MY_API_KEY")
        assert "MY_API_KEY" in secrets_mod.registered_names()


# ---------------------------------------------------------------------------
# Redaction guard
# ---------------------------------------------------------------------------


class TestRedactionGuard:
    """RedactionGuard scrubs secrets from data structures."""

    def test_redact_sensitive_key(self) -> None:
        from voodoo.security.redaction import redact

        data = {"api_key": "sk-abc123", "name": "test"}
        result = redact(data)
        assert result["api_key"] == "[REDACTED]"
        assert result["name"] == "test"

    def test_redact_nested_dict(self) -> None:
        from voodoo.security.redaction import redact

        data = {
            "config": {
                "token": "secret-token-value",
                "debug": True,
            },
            "items": [{"password": "hunter2", "id": 1}],
        }
        result = redact(data)
        assert result["config"]["token"] == "[REDACTED]"
        assert result["config"]["debug"] is True
        assert result["items"][0]["password"] == "[REDACTED]"
        assert result["items"][0]["id"] == 1

    def test_redact_known_value(self) -> None:
        from voodoo.security.redaction import RedactionGuard

        guard = RedactionGuard()
        guard.add_value("my-super-secret-value")
        result = guard.redact("the secret is my-super-secret-value here")
        assert "my-super-secret-value" not in result
        assert "[REDACTED]" in result

    def test_redact_bearer_token(self) -> None:
        from voodoo.security.redaction import redact_string

        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc123"
        result = redact_string(text)
        assert "Bearer" not in result or "[REDACTED]" in result

    def test_redact_sk_key_pattern(self) -> None:
        from voodoo.security.redaction import redact_string

        text = "Using key sk-abcdefghijklmnopqrstuvwxyz"
        result = redact_string(text)
        assert "sk-abcdefghijklmnopqrstuvwxyz" not in result
        assert "[REDACTED]" in result

    def test_redact_aws_key_pattern(self) -> None:
        from voodoo.security.redaction import redact_string

        text = "Access key: AKIAIOSFODNN7EXAMPLE"
        result = redact_string(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert "[REDACTED]" in result

    def test_redact_password_in_uri(self) -> None:
        from voodoo.security.redaction import redact_string

        text = "postgresql://admin:secretpass@localhost:5432/db"
        result = redact_string(text)
        assert "secretpass" not in result
        assert "postgresql://" in result
        assert "localhost" in result

    def test_redact_jwt_token(self) -> None:
        from voodoo.security.redaction import redact_string

        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        result = redact_string(jwt)
        assert jwt not in result
        assert "[REDACTED]" in result

    def test_redact_passthrough_types(self) -> None:
        from voodoo.security.redaction import redact

        assert redact(42) == 42
        assert redact(3.14) == 3.14
        assert redact(True) is True
        assert redact(None) is None

    def test_redact_list(self) -> None:
        from voodoo.security.redaction import redact

        data = [{"token": "abc"}, {"name": "safe"}]
        result = redact(data)
        assert result[0]["token"] == "[REDACTED]"
        assert result[1]["name"] == "safe"

    def test_redact_secret_key_patterns(self) -> None:
        """Various key-name patterns are all caught."""
        from voodoo.security.redaction import redact

        for key in [
            "secret",
            "password",
            "passwd",
            "api_key",
            "api-key",
            "token",
            "auth_token",
            "private_key",
            "access_key",
            "session_id",
            "cookie",
        ]:
            result = redact({key: "should-be-redacted"})
            assert result[key] == "[REDACTED]", f"key '{key}' was not redacted"

    def test_load_secrets_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from voodoo.security.redaction import RedactionGuard

        monkeypatch.setenv("REDACTION_TEST_SECRET", "super-secret-value-123")
        guard = RedactionGuard()
        guard.load_secrets({"REDACTION_TEST_SECRET"})
        result = guard.redact("the value is super-secret-value-123 here")
        assert "super-secret-value-123" not in result
        assert "[REDACTED]" in result


# ---------------------------------------------------------------------------
# Redaction in engine events
# ---------------------------------------------------------------------------


class TestRedactionInEngine:
    """Secrets are redacted from engine event payloads."""

    @pytest.mark.asyncio
    async def test_emit_redacts_payload(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Engine._emit applies redaction before broadcasting."""
        from voodoo.primitives.intent import Intent
        from voodoo.runtime.engine import ExecutionEngine

        captured: list[tuple[str, dict[str, Any]]] = []

        async def fake_broadcast(event: str, payload: dict[str, Any]) -> None:
            captured.append((event, payload))

        monkeypatch.setattr("voodoo.mesh.broadcast", fake_broadcast)

        engine = ExecutionEngine()
        Intent(name="test", params={"api_key": "sk-secret123"})  # noqa: F841
        await engine._emit("test.event", {"data": {"token": "abc123"}})

        assert len(captured) == 1
        _, payload = captured[0]
        assert payload["data"]["token"] == "[REDACTED]"

    @pytest.mark.asyncio
    async def test_journal_redacts_payload(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Engine._journal_approval_decision applies redaction."""
        from voodoo.runtime.engine import ExecutionEngine

        captured: list[dict[str, Any]] = []

        class FakeStore:
            def append_event(self, exec_id: str, event: str, payload: dict) -> None:
                captured.append(payload)

        engine = ExecutionEngine()
        engine._execution_store = FakeStore()
        engine._journal_approval_decision(
            "exec-1",
            "approval.granted",
            {"by": "admin", "secret_note": "password123"},
        )

        assert len(captured) == 1
        assert captured[0]["secret_note"] == "[REDACTED]"
        assert captured[0]["by"] == "admin"
