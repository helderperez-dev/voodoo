"""Validate the Profile 1 health/status contract and its regression slices."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).parents[1]
STATUS = ROOT / "src/voodoo/status.py"
TESTS = ROOT / "tests/unit/test_status.py"
HTTP_TESTS = ROOT / "tests/integration/test_http_runtime.py"
REQUIRED_REMEDIATION_KEYS = {"database", "queue", "storage", "agent", "store"}
REQUIRED_TESTS = {
    "test_status_distinguishes_degraded_services",
    "test_status_returns_service_unavailable_for_down_service",
    "test_store_health_projects_capacity_and_redacts_details",
    "test_store_health_details_are_bounded_json_safe_and_identifier_free",
    "test_database_health_does_not_hide_unexpected_implementation_failures",
    "test_store_health_does_not_hide_unexpected_implementation_failures",
}
REQUIRED_HTTP_TESTS = {
    "test_liveness_and_readiness_probes_are_explicit",
    "test_readiness_fails_closed_during_lifecycle_transitions",
    "test_readiness_reports_migration_required_mode",
    "test_readiness_fails_closed_when_store_health_probe_raises",
    "test_readiness_does_not_hide_store_invariant_failures",
}


def _symbols(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


def _validate_policy(source: str) -> None:
    if (
        '"attention"' not in source
        or '"policy": _STATUS_POLICY[overall]' not in source
        or "status_code=503 if has_down else 200" not in source
    ):
        raise SystemExit(
            "status contract must expose remediation policy and fail closed on Down"
        )
    if '"Degraded": {"http_status": 200, "traffic": "serve_with_attention"}' not in source:
        raise SystemExit("status contract must keep degraded traffic serving with attention")
    if '"Down": {"http_status": 503, "traffic": "fail_closed"}' not in source:
        raise SystemExit("status contract must keep Down traffic fail-closed")


def main() -> int:
    source = STATUS.read_text(encoding="utf-8")
    tests = _symbols(TESTS)
    http_tests = _symbols(HTTP_TESTS)
    missing = sorted(REQUIRED_TESTS - tests)
    if missing:
        raise SystemExit("status contract missing regression tests: " + ", ".join(missing))
    missing_http = sorted(REQUIRED_HTTP_TESTS - http_tests)
    if missing_http:
        raise SystemExit(
            "status contract missing readiness regression tests: "
            + ", ".join(missing_http)
        )
    _validate_policy(source)
    keys = set()
    in_remediation = False
    for line in source.splitlines():
        if line.startswith("_REMEDIATION:"):
            in_remediation = True
            continue
        if in_remediation and line.startswith("}"):
            break
        if in_remediation and line.startswith('    "'):
            keys.add(line.split('"', 2)[1])
    missing_keys = sorted(REQUIRED_REMEDIATION_KEYS - keys)
    if missing_keys:
        raise SystemExit(
            "status contract missing remediation guidance: " + ", ".join(missing_keys)
        )
    print(
        "status contract passed "
        f"({len(REQUIRED_REMEDIATION_KEYS)} remediation paths, "
        f"{len(REQUIRED_TESTS) + len(REQUIRED_HTTP_TESTS)} tests)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
