"""Real-browser acceptance for the Voodoo Component Lab.

Opt in with VOODOO_BROWSER_TESTS=1 after installing the browser extra and
Chromium. Normal unit/CI runs skip this module until browser provisioning is
enabled in the protected workflow.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("VOODOO_BROWSER_TESTS") != "1",
    reason="set VOODOO_BROWSER_TESTS=1 to run real-browser UI acceptance",
)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="module")
def component_lab_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    root = Path(__file__).resolve().parents[2]
    workdir = tmp_path_factory.mktemp("component-lab-browser")
    port = _free_port()
    env = os.environ.copy()
    pythonpath = [str(root), str(root / "src")]
    if env.get("PYTHONPATH"):
        pythonpath.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath)
    env["VOODOO_ENV"] = "test"

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "examples.web.component_lab.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=workdir,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=0.5) as response:
                    if response.status == 200:
                        break
            except Exception:
                if process.poll() is not None:
                    pytest.fail("Component Lab server exited before becoming ready")
                time.sleep(0.1)
        else:
            pytest.fail("Component Lab server did not become ready")
        yield url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


@pytest.fixture(scope="module")
def browser_page(component_lab_url: str):
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 960})
        yield page, component_lab_url
        browser.close()


def test_dropdown_keyboard_and_tabs_work_in_browser(browser_page) -> None:
    page, base = browser_page
    page.goto(f"{base}/navigation")

    page.get_by_role("button", name="Actions").click()
    menu = page.get_by_role("menu", name="Project actions")
    assert menu.is_visible()

    page.keyboard.press("Escape")
    assert not menu.is_visible()

    page.get_by_role("tab", name="Activity").click()
    assert page.get_by_text("Activity content").is_visible()
    assert page.get_by_role("tab", name="Activity").get_attribute("aria-selected") == "true"


def test_inputs_focus_and_theme_toggle_are_real_browser_behaviors(browser_page) -> None:
    page, base = browser_page
    page.goto(f"{base}/forms")

    name = page.locator('input[name="name"]')
    name.fill("Ada Lovelace")
    assert name.input_value() == "Ada Lovelace"
    assert page.evaluate("document.activeElement === document.querySelector('input[name=name]')")

    page.goto(base)
    toggle = page.get_by_role("button", name="Toggle theme")
    before = page.locator("html").get_attribute("class") or ""
    toggle.click()
    after = page.locator("html").get_attribute("class") or ""
    assert ("dark" in before.split()) != ("dark" in after.split())


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/foundations",
        "/shell",
        "/chat",
        "/auth",
        "/forms",
        "/navigation",
        "/advanced",
        "/data",
        "/workspace",
        "/system",
        "/feedback",
    ],
)
def test_component_lab_has_no_mobile_horizontal_overflow(browser_page, path: str) -> None:
    page, base = browser_page
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{base}{path}")
    metrics = page.evaluate(
        "() => ({scroll: document.documentElement.scrollWidth, "
        "client: document.documentElement.clientWidth})"
    )
    assert metrics["scroll"] <= metrics["client"] + 1
