"""Ensure every production risk surface has a tracked executable test slice."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
TESTS = ROOT / "tests"

SURFACES: dict[str, tuple[str, ...]] = {
    "auth/security": (
        "unit/auth/test_auth.py",
        "unit/auth/test_security.py",
        "unit/auth/test_websocket_security.py",
    ),
    "events": ("unit/core/test_events.py", "integration/test_mesh_event_bus.py"),
    "state": (
        "unit/ui/test_state.py",
        "unit/runtime/test_state_dependency_integration.py",
    ),
    "Store adapters": (
        "contracts/test_execution_store.py",
        "contracts/test_objectstore.py",
        "unit/storage/test_store_model_backend.py",
        "integration/test_runtime_store_provider.py",
    ),
    "scheduling": (
        "unit/runtime/test_work_scheduler.py",
        "unit/storage/test_scheduler.py",
    ),
    "providers": (
        "unit/ai/test_providers.py",
        "contracts/test_model_provider.py",
    ),
}

TEST_FUNCTION = re.compile(
    r"^\s*(?:async\s+)?def\s+test_[A-Za-z0-9_]+\s*\(", re.MULTILINE
)


def main() -> int:
    failures: list[str] = []
    totals: dict[str, int] = {}
    for surface, relative_paths in SURFACES.items():
        count = 0
        for relative in relative_paths:
            path = TESTS / relative
            if not path.is_file():
                failures.append(f"{surface}: missing {relative}")
                continue
            tests = len(TEST_FUNCTION.findall(path.read_text(encoding="utf-8")))
            if tests == 0:
                failures.append(f"{surface}: {relative} has no test functions")
            count += tests
        totals[surface] = count
    if failures:
        raise SystemExit("risk-path coverage contract failed: " + "; ".join(failures))
    summary = ", ".join(f"{name}={count}" for name, count in totals.items())
    print(f"risk-path coverage contract passed ({summary})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
