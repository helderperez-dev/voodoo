"""Run dependency-free semantic accessibility checks for stable components."""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

import voodoo.ui as ui
from voodoo.ui import Component

EXAMPLES: dict[str, tuple[object, ...]] = {
    "A": ("Link",),
    "Alert": ("Message",),
    "Badge": ("New",),
    "Button": ("Save",),
    "Card": ("Content",),
    "Container": ("Content",),
    "Div": ("Content",),
    "Flex": ("Content",),
    "Form": ("Fields",),
    "Grid": ("Content",),
    "Heading": ("Title",),
    "Input": (),
    "Label": ("Name",),
    "Page": ("Content",),
    "Stack": ("Content",),
    "Text": ("Content",),
}


def _opening(rendered: str) -> tuple[str, str]:
    match = re.match(r"^<([a-z0-9]+)([^>]*)>", rendered)
    if match is None:
        raise SystemExit("stable component did not render an HTML opening tag")
    return match.group(1), match.group(2)


def _validate_interactive_states() -> None:
    disabled_button = ui.Button(
        "Save", disabled=True, render_key="contract/button-disabled"
    ).render()
    if "disabled" not in disabled_button.lower():
        raise SystemExit("Button disabled state must render a disabled attribute")
    loading_button = ui.Button(
        "Save", loading=True, render_key="contract/button-loading"
    ).render()
    if 'aria-busy="true"' not in loading_button:
        raise SystemExit("Button loading state must announce aria-busy")
    disabled_input = ui.Input(
        disabled=True, render_key="contract/input-disabled"
    ).render()
    if "disabled" not in disabled_input.lower():
        raise SystemExit("Input disabled state must render a disabled attribute")
    submitted_form = ui.Form(
        submit="Save", render_key="contract/form-submit"
    ).render()
    if 'type="submit"' not in submitted_form:
        raise SystemExit("Form submit shortcut must render a submit control")


def _validate_deterministic_identity(stable: set[str]) -> None:
    """Every stable component must honor deterministic render-tree identity."""
    for name in sorted(stable):
        component_type = getattr(ui, name)
        example = EXAMPLES[name]
        first = component_type(*example, render_key=f"contract/{name}")
        second = component_type(*example, render_key=f"contract/{name}")
        if first.id is None or first.id != second.id:
            raise SystemExit(f"{name} render_key did not produce deterministic identity")
        if not first.id.startswith(f"vd-{name.lower()}-"):
            raise SystemExit(f"{name} render_key identity has an unstable prefix")
        explicit = component_type(
            *example, id=f"explicit-{name.lower()}", render_key=f"contract/{name}"
        )
        if explicit.id != f"explicit-{name.lower()}":
            raise SystemExit(f"{name} explicit id must take precedence over render_key")


def _validate_exported_component_sources(exported: set[str]) -> None:
    """Apply source-level safety checks to every exported component.

    Components may be experimental, but none should smuggle executable script
    tags or inline event handlers into rendered HTML. Stable components also
    receive the stronger runtime semantic checks below.
    """
    violations: list[str] = []
    for name in sorted(exported):
        component_type = getattr(ui, name)
        try:
            source = inspect.getsource(component_type).lower()
        except (OSError, TypeError) as error:
            violations.append(f"{name}: source unavailable ({type(error).__name__})")
            continue
        if "<script" in source:
            violations.append(f"{name}: script tag")
        if "onclick=" in source or "onkeydown=" in source:
            violations.append(f"{name}: inline event handler")
    if violations:
        raise SystemExit("exported component source safety violations: " + ", ".join(violations))


def _parse_wcag_rows(path: Path) -> list[tuple[str, str, str, str]]:
    rows: list[tuple[str, str, str, str]] = []
    for line in path.read_text().splitlines():
        if not line.startswith("|") or line.startswith("| ---"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 4 or not re.match(r"^\d+\.\d+\.\d+ ", cells[0]):
            continue
        rows.append((cells[0], cells[1], cells[2], cells[3]))
    return rows


def _validate_wcag_row(row: tuple[str, str, str, str]) -> None:
    criterion, evidence, status, release_evidence = row
    allowed = {"automated", "manual-required", "not-applicable"}
    if status not in allowed:
        raise SystemExit(f"invalid WCAG evidence status for {criterion}: {status}")
    if not evidence or not release_evidence:
        raise SystemExit(f"WCAG evidence row is incomplete: {criterion}")
    if status == "manual-required" and not any(
        marker in release_evidence.lower() for marker in ("manual", "hosted")
    ):
        raise SystemExit(
            f"manual WCAG criterion must name manual release evidence: {criterion}"
        )


def _validate_wcag_register(root: Path) -> None:
    """Validate the checked-in WCAG evidence register as a release contract."""
    path = root / "docs/accessibility/WCAG_2_2_AA_EVIDENCE.md"
    if not path.is_file():
        raise SystemExit(f"missing WCAG evidence register: {path}")
    rows = _parse_wcag_rows(path)
    if len(rows) < 10:
        raise SystemExit("WCAG evidence register must list at least 10 criteria")
    for row in rows:
        _validate_wcag_row(row)
    if not any(status == "manual-required" for _c, _e, status, _r in rows):
        raise SystemExit("WCAG register must retain explicit manual-required criteria")


def main() -> int:
    root = Path(__file__).parents[1]
    _validate_wcag_register(root)
    manifest = json.loads((root / "docs/component_maturity.json").read_text())
    exported = {
        name
        for name in ui.__all__
        if inspect.isclass(getattr(ui, name, None))
        and issubclass(getattr(ui, name), Component)
    }
    stable = set(manifest.get("stable", []))
    _validate_exported_component_sources(exported)
    for name in sorted(stable):
        if name not in EXAMPLES or name not in exported:
            raise SystemExit(f"missing accessibility example for stable component: {name}")
        rendered = getattr(ui, name)(*EXAMPLES[name]).render()
        tag, attrs = _opening(rendered)
        lowered = attrs.lower()
        if "<script" in rendered.lower():
            raise SystemExit(f"stable component emitted script content: {name}")
        if "onclick=" in lowered or "onkeydown=" in lowered:
            raise SystemExit(f"stable component emitted inline event handler: {name}")
        if name == "A" and tag != "a":
            raise SystemExit("A must render a semantic anchor")
        if name == "Button" and (tag != "button" or "type=" not in lowered):
            raise SystemExit("Button must render <button> with an explicit type")
        if name == "Input" and (tag != "input" or "type=" not in lowered):
            raise SystemExit("Input must render <input> with an explicit type")
        if name == "Label" and (tag != "label" or not re.search(r">\s*\S", rendered)):
            raise SystemExit("Label must render a semantic label with text")
        if name == "Heading" and tag not in {f"h{i}" for i in range(1, 7)}:
            raise SystemExit("Heading must render a semantic heading element")

    _validate_interactive_states()
    _validate_deterministic_identity(stable)
    print(
        f"accessibility contract passed ({len(stable)} stable, "
        f"{len(exported)} exported components)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
