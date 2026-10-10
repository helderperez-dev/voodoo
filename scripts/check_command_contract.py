"""Validate canonical onboarding commands in current Framework documentation."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]
CANONICAL_DOCS = (
    ROOT / "docs/installation.md",
    ROOT / "docs/hello_world.md",
    ROOT / "docs/runtime-consolidation.md",
)


def main() -> int:
    errors: list[str] = []
    for path in CANONICAL_DOCS:
        for line_number, line in enumerate(path.read_text().splitlines(), 1):
            if "voodoo create" not in line:
                continue
            lowered = line.lower()
            if not any(
                marker in lowered
                for marker in ("deprecated", "compatibility alias", "deprecation")
            ):
                errors.append(f"{path}:{line_number}: use canonical 'voodoo new'")
    if errors:
        print("command contract failed:")
        print("\n".join(errors))
        return 1
    print("command contract passed (voodoo new is canonical)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
