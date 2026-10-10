"""Validate the reviewed visual-regression coverage contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Scripts execute with their own directory first on ``sys.path``; expose the
# repository root so the dependency-free browser signature helper is reusable.
ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
from tests.browser.visual_signature import signature

REQUIRED_STATES = {"default", "focus", "overlay", "empty-error", "long-content"}
REQUIRED_DENSITIES = {"compact", "comfortable", "spacious"}


def _validate_cases(manifest: dict[str, object], viewports: dict[str, object]) -> int:
    ids: set[str] = set()
    states: set[str] = set()
    densities: set[str] = set()
    for case in manifest.get("cases", []):
        case_id = case.get("id")
        if not case_id or case_id in ids:
            raise SystemExit(f"duplicate or missing visual case id: {case_id}")
        ids.add(case_id)
        if case.get("viewport") not in viewports:
            raise SystemExit(f"unknown viewport in visual case: {case_id}")
        if case.get("theme") not in {"light", "dark"}:
            raise SystemExit(f"unknown theme in visual case: {case_id}")
        states.add(case.get("state", ""))
        density = case.get("density")
        if density not in REQUIRED_DENSITIES:
            raise SystemExit(f"invalid or missing visual density: {case_id}")
        densities.add(density)
    missing = REQUIRED_STATES - states
    if missing:
        raise SystemExit(f"visual contract misses states: {sorted(missing)}")
    if len(ids) < 7:
        raise SystemExit("visual contract needs at least seven reviewed cases")
    missing_densities = REQUIRED_DENSITIES - densities
    if missing_densities:
        raise SystemExit(f"visual contract misses densities: {sorted(missing_densities)}")
    return len(ids)


def main() -> int:
    manifest = json.loads((ROOT / "tests/browser/visual_contract.json").read_text())
    comparison = manifest.get("comparison", {})
    if not comparison.get("review_required_on_baseline_change"):
        raise SystemExit("visual baselines must require review on change")
    for key in ("max_pixel_diff_ratio", "max_shifted_pixel_ratio"):
        value = comparison.get(key)
        if not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise SystemExit(f"invalid visual threshold: {key}")
    viewports = manifest.get("viewports", {})
    if set(viewports) != {"desktop", "mobile"}:
        raise SystemExit("visual contract must define desktop and mobile viewports")
    count = _validate_cases(manifest, viewports)
    baseline_dir = ROOT / "tests/browser/visual_baselines"
    baseline_path = ROOT / "tests/browser/visual_baselines.json"
    if not baseline_dir.is_dir() or not baseline_path.is_file():
        raise SystemExit("visual contract requires committed PNG and signature baselines")
    signatures = json.loads(baseline_path.read_text())
    missing: list[str] = []
    mismatched: list[str] = []
    for case in manifest["cases"]:
        case_id = case["id"]
        image_path = baseline_dir / f"{case_id}.png"
        if not image_path.is_file():
            missing.append(case_id)
            continue
        expected = signatures.get(case_id)
        if expected is None:
            mismatched.append(f"{case_id}: missing signature")
            continue
        actual = signature(image_path.read_bytes())
        if actual != expected:
            mismatched.append(f"{case_id}: PNG/signature mismatch")
    if missing:
        raise SystemExit(f"visual contract missing PNG baselines: {', '.join(missing)}")
    if mismatched:
        raise SystemExit("visual baseline contract failed: " + "; ".join(mismatched))
    print(
        f"visual contract passed ({count} cases, thresholds reviewed, "
        "committed PNG baselines verified)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
