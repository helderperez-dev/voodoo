"""Contract tests for the Sprint 28 Runtime-owned Store provider boundary."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from voodoo.core.errors import ConfigurationError
from voodoo.runtime.store import (
    StoreProvider,
    StoreProviderError,
    VoodooStoreProvider,
)


class FakeNativeStore:
    open_calls = 0
    close_calls = 0
    verify_calls = 0
    fail_open = False
    fail_close = False
    fail_verify = False

    @classmethod
    def reset(cls) -> None:
        cls.open_calls = 0
        cls.close_calls = 0
        cls.verify_calls = 0
        cls.fail_open = False
        cls.fail_close = False
        cls.fail_verify = False

    @classmethod
    def open(
        cls,
        path: Path,
        *,
        durability: str,
        repair_torn_tail: bool,
        max_bytes: int | None,
    ) -> FakeNativeStore:
        cls.open_calls += 1
        if cls.fail_open:
            raise RuntimeError("open failed")
        path.touch()
        instance = cls()
        instance.path = path
        instance.durability = durability
        instance.repair_torn_tail = repair_torn_tail
        instance.max_bytes = max_bytes
        return instance

    @classmethod
    def verify(cls, path: Path) -> SimpleNamespace:
        cls.verify_calls += 1
        if cls.fail_verify:
            raise RuntimeError("corrupt")
        return SimpleNamespace(
            file_bytes=128,
            valid_bytes=128,
            records=4,
            committed_transactions=2,
            pending_transactions=0,
            keys=3,
            has_torn_tail=False,
        )

    def close(self) -> None:
        type(self).close_calls += 1
        if type(self).fail_close:
            raise RuntimeError("close failed")

    def health_report(self) -> dict[str, object]:
        return {
            "store_id": b"secret-id-that-must-not-cross-boundary",
            "compaction_backlog_bytes": 17,
            "lock_contentions_total": 2,
            "queue_ready": 3,
            "queue_oldest_ready_at_ms": 1234,
            "metrics": {
                "commits": 4,
                "commit_latency_max_us": 19,
            },
            "storage": {"file_bytes": 128, "live_bytes": 96},
        }


@pytest.fixture(autouse=True)
def _reset_fake_store() -> None:
    FakeNativeStore.reset()


@pytest.fixture
def native_module(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    module = SimpleNamespace(Store=FakeNativeStore)
    monkeypatch.setattr("voodoo.runtime.store.import_module", lambda _name: module)
    return module


class TestStoreProviderContract:
    def test_voodoo_provider_satisfies_runtime_protocol(self) -> None:
        provider = VoodooStoreProvider()
        assert isinstance(provider, StoreProvider)
        assert provider.name == "voodoo"
        assert provider.path == Path(".voodoo/application.vstore")
        assert provider.opened is False

    def test_native_handle_requires_open_provider(self) -> None:
        provider = VoodooStoreProvider()
        with pytest.raises(StoreProviderError, match="not open"):
            _ = provider.native

    def test_open_creates_parent_and_is_idempotent(
        self, tmp_path: Path, native_module: SimpleNamespace
    ) -> None:
        path = tmp_path / "nested" / "application.vstore"
        provider = VoodooStoreProvider(path, durability="strict")

        provider.open()
        provider.open()

        assert provider.opened is True
        assert path.exists()
        assert FakeNativeStore.open_calls == 1
        assert provider.native.durability == "strict"

    def test_provider_lifecycle_emits_store_spans(
        self, tmp_path: Path, native_module: SimpleNamespace
    ) -> None:
        from voodoo.observability import telemetry_store

        before = len(telemetry_store.metrics["spans"])
        provider = VoodooStoreProvider(tmp_path / "traced.vstore")
        provider.open()
        provider.health()
        provider.close()

        names = [
            span["name"]
            for span in telemetry_store.metrics["spans"][before:]
            if span["name"].startswith("store.")
        ]
        assert names[:3] == ["store.open", "store.metric.open", "store.health"]
        assert "store.metric.recovery.verify" in names
        assert names[-2:] == ["store.close", "store.metric.close"]

    def test_open_rejects_store_over_configured_byte_limit(
        self, tmp_path: Path, native_module: SimpleNamespace
    ) -> None:
        path = tmp_path / "limited.vstore"
        path.write_bytes(b"0123456789")
        provider = VoodooStoreProvider(path, max_bytes=4)

        with pytest.raises(StoreProviderError, match="max_bytes"):
            provider.open()
        assert FakeNativeStore.open_calls == 0

    def test_close_is_idempotent(
        self, tmp_path: Path, native_module: SimpleNamespace
    ) -> None:
        provider = VoodooStoreProvider(tmp_path / "application.vstore")
        provider.open()

        provider.close()
        provider.close()

        assert provider.opened is False
        assert FakeNativeStore.close_calls == 1

    def test_open_failure_is_normalized(
        self, tmp_path: Path, native_module: SimpleNamespace
    ) -> None:
        FakeNativeStore.fail_open = True
        provider = VoodooStoreProvider(tmp_path / "application.vstore")

        with pytest.raises(StoreProviderError, match="Unable to open"):
            provider.open()
        assert provider.opened is False

    def test_close_failure_is_normalized_and_handle_is_released(
        self, tmp_path: Path, native_module: SimpleNamespace
    ) -> None:
        provider = VoodooStoreProvider(tmp_path / "application.vstore")
        provider.open()
        FakeNativeStore.fail_close = True

        with pytest.raises(StoreProviderError, match="Unable to close"):
            provider.close()
        assert provider.opened is False

    def test_missing_binding_has_actionable_configuration_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def missing(_name: str) -> object:
            raise ImportError("missing")

        monkeypatch.setattr("voodoo.runtime.store.import_module", missing)
        provider = VoodooStoreProvider()

        with pytest.raises(ConfigurationError, match="voodoo-store"):
            provider.open()


class TestStoreProviderHealth:
    def test_missing_store_reports_unverified(
        self, tmp_path: Path, native_module: SimpleNamespace
    ) -> None:
        provider = VoodooStoreProvider(tmp_path / "missing.vstore")

        health = provider.health()

        assert health.provider == "voodoo"
        assert health.opened is False
        assert health.verified is False
        assert health.details == {"exists": False}
        assert FakeNativeStore.verify_calls == 0

    def test_health_projects_native_verification_without_leaking_report(
        self, tmp_path: Path, native_module: SimpleNamespace
    ) -> None:
        provider = VoodooStoreProvider(tmp_path / "application.vstore")
        provider.open()

        health = provider.health()

        assert health.opened is True
        assert health.verified is True
        assert health.details["records"] == 4
        assert health.details["committed_transactions"] == 2
        assert health.details["keys"] == 3
        assert health.details["has_torn_tail"] is False
        assert health.details["native_health"]["compaction_backlog_bytes"] == 17
        assert health.details["native_health"]["lock_contentions_total"] == 2
        assert health.details["native_health"]["metrics"]["commits"] == 4
        assert "store_id" not in health.details["native_health"]
        assert FakeNativeStore.verify_calls == 1

    def test_verification_failure_is_health_evidence_not_crash(
        self, tmp_path: Path, native_module: SimpleNamespace
    ) -> None:
        provider = VoodooStoreProvider(tmp_path / "application.vstore")
        provider.open()
        FakeNativeStore.fail_verify = True

        health = provider.health()

        assert health.verified is False
        assert health.details["exists"] is True
        assert "corrupt" in health.details["error"]
