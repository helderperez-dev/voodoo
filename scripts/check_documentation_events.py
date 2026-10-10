"""Reject inline browser handlers in the canonical component guide."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
GUIDE = ROOT / "docs/components.md"
INLINE_HANDLER = re.compile(r"\bon(?:click|change|input|submit|keydown|keyup)\s*=", re.I)


def main() -> int:
    text = GUIDE.read_text(encoding="utf-8")
    match = INLINE_HANDLER.search(text)
    if match:
        line = text.count("\n", 0, match.start()) + 1
        raise SystemExit(
            f"{GUIDE.relative_to(ROOT)}:{line}: canonical component guide "
            "must use Voodoo event props, not inline handlers"
        )
    if "on_click=" not in text:
        raise SystemExit("canonical component guide is missing the on_click example")
    print("documentation event-boundary contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
