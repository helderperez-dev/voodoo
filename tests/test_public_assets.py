"""Acceptance tests for the public asset URL contract."""

from starlette.testclient import TestClient

from voodoo import App


def test_public_assets_are_served_from_root_without_shadowing_pages(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "page.py").write_text(
        "from voodoo.ui import Text\n\n"
        "def page(request):\n"
        "    return Text('Application page wins')\n"
    )

    public_dir = tmp_path / "public"
    (public_dir / "assets").mkdir(parents=True)
    (public_dir / "logo.txt").write_text("voodoo-logo")
    (public_dir / "assets" / "icon.txt").write_text("voodoo-icon")
    # A static index must never shadow the application root route.
    (public_dir / "index.html").write_text("STATIC INDEX")

    with TestClient(App(app_dir=str(app_dir))) as client:
        root = client.get("/")
        logo = client.get("/logo.txt")
        nested = client.get("/assets/icon.txt")
        legacy = client.get("/public/logo.txt")
        missing = client.get("/does-not-exist.txt")

    assert root.status_code == 200
    assert "Application page wins" in root.text
    assert "STATIC INDEX" not in root.text

    assert logo.status_code == 200
    assert logo.text == "voodoo-logo"
    assert nested.status_code == 200
    assert nested.text == "voodoo-icon"

    # Preserve the 2.x URL as a compatibility alias while root URLs become canonical.
    assert legacy.status_code == 200
    assert legacy.text == "voodoo-logo"

    assert missing.status_code == 404
