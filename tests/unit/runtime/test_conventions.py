from voodoo.runtime.conventions import discover_layout


def test_layout_discovery_is_descriptive_not_registration(tmp_path):
    pages = tmp_path / "app" / "pages"
    pages.mkdir(parents=True)
    (pages / "home.py").write_text("raise RuntimeError('must not import')")

    layout = discover_layout(tmp_path)

    assert layout.pages == pages


def test_layout_reports_present_conventions_without_importing_modules(tmp_path):
    pages = tmp_path / "app" / "pages"
    goals = tmp_path / "app" / "goals"
    pages.mkdir(parents=True)
    goals.mkdir(parents=True)
    (goals / "danger.py").write_text("raise RuntimeError('must not import')")

    layout = discover_layout(tmp_path)

    assert layout.present() == ("pages", "goals")
    assert layout.describe() == {
        "pages": str(pages),
        "goals": str(goals),
    }
