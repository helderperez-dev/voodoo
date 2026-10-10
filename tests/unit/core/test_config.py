"""Tests for Sprint 9 runtime configuration, env interpolation, precedence, and validation."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from voodoo.adapters.registry import ProviderRegistry
from voodoo.config import (
    CacheConfig,
    DatabaseConfig,
    EventsConfig,
    ObjectsConfig,
    QueueConfig,
    ThemeConfig,
    VoodooConfig,
    get_config,
    interpolate_env_vars,
    validate_production_config,
)
from voodoo.core.errors import ConfigurationError


class TestProductionConfiguration:
    """Production mode rejects development security behavior."""

    def test_production_defaults_are_browser_safe(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("VOODOO_ENV", "production")
        monkeypatch.delenv("VOODOO_CORS_ORIGINS", raising=False)
        monkeypatch.delenv("VOODOO_CORS_ALLOW_CREDENTIALS", raising=False)
        monkeypatch.delenv("VOODOO_CSRF_ENABLED", raising=False)

        resolved = get_config(overrides={"auth": {"secret_key": "x" * 48}})

        assert resolved.debug is False
        assert resolved.auth.cookie_secure is True
        assert resolved.security.hsts_enabled is True
        assert resolved.security.csrf_enabled is True
        assert resolved.security.cors_origins == []
        assert resolved.security.cors_allow_credentials is False
        assert resolved.security.cors_allow_methods == [
            "GET",
            "HEAD",
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
            "OPTIONS",
        ]
        assert "*" not in resolved.security.cors_allow_headers
        assert "X-CSRF-Token" in resolved.security.cors_allow_headers
        assert resolved.security.permissions_policy == (
            "camera=(), geolocation=(), microphone=(), payment=(), usb=()"
        )
        assert resolved.security.csp_directives["script-src"] == "'self'"
        assert resolved.security.csp_directives["style-src"] == "'self'"
        validate_production_config(resolved)

    def test_default_signing_secret_is_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("VOODOO_ENV", "production")
        monkeypatch.delenv("VOODOO_SECRET_KEY", raising=False)

        with pytest.raises(ConfigurationError, match="VOODOO_SECRET_KEY"):
            validate_production_config(get_config(overrides={}))

    @pytest.mark.parametrize(
        ("overrides", "message"),
        [
            ({"debug": True}, "debug mode"),
            ({"auth": {"cookie_secure": False}}, "cookies must use Secure"),
            ({"security": {"hsts_enabled": False}}, "HSTS"),
            ({"security": {"csrf_enabled": False}}, "CSRF"),
            (
                {
                    "security": {
                        "cors_origins": ["*"],
                        "cors_allow_credentials": True,
                    }
                },
                "credentialed CORS",
            ),
            (
                {"security": {"cors_allow_methods": ["*"]}},
                "CORS methods",
            ),
            (
                {"security": {"cors_allow_headers": ["*"]}},
                "CORS headers",
            ),
            (
                {"security": {"permissions_policy": "camera=*"}},
                "Permissions-Policy",
            ),
            (
                {"security": {"cors_origins": ["https://example.com/docs"]}},
                "absolute HTTP",
            ),
            (
                {"security": {"cors_origins": ["https://example.com:bad"]}},
                "absolute HTTP",
            ),
            (
                {"security": {"cors_origins": ["https://user:pass@example.com"]}},
                "absolute HTTP",
            ),
            (
                {"security": {"cors_origins": ["*"]}},
                "wildcard",
            ),
            (
                {
                    "security": {
                        "csp_directives": {
                            "default-src": "'self'",
                            "script-src": "'self' 'unsafe-inline'",
                        }
                    }
                },
                "unsafe-inline",
            ),
            (
                {
                    "security": {
                        "csp_directives": {
                            "default-src": "'self'",
                            "script-src": "'self'",
                            "style-src": "'self' 'unsafe-inline'",
                        }
                    }
                },
                "style-src",
            ),
        ],
    )
    def test_unsafe_production_overrides_are_rejected(
        self,
        monkeypatch: pytest.MonkeyPatch,
        overrides: dict[str, object],
        message: str,
    ) -> None:
        monkeypatch.setenv("VOODOO_ENV", "production")
        monkeypatch.setenv("VOODOO_SECRET_KEY", "unique-production-secret-" * 2)

        with pytest.raises(ConfigurationError, match=message):
            validate_production_config(get_config(overrides=overrides))

    def test_security_limits_reject_non_positive_or_unbounded_values(self) -> None:
        from voodoo.config import AuthConfig, SecurityConfig

        with pytest.raises(ValidationError):
            SecurityConfig(rate_limit_requests=0)
        with pytest.raises(ValidationError):
            SecurityConfig(rate_limit_window=86_401)
        with pytest.raises(ValidationError):
            AuthConfig(token_expiry_seconds=0)
        with pytest.raises(ValidationError):
            ObjectsConfig(max_upload_bytes=10 * 1024 * 1024 * 1024 + 1)


def test_env_interpolation():
    os.environ["TEST_ENV_VAR"] = "production_db_url"
    os.environ["TEST_PORT"] = "9000"

    raw = {
        "database": {"url": "${TEST_ENV_VAR}"},
        "port": "${TEST_PORT}",
        "fallback": "${NON_EXISTENT_VAR:default_value}",
        "empty_fallback": "${NON_EXISTENT_VAR:}",
        "missing": "${MISSING_VAR}",
        "nested": {
            "list": ["item1", "${TEST_ENV_VAR}"],
        },
    }

    interpolated = interpolate_env_vars(raw)
    assert interpolated["database"]["url"] == "production_db_url"
    assert interpolated["port"] == "9000"
    assert interpolated["fallback"] == "default_value"
    assert interpolated["empty_fallback"] == ""
    assert interpolated["missing"] == ""
    assert interpolated["nested"]["list"] == ["item1", "production_db_url"]


def test_config_precedence():
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = Path(tmpdir) / "voodoo.yaml"
        yaml_content = {
            "runtime": {"mode": "production"},
            "queue": {"provider": "memory"},
            "database": {"provider": "sqlite", "path": ":memory:"},
            "events": {"provider": "local"},
            "objects": {"provider": "local"},
        }
        with open(yaml_path, "w") as f:
            yaml.dump(yaml_content, f)

        # 1. File config wins over env vars
        os.environ["VOODOO_QUEUE_PROVIDER"] = "sqlite"
        cfg = get_config(str(yaml_path))
        assert cfg.runtime.mode == "production"
        assert cfg.queue.provider == "memory"
        assert cfg.events.provider == "local"

        # 2. Env vars win when file config doesn't specify
        yaml_content_partial = {
            "runtime": {"mode": "staging"},
        }
        with open(yaml_path, "w") as f:
            yaml.dump(yaml_content_partial, f)

        os.environ["VOODOO_QUEUE_PROVIDER"] = "memory"
        cfg_env = get_config(str(yaml_path))
        assert cfg_env.runtime.mode == "staging"
        assert cfg_env.queue.provider == "memory"

        # 3. Default zero-infra converges on Voodoo Store
        os.environ.pop("VOODOO_QUEUE_PROVIDER", None)
        cfg_default = get_config(str(yaml_path))
        assert cfg_default.queue.provider == "voodoo"
        assert cfg_default.database.provider == "voodoo"
        assert cfg_default.events.provider == "voodoo"
        assert cfg_default.objects.provider == "voodoo"


def test_provider_registry_and_errors():
    reg = ProviderRegistry()

    # Valid retrievals
    db = reg.get_database(DatabaseConfig(provider="sqlite", path=":memory:"))
    assert db is not None

    q_mem = reg.get_queue(QueueConfig(provider="memory"))
    assert q_mem is not None

    events_local = reg.get_events(EventsConfig(provider="local"))
    assert events_local is not None

    objects_local = reg.get_objects(
        ObjectsConfig(provider="local", base_dir="/tmp/test_obj")
    )
    assert objects_local is not None

    # Sprint 12 regression: the s3 factory previously passed access_key/
    # secret_key/region kwargs that S3ObjectStore.__init__ rejected, so
    # provider="s3" raised TypeError. The factory must construct the store
    # (use_s3 False without credentials) without raising.
    objects_s3 = reg.get_objects(ObjectsConfig(provider="s3", bucket="b"))
    assert objects_s3 is not None
    assert objects_s3.provider == "s3"
    assert not objects_s3.use_s3

    cache_mem = reg.get_cache(CacheConfig(provider="memory"))
    assert cache_mem is not None

    # Unknown providers raise actionable ConfigurationError
    with pytest.raises(ConfigurationError) as exc_info:
        reg.get_queue(QueueConfig(provider="unknown_queue"))
    assert "Unknown queue provider 'unknown_queue'" in str(exc_info.value)
    assert "memory" in str(exc_info.value)
    assert "sqlite" in str(exc_info.value)

    with pytest.raises(ConfigurationError) as exc_info:
        reg.get_database(DatabaseConfig(provider="nonexistent_db"))
    assert "Unknown database provider 'nonexistent_db'" in str(exc_info.value)


def test_theme_block_parses_and_keeps_extra_keys():
    # Sprint 9 regression: a ``theme:`` block in voodoo.yaml referenced an
    # undefined ThemeConfig and would crash get_config() with a NameError.
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = Path(tmpdir) / "voodoo.yaml"
        yaml_content = {
            "theme": {"mode": "light", "colors": {"primary": "#ff0000"}},
        }
        with open(yaml_path, "w") as f:
            yaml.dump(yaml_content, f)

        cfg = get_config(str(yaml_path))
        assert isinstance(cfg.theme, ThemeConfig)
        assert cfg.theme.mode == "light"
        assert cfg.theme.colors == {"primary": "#ff0000"}
        assert "theme" not in cfg.extra


def test_ai_block_parses_and_env_fallbacks():
    from voodoo.config import AIConfig

    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = Path(tmpdir) / "voodoo.yaml"
        yaml_content = {
            "ai": {
                "provider": "openai",
                "model": "deepseek-chat",
                "base_url": "https://api.deepseek.com/v1",
                "api_key": "${DEEPSEEK_TEST_KEY}",
                "aliases": {"agent": "openai:deepseek-chat"},
            },
        }
        os.environ["DEEPSEEK_TEST_KEY"] = "sk-test-123"
        try:
            with open(yaml_path, "w") as f:
                yaml.dump(yaml_content, f)

                cfg = get_config(str(yaml_path))
                assert isinstance(cfg.ai, AIConfig)
                assert cfg.ai.provider == "openai"
                assert cfg.ai.model == "deepseek-chat"
                assert cfg.ai.base_url == "https://api.deepseek.com/v1"
                assert cfg.ai.api_key == "sk-test-123"
                assert cfg.ai.aliases == {"agent": "openai:deepseek-chat"}
                assert "ai" not in cfg.extra
        finally:
            os.environ.pop("DEEPSEEK_TEST_KEY", None)

        with open(yaml_path, "w") as f:
            yaml.dump({"runtime": {"mode": "development"}}, f)

        env_pairs = {
            "VOODOO_AI_PROVIDER": "openai",
            "VOODOO_AI_MODEL": "deepseek-reasoner",
            "VOODOO_AI_BASE_URL": "https://api.deepseek.com/v1",
            "VOODOO_AI_API_KEY": "sk-env-456",
        }
        saved = {k: os.environ.get(k) for k in env_pairs}
        try:
            os.environ.update(env_pairs)
            cfg_env = get_config(str(yaml_path))
            assert cfg_env.ai.provider == "openai"
            assert cfg_env.ai.model == "deepseek-reasoner"
            assert cfg_env.ai.base_url == "https://api.deepseek.com/v1"
            assert cfg_env.ai.api_key == "sk-env-456"
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


def test_runtime_run_api_through_runtime_flag():
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = Path(tmpdir) / "voodoo.yaml"
        with open(yaml_path, "w") as f:
            yaml.dump(
                {"runtime": {"mode": "development", "run_api_through_runtime": False}},
                f,
            )
        cfg = get_config(str(yaml_path))
        assert cfg.runtime.run_api_through_runtime is False

    key = "VOODOO_RUN_API_THROUGH_RUNTIME"
    saved = os.environ.get(key)
    try:
        os.environ[key] = "0"
        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_path = Path(tmpdir) / "voodoo.yaml"
            with open(yaml_path, "w") as f:
                yaml.dump({}, f)
            cfg = get_config(str(yaml_path))
            assert cfg.runtime.run_api_through_runtime is False
    finally:
        if saved is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = saved


def test_voodoo_config_theme_default():
    assert VoodooConfig().theme.mode == "dark"
