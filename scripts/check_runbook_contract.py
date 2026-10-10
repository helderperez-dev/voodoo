"""Validate that the Profile 1 operator runbook stays executable and safe."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]
RUNBOOK = ROOT / "docs/PRODUCTION_PROFILE_1_RUNBOOK.md"

REQUIRED_MARKERS = (
    "## Before deploy",
    "## Backup and restore drill",
    "## Shutdown and incident response",
    "## Diagnosis and maintenance",
    "## Rollback decision",
    "VOODOO_ENV=production",
    "GET /healthz",
    "GET /readyz",
    "attention",
    "voodoo-store inspect",
    "voodoo-store verify",
    "compact-copy",
    "Store.restore_copy",
    "scripts/dr_game_day.py",
    "legacy-0.2.2.vstore",
    '"status": "passed"',
    "fresh path",
    "never compact in place",
)


def main() -> int:
    text = RUNBOOK.read_text(encoding="utf-8")
    haystack = text.lower()
    missing = [marker for marker in REQUIRED_MARKERS if marker.lower() not in haystack]
    if missing:
        raise SystemExit("runbook contract missing: " + ", ".join(missing))
    if "delete the source" not in haystack or "preserve the original" not in haystack:
        raise SystemExit("runbook must preserve source files before destructive operations")
    print(f"runbook contract passed ({len(REQUIRED_MARKERS)} markers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
