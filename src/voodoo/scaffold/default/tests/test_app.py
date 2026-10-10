"""Starter regression tests for the generated application."""

from __future__ import annotations

import importlib


def test_landing_page_renders_semantic_shell() -> None:
    _, page = importlib.import_module("app.page").page(None)
    html = page.render()
    assert "<main" in html
    assert "<h1" in html


def test_landing_page_has_no_inline_script() -> None:
    _, page = importlib.import_module("app.page").page(None)
    assert "<script" not in page.render().lower()
