"""Sprint 28.2 acceptance for the application-owned Voodoo Store lifecycle."""

from pathlib import Path

from starlette.testclient import TestClient

from voodoo.core.app import create_app


def test_app_opens_and_closes_voodoo_store_by_default(
    tmp_path: Path, monkeypatch
) -> None:
    store_path = tmp_path / "application.vstore"
    monkeypatch.setenv("VOODOO_STORE_PATH", str(store_path))
    monkeypatch.delenv("VOODOO_STORE_ENABLED", raising=False)

    app = create_app(app_dir=str(tmp_path / "app"))

    with TestClient(app):
        runtime_store = app.state.runtime_store
        assert runtime_store.started is True
        assert runtime_store.provider is not None
        assert runtime_store.provider.name == "voodoo"
        assert runtime_store.provider.path == store_path
        assert store_path.exists()

    assert runtime_store.started is False
    assert runtime_store.provider is None
    assert store_path.exists()


def test_app_can_explicitly_disable_default_store(tmp_path: Path, monkeypatch) -> None:
    store_path = tmp_path / "disabled.vstore"
    monkeypatch.setenv("VOODOO_STORE_PATH", str(store_path))
    monkeypatch.setenv("VOODOO_STORE_ENABLED", "false")

    app = create_app(app_dir=str(tmp_path / "app"))

    with TestClient(app):
        runtime_store = app.state.runtime_store
        assert runtime_store.started is False
        assert runtime_store.provider is None

    assert not store_path.exists()
