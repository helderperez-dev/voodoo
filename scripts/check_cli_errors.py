"""Require actionable hints on user-facing CLI error output."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).parents[1]
CLI = ROOT / "src" / "voodoo" / "cli"


def main() -> int:
    violations: list[str] = []
    for path in sorted(CLI.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (
                isinstance(func, ast.Attribute)
                and func.attr == "error"
                and isinstance(func.value, ast.Name)
                and func.value.id == "terminal"
            ):
                continue
            if not any(keyword.arg == "hint" for keyword in node.keywords):
                violations.append(
                    f"{path.relative_to(ROOT)}:{node.lineno}: terminal.error requires hint=..."
                )
    if violations:
        raise SystemExit("CLI error contract failed:\n- " + "\n- ".join(violations))
    print("CLI error contract passed (all terminal errors are actionable)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
