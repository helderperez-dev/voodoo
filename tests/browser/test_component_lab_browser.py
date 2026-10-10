"""Real-browser acceptance for the Voodoo Component Lab.

Opt in with VOODOO_BROWSER_TESTS=1 after installing the browser extra and a
Playwright browser. Set VOODOO_BROWSER_NAME to chromium, firefox, or webkit
to select the engine; Chromium is the local default.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.browser.visual_signature import distance, signature

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
    browser_name = os.environ.get("VOODOO_BROWSER_NAME", "chromium")
    if browser_name not in {"chromium", "firefox", "webkit"}:
        raise ValueError(
            "VOODOO_BROWSER_NAME must be one of chromium, firefox, or webkit"
        )
    with playwright.sync_playwright() as runtime:
        browser = getattr(runtime, browser_name).launch()
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

    python = page.get_by_role("option", name="Python", exact=True)
    rust = page.get_by_role("option", name="Rust", exact=True)

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
    results = Path(".test-results/browser")
    results.mkdir(parents=True, exist_ok=True)
    first_is_dark = "dark" in (page.locator("html").get_attribute("class") or "")
    first_name = "dark.png" if first_is_dark else "light.png"
    first_capture = page.screenshot(path=str(results / first_name), full_page=True)

    toggle.click()
    second_background = page.locator("body").evaluate(
        "(el) => getComputedStyle(el).backgroundColor"
    )
    second_name = "light.png" if first_is_dark else "dark.png"
    second_capture = page.screenshot(path=str(results / second_name), full_page=True)

    assert first_background != second_background
    assert first_capture != second_capture
    assert len(first_capture) > 1000
    assert len(second_capture) > 1000


def test_form_validation_focus_and_submit_lifecycle(browser_page) -> None:
    page, base = browser_page
    page.goto(f"{base}/forms")

    form = page.locator("form.vd-form")
    project = form.get_by_role("textbox", name="Project name")
    submit = form.get_by_role("button", name="Create project")

    submit.click()
    assert project.evaluate("(el) => el.matches(':invalid')")
    assert project.evaluate("(el) => document.activeElement === el")

    project.fill("Atlas")
    assert project.evaluate("(el) => el.matches(':valid')")
    submit.click()
    assert page.url == f"{base}/forms"
    assert project.input_value() == "Atlas"


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


@pytest.mark.parametrize("path", ["/forms", "/navigation", "/feedback"])
def test_production_surfaces_have_basic_accessible_names(browser_page, path: str) -> None:
    """Catch missing names before visual/browser changes ship."""
    page, base = browser_page
    page.goto(f"{base}{path}")
    violations = page.evaluate(
        """() => {
          const controls = [...document.querySelectorAll('input, textarea, select')]
            .filter((el) => el.type !== 'hidden')
            .filter((el) => {
              const labelled = el.getAttribute('aria-label') || el.getAttribute('aria-labelledby');
              const byFor = el.id && document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
              return !labelled && !byFor && !el.closest('label');
            })
            .map((el) => el.outerHTML);
          const buttons = [...document.querySelectorAll('button')]
            .filter((el) => !(el.textContent || '').trim() && !el.getAttribute('aria-label') && !el.getAttribute('aria-labelledby'))
            .map((el) => el.outerHTML);
          const images = [...document.querySelectorAll('img')]
            .filter((el) => !el.hasAttribute('alt') && el.getAttribute('aria-hidden') !== 'true')
            .map((el) => el.outerHTML);
          return {controls, buttons, images};
        }"""
    )
    assert violations == {"controls": [], "buttons": [], "images": []}


def test_production_surfaces_have_valid_aria_references_and_heading_order(
    browser_page,
) -> None:
    """Browser-rendered stable surfaces must keep their semantic graph intact."""
    page, base = browser_page
    routes = ("/", "/foundations", "/shell", "/forms", "/navigation", "/feedback")
    for path in routes:
        page.goto(f"{base}{path}")
        violations = page.evaluate(
            """() => {
              const ids = [...document.querySelectorAll('[id]')].map(el => el.id);
              const duplicateIds = [...new Set(ids.filter((id, i) => ids.indexOf(id) !== i))];
              const ariaReferences = [...document.querySelectorAll('[aria-labelledby], [aria-describedby], [aria-controls]')]
                .flatMap(el => ['aria-labelledby', 'aria-describedby', 'aria-controls']
                  .filter(name => el.hasAttribute(name))
                  .flatMap(name => (el.getAttribute(name) || '').split(/\\s+/)
                    .filter(Boolean)
                    .filter(id => !document.getElementById(id))
                    .map(id => `${name}:${id}`)));
              const headings = [...document.querySelectorAll('h1, h2, h3, h4, h5, h6')]
                .map(el => Number(el.tagName.slice(1)));
              const skipped = headings.slice(1).some((level, index) => level > headings[index] + 1);
              return {duplicateIds, ariaReferences, skipped};
            }"""
        )
        assert violations == {
            "duplicateIds": [],
            "ariaReferences": [],
            "skipped": False,
        }, path


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


def test_rtl_reduced_motion_zoom_and_long_content_contract(browser_page) -> None:
    """Stable surfaces remain usable under common user preference changes."""
    page, base = browser_page
    page.set_viewport_size({"width": 390, "height": 844})
    page.emulate_media(reduced_motion="reduce")
    page.goto(f"{base}/workspace")
    page.evaluate("document.documentElement.dir = 'rtl'")
    page.evaluate("document.documentElement.lang = 'ar'")
    page.evaluate("document.body.style.zoom = '2'")
    page.wait_for_timeout(50)
    metrics = page.evaluate(
        "() => ({scroll: document.documentElement.scrollWidth, "
        "client: document.documentElement.clientWidth, "
        "motion: getComputedStyle(document.body).animationDuration})"
    )
    assert metrics["scroll"] <= metrics["client"] * 2 + 2
    # Chromium serializes the 0.01ms reduced-motion duration as 1e-05s.
    assert float(metrics["motion"].removesuffix("s")) <= 0.001
    assert page.locator("[role='tree']").is_visible()


def test_touch_targets_and_high_contrast_tokens(browser_page) -> None:
    """Interactive controls expose usable target sizes and contrast tokens."""
    page, base = browser_page
    page.goto(f"{base}/forms")
    page.evaluate("document.documentElement.dataset.contrast = 'high'")
    buttons = page.locator("button")
    for index in range(buttons.count()):
        button = buttons.nth(index)
        if not button.is_visible():
            continue
        box = button.bounding_box()
        assert box is not None
        assert box["width"] >= 24 and box["height"] >= 24, (
            button.get_attribute("class"),
            button.inner_text(),
            box,
        )
    assert page.locator("body").evaluate(
        "(el) => getComputedStyle(el).color"
    )


def test_visual_contract_captures_every_reviewed_case(browser_page) -> None:
    """Capture every reviewed visual state for CI artifact comparison.

    The workflow uploads these captures for human review. Keeping the case
    enumeration in the same test as the contract prevents a newly documented
    state from silently losing browser evidence.
    """
    page, base = browser_page
    root = Path(__file__).resolve().parents[2]
    contract = json.loads(
        (root / "tests/browser/visual_contract.json").read_text()
    )
    viewports = contract["viewports"]
    output = Path(".test-results/browser/visual")
    output.mkdir(parents=True, exist_ok=True)
    baseline_path = root / "tests/browser/visual_baselines.json"
    baselines = json.loads(baseline_path.read_text()) if baseline_path.exists() else {}
    threshold = float(contract["comparison"]["max_pixel_diff_ratio"])
    manifest: list[dict[str, object]] = []
    for case in contract["cases"]:
        width, height = viewports[case["viewport"]]
        page.set_viewport_size({"width": width, "height": height})
        page.goto(f"{base}{case['route']}")
        page.evaluate(
            "({theme, state, density}) => {"
            "document.documentElement.classList.toggle('dark', theme === 'dark');"
            "document.documentElement.dataset.visualState = state;"
            "document.documentElement.dataset.vdDensity = density;"
            "}",
            {
                "theme": case["theme"],
                "state": case["state"],
                "density": case["density"],
            },
        )
        if case["state"] == "focus":
            page.locator("button, a, input, textarea, select").first.focus()
        elif case["state"] == "overlay":
            trigger = page.get_by_role("button", name="Open modal")
            if trigger.count():
                trigger.click()
        elif case["state"] == "long-content":
            page.evaluate("document.body.style.minHeight = '2200px'")
        page.wait_for_timeout(50)
        path = output / f"{case['id']}.png"
        capture = page.screenshot(path=str(path), full_page=True)
        assert len(capture) > 1000, case["id"]
        visual_signature = signature(capture)
        if baselines:
            expected = baselines.get(case["id"])
            assert expected is not None, f"missing visual baseline: {case['id']}"
            assert distance(visual_signature, expected) <= threshold, case["id"]
        manifest.append(
            {
                "id": case["id"],
                "route": case["route"],
                "viewport": [width, height],
                "theme": case["theme"],
                "state": case["state"],
                "density": case["density"],
                "bytes": len(capture),
                "signature": visual_signature,
            }
        )
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
