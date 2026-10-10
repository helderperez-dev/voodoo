"""Validate the Runtime durable-record migration fixture corpus.

The corpus is intentionally explicit. A new durable record must add a source
codec and legacy/current/future fixtures in the same change; passing an
inventory-only check is not enough to claim migration safety.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
CORPUS = ROOT / "docs/architecture/migration-corpus.json"


def main() -> int:
    if not CORPUS.is_file():
        raise SystemExit(f"missing migration corpus: {CORPUS}")
    payload = json.loads(CORPUS.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise SystemExit("migration corpus must use schema_version 1")
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        raise SystemExit("migration corpus must declare records")

    errors: list[str] = []
    names: set[str] = set()
    for record in records:
        name = record.get("name")
        source_name = record.get("source")
        fixture_name = record.get("fixture")
        version_marker = record.get("version")
        if not all(isinstance(value, str) and value for value in (name, source_name, fixture_name, version_marker)):
            errors.append(f"invalid corpus entry: {record!r}")
            continue
        if name in names:
            errors.append(f"duplicate corpus record: {name}")
        names.add(name)
        source = ROOT / source_name
        fixture = ROOT / fixture_name
        if not source.is_file():
            errors.append(f"{name}: missing source {source_name}")
            continue
        if not fixture.is_file():
            errors.append(f"{name}: missing fixture test {fixture_name}")
            continue
        source_text = source.read_text(encoding="utf-8")
        fixture_text = fixture.read_text(encoding="utf-8").lower()
        if version_marker not in source_text:
            errors.append(f"{name}: source lacks version marker {version_marker}")
        for marker in ("legacy", "future"):
            if marker not in fixture_text:
                errors.append(f"{name}: fixture lacks {marker} coverage")

    if errors:
        raise SystemExit("migration corpus contract failed:\n- " + "\n- ".join(errors))
    print(f"migration corpus contract passed ({len(records)} records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
