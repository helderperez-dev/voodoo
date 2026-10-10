"""Validate import statements in Markdown documentation.

The public API is intentionally small. This check prevents documentation from
silently drifting back to removed root-level UI/runtime aliases. It validates
both single-line and parenthesized ``from voodoo... import`` statements without
executing arbitrary documentation snippets.
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path


def _iter_imports(path: Path) -> list[tuple[int, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    found: list[tuple[int, str]] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.startswith("from voodoo "):
            index += 1
            continue
        statement = line
        end = index
        while "(" in statement and ")" not in statement and end + 1 < len(lines):
            end += 1
            statement += "\n" + lines[end]
        found.append((index + 1, statement))
        index = end + 1
    return found


def check(root: Path) -> list[str]:
    errors: list[str] = []
    for path in sorted(root.glob("**/*.md")):
        for line_number, statement in _iter_imports(path):
            try:
                node = ast.parse(statement).body[0]
                if not isinstance(node, ast.ImportFrom) or node.module is None:
                    continue
                module = importlib.import_module(node.module)
            except (ImportError, SyntaxError) as exc:
                errors.append(f"{path}:{line_number}: {exc}")
                continue
            missing = [
                alias.name
                for alias in node.names
                if alias.name != "*" and not hasattr(module, alias.name)
            ]
            if missing:
                errors.append(
                    f"{path}:{line_number}: {node.module} is missing "
                    + ", ".join(missing)
                )
    return errors


def main() -> int:
    errors = check(Path(__file__).parents[1] / "docs")
    if errors:
        print("documentation import validation failed:", file=sys.stderr)
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("documentation import validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
