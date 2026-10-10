"""Validate the public compatibility/deprecation registry."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
REGISTRY = ROOT / "docs" / "public_api_compatibility.json"
SOURCE = ROOT / "src" / "voodoo"


def _major(version: str) -> int:
    match = re.fullmatch(r"(\d+)\.\d+\.\d+", version)
    if match is None:
        raise ValueError(f"invalid semantic version: {version}")
    return int(match.group(1))


def _validate_entry(entry: dict[str, object], current_major: int, seen: set[str]) -> list[str]:
    errors: list[str] = []
    surface = entry.get("surface")
    status = entry.get("status")
    if not isinstance(surface, str) or not surface or surface in seen:
        errors.append(f"missing or duplicate surface: {surface!r}")
    if isinstance(surface, str):
        seen.add(surface)
    if status not in {"deprecated", "compatibility", "stable"}:
        errors.append(f"{surface}: invalid status {status!r}")
    if not entry.get("replacement") or not entry.get("migration"):
        errors.append(f"{surface}: replacement and migration are required")
    if status == "deprecated":
        remove_after = entry.get("remove_after")
        if not isinstance(remove_after, str):
            errors.append(f"{surface}: deprecated entries need remove_after")
        else:
            try:
                if _major(remove_after) <= current_major:
                    errors.append(f"{surface}: removal must be after current major")
            except ValueError as exc:
                errors.append(str(exc))
    elif not entry.get("review_after"):
        errors.append(f"{surface}: compatibility entries need review_after")
    return errors


def _validate_legacy_import_boundaries() -> list[str]:
    """Keep retained legacy implementations behind their public facades."""
    allowed = {
        SOURCE / "ai" / "agent.py",
        SOURCE / "ai" / "agent_runtime_truth.py",
    }
    errors: list[str] = []
    for path in SOURCE.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            module = node.module if isinstance(node, ast.ImportFrom) else None
            if module == "voodoo.ai.agent_legacy" and path not in allowed:
                errors.append(
                    f"{path.relative_to(ROOT)} imports retained legacy agent directly"
                )
    return errors


def main() -> int:
    payload = json.loads(REGISTRY.read_text())
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("unsupported compatibility registry schema")
    current_major = int(payload.get("current_major", 0))
    entries = payload.get("entries", [])
    if not entries:
        errors.append("compatibility registry has no entries")
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("registry entries must be objects")
            continue
        errors.extend(_validate_entry(entry, current_major, seen))
    errors.extend(_validate_legacy_import_boundaries())
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"API compatibility registry passed ({len(entries)} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
