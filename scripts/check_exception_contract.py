"""Reject silent broad exception handlers on framework correctness paths."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).parents[1]
SOURCE = ROOT / "src" / "voodoo"
BROAD = {"Exception", "BaseException"}


def _is_broad_type(node: ast.expr | None) -> bool:
    if node is None:
        return True
    if isinstance(node, ast.Name):
        return node.id in BROAD
    if isinstance(node, ast.Attribute):
        return node.attr in BROAD
    if isinstance(node, ast.Tuple):
        return any(_is_broad_type(item) for item in node.elts)
    return False


def _is_broad(handler: ast.ExceptHandler) -> bool:
    return _is_broad_type(handler.type)


def _has_call_or_raise(handler: ast.ExceptHandler) -> bool:
    return any(
        isinstance(node, ast.Call | ast.Raise)
        for statement in handler.body
        for node in ast.walk(statement)
    )


def main() -> int:
    violations: list[str] = []
    for path in sorted(SOURCE.rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler) or not _is_broad(node):
                continue
            if not _has_call_or_raise(node):
                relative = path.relative_to(ROOT)
                violations.append(
                    f"{relative}:{node.lineno}: broad exception handler silently swallows errors"
                )
    if violations:
        raise SystemExit("\n".join(violations))
    print("exception contract passed (no silent broad handlers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
