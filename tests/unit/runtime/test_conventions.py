from voodoo.runtime.conventions import discover_layout


def test_layout_discovery_is_descriptive_not_registration(tmp_path):
    pages = tmp_path / "app" / "pages"
    pages.mkdir(parents=True)
    (pages / "home.py").write_text("raise RuntimeError('must not import')")

    layout = discover_layout(tmp_path)

    assert layout.pages == pages
