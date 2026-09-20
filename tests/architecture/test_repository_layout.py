"""Repository architecture invariants.

These tests keep physical repository growth aligned with the semantic ownership
documented in docs/architecture/repository.md.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).parents[2] / "src" / "voodoo"

# Existing package-root modules are compatibility/application facades. New
# root modules require an explicit public-API decision.
ROOT_MODULES = {
    "__init__.py",
    "agent.py",
    "api.py",
    "components.py",
    "config.py",
    "i18n.py",
    "queue.py",
    "schedule.py",
    "seo.py",
    "status.py",
    "theme.py",
}

SEMANTIC_CORE = ("core", "runtime", "primitives", "protocol", "world")

VENDOR_ROOTS = {
    "anthropic",
    "boto3",
    "botocore",
    "google.generativeai",
    "openai",
    "posthog",
    "redis",
    "resend",
    "stripe",
    "supabase",
}


def _python_files(root: Path):
    return root.rglob("*.py")


def test_package_root_is_curated() -> None:
    actual = {path.name for path in SRC.glob("*.py")}
    assert actual <= ROOT_MODULES


def test_source_has_no_noqa_suppressions() -> None:
    """Architecture debt must not be hidden behind lint suppressions."""
    offenders = []
    for path in _python_files(SRC):
        if "# noqa" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(SRC)))
    assert offenders == []


def test_tests_are_owned_by_a_test_domain() -> None:
    """Tests must live under unit/integration/e2e/contracts/architecture."""
    tests = Path(__file__).parents[1]
    offenders = sorted(path.name for path in tests.glob("test_*.py"))
    assert offenders == []


def test_semantic_core_has_no_vendor_imports() -> None:
    offenders: list[str] = []
    for domain in SEMANTIC_CORE:
        for path in _python_files(SRC / domain):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    if any(
                        name == vendor or name.startswith(f"{vendor}.")
                        for vendor in VENDOR_ROOTS
                    ):
                        offenders.append(f"{path.relative_to(SRC)} imports {name}")
    assert offenders == []
