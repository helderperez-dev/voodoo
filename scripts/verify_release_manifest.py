"""Verify a generated release manifest against the artifacts on disk."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _safe_artifact_path(root: Path, name: str) -> Path:
    """Resolve a manifest path without allowing directory traversal."""
    if not name or "\\" in name:
        raise ValueError("release manifest artifact path is unsafe")
    candidate = Path(name)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("release manifest artifact path is unsafe")
    root_resolved = root.resolve()
    resolved = (root / candidate).resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise ValueError("release manifest artifact path escapes dist directory")
    return resolved


def verify(dist: Path) -> None:
    manifest_path = dist / "release-manifest.json"
    payload = json.loads(manifest_path.read_text())
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("release manifest has no artifacts")
    seen: set[str] = set()
    for item in artifacts:
        if not isinstance(item, dict):
            raise ValueError("release manifest artifact must be an object")
        name = item.get("file")
        digest = item.get("sha256")
        size = item.get("bytes")
        if (
            not isinstance(name, str)
            or not name
            or name in seen
            or not isinstance(digest, str)
            or not _SHA256.fullmatch(digest)
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
        ):
            raise ValueError("release manifest contains invalid or duplicate artifact metadata")
        seen.add(name)
        path = _safe_artifact_path(dist, name)
        if not path.is_file():
            raise ValueError(f"manifest artifact is missing: {path.name}")
        if path.stat().st_size != item["bytes"]:
            raise ValueError(f"manifest byte count mismatch: {path.name}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != item["sha256"]:
            raise ValueError(f"manifest checksum mismatch: {path.name}")
    print(f"release manifest verified: {len(artifacts)} artifacts")


if __name__ == "__main__":
    verify(Path(sys.argv[1] if len(sys.argv) > 1 else "dist"))
