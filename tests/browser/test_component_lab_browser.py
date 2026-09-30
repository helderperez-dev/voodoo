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
    assert (
        page.get_by_role("tab", name="Activity").get_attribute("aria-selected")
        == "true"
    )


def test_listbox_keyboard_roving_focus_and_selection(browser_page) -> None:
    page, base = browser_page
    page.goto(f"{base}/data")

    python = page.get_by_role("option", name="Python Application language")
    rust = page.get_by_role("option", name="Rust Store core")

    python.focus()
    page.keyboard.press("ArrowDown")
    assert rust.evaluate("(el) => document.activeElement === el")

    page.keyboard.press("Space")
    assert rust.get_attribute("aria-selected") == "true"
    assert python.get_attribute("aria-selected") == "false"


def test_tree_keyboard_navigation_expand_and_collapse(browser_page) -> None:
    page, base = browser_page
    page.goto(f"{base}/workspace")

    tree = page.get_by_role("tree", name="Project files")
    src = tree.locator('[role="treeitem"]').filter(has_text="src").first
    ui = tree.locator('[role="treeitem"]').filter(has_text="ui").first

    assert src.get_attribute("aria-expanded") == "true"
    ui.focus()
    page.keyboard.press("ArrowLeft")
    assert src.evaluate("(el) => document.activeElement === el")

    page.keyboard.press("ArrowLeft")
    assert src.get_attribute("aria-expanded") == "false"

    page.keyboard.press("ArrowRight")
    assert src.get_attribute("aria-expanded") == "true"


def test_modal_traps_focus_and_restores_trigger(browser_page) -> None:
    page, base = browser_page
    page.goto(f"{base}/feedback")

    trigger = page.get_by_role("button", name="Open modal")
    trigger.click()

    dialog = page.get_by_role("dialog")
    assert dialog.is_visible()
    done = dialog.get_by_role("button", name="Done")
    assert done.evaluate("(el) => document.activeElement === el")

    page.keyboard.press("Tab")
    assert done.evaluate("(el) => document.activeElement === el")

    done.click()
    page.wait_for_timeout(250)
    assert not dialog.is_visible()
    assert trigger.evaluate("(el) => document.activeElement === el")


def test_sidebar_switches_between_mobile_and_desktop_modes(browser_page) -> None:
    page, base = browser_page
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{base}/shell")

    sidebar = page.locator("[data-vd-sidebar]")
    assert sidebar.get_attribute("data-vd-sidebar-mode") == "hidden"

    page.set_viewport_size({"width": 1024, "height": 844})
    page.wait_for_timeout(50)
    assert sidebar.get_attribute("data-vd-sidebar-mode") == "expanded"


def test_light_and_dark_renderings_have_distinct_visual_output(browser_page) -> None:
    page, base = browser_page
    page.set_viewport_size({"width": 1024, "height": 768})
    page.goto(base)

    toggle = page.get_by_role("button", name="Toggle theme")
    first_background = page.locator("body").evaluate(
        "(el) => getComputedStyle(el).backgroundColor"
    )
    first_capture = page.screenshot(full_page=True)

    toggle.click()
    second_background = page.locator("body").evaluate(
        "(el) => getComputedStyle(el).backgroundColor"
    )
    second_capture = page.screenshot(full_page=True)

    assert first_background != second_background
    assert first_capture != second_capture
    assert len(first_capture) > 1000
    assert len(second_capture) > 1000


def test_inputs_focus_and_theme_toggle_are_real_browser_behaviors(browser_page) -> None:
    page, base = browser_page
    page.goto(f"{base}/forms")

    name = page.locator('input[name="name"]')
    name.fill("Ada Lovelace")
    assert name.input_value() == "Ada Lovelace"
    assert page.evaluate(
        "document.activeElement === document.querySelector('input[name=name]')"
    )

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
def test_component_lab_has_no_mobile_horizontal_overflow(
    browser_page, path: str
) -> None:
    page, base = browser_page
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{base}{path}")
    metrics = page.evaluate(
        "() => ({scroll: document.documentElement.scrollWidth, "
        "client: document.documentElement.clientWidth})"
    )
    assert metrics["scroll"] <= metrics["client"] + 1
