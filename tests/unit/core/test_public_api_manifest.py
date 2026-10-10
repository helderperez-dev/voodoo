"""Keep the documented public API manifest executable."""

from __future__ import annotations

import json
import runpy
from pathlib import Path

import voodoo

FRAMEWORK_ROOT = Path(__file__).parents[3]


def test_public_api_manifest_matches_package_root() -> None:
    manifest_path = Path(__file__).parents[3] / "docs" / "public_api_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["version"] == voodoo.__version__
    assert list(voodoo.__all__) == manifest["root_exports"]


def test_public_api_compatibility_registry_is_valid() -> None:
    namespace = runpy.run_path(str(FRAMEWORK_ROOT / "scripts" / "check_api_compatibility.py"))
    assert namespace["main"]() == 0


def test_legacy_agent_imports_are_confined_to_runtime_facades() -> None:
    namespace = runpy.run_path(str(FRAMEWORK_ROOT / "scripts" / "check_api_compatibility.py"))
    assert namespace["_validate_legacy_import_boundaries"]() == []
