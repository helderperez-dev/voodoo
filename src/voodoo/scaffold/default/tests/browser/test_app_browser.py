"""Minimal browser/a11y contract for the generated landing page."""

from __future__ import annotations

import os

from playwright.sync_api import sync_playwright


def test_landing_page_browser_contract() -> None:
    url = os.environ.get("VOODOO_APP_URL", "http://127.0.0.1:8766/")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(url, wait_until="networkidle")
        assert page.locator("main").count() == 1
        assert page.locator("h1").first.inner_text()
        assert page.locator("body").inner_text().find("Your application") >= 0
        browser.close()
