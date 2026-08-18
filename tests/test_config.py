"""Tests for Sprint 9 runtime configuration, env interpolation, precedence, and validation."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from voodoo.adapters.registry import ProviderRegistry
from voodoo.config import (
    CacheConfig,
    DatabaseConfig,
    EventsConfig,
    ObjectsConfig,
    QueueConfig,
    get_config,
    interpolate_env_vars,
)
from voodoo.core.errors import ConfigurationError


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

        # 3. Default zero-infra when nothing specified
        os.environ.pop("VOODOO_QUEUE_PROVIDER", None)
        cfg_default = get_config(str(yaml_path))
        assert cfg_default.queue.provider == "sqlite"
        assert cfg_default.database.provider == "sqlite"
        assert cfg_default.objects.provider == "local"


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
