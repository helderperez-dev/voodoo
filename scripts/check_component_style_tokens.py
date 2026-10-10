"""Ensure stable component source stays semantic and theme-token based."""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

import voodoo.ui as ui

ROOT = Path(__file__).parents[1]
# Scan every Python component module, not only the initial stable-tier files.
# CSS/theme definition modules remain the intentional token-definition layer.
COMPONENT_SOURCES = tuple(
    path
    for path in sorted((ROOT / "src/voodoo/ui").glob("*.py"))
    if path.name != "__init__.py"
)
# These stylesheets are rule layers, not token-definition modules. Keep the
# token-definition layers (theme, palette, presets, and the design-system
# declaration block) explicit so literal values remain legal only at the
# source-of-truth boundary.
STYLESHEET_RULE_SOURCES = tuple(
    ROOT / "src/voodoo/ui/styles" / name
    for name in ("product.py", "extended.py", "voodoo_system.py")
)
RAW_COLOR = re.compile(r"(?:#[0-9a-fA-F]{3,8}|rgba?\s*\()")


def _scan_raw_colors(path: Path, *, label: str = "") -> list[str]:
    prefix = f"{label} " if label else ""
    return [
        f"{prefix}{path.relative_to(ROOT)}:{line_number}"
        for line_number, line in enumerate(path.read_text().splitlines(), start=1)
        if RAW_COLOR.search(line)
    ]


def main() -> int:
    violations: list[str] = []
    for path in COMPONENT_SOURCES:
        violations.extend(_scan_raw_colors(path))
    for path in STYLESHEET_RULE_SOURCES:
        violations.extend(_scan_raw_colors(path, label="stylesheet"))
    manifest = json.loads((ROOT / "docs/component_maturity.json").read_text())
    components = {
        name
        for name in ui.__all__
        if inspect.isclass(getattr(ui, name, None))
        and issubclass(getattr(ui, name), ui.Component)
    }
    for name in sorted(components):
        component = getattr(ui, name, None)
        if component is None:
            violations.append(f"stable component is not exported: {name}")
            continue
        try:
            source = inspect.getsource(component)
        except (OSError, TypeError) as error:
            violations.append(f"{name}: source unavailable ({type(error).__name__})")
            continue
        for line_number, line in enumerate(source.splitlines(), start=1):
            if RAW_COLOR.search(line):
                violations.append(f"stable component {name}:{line_number}")
    if violations:
        raise SystemExit(
            "stable component sources contain raw color values; use semantic tokens: "
            + ", ".join(violations)
        )
    print(
        "component style-token contract passed "
        f"({len(COMPONENT_SOURCES)} modules, {len(components)} exported components, "
        f"{len(manifest.get('stable', []))} stable components)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
