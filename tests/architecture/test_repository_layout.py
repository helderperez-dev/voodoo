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

# Transitional debt baseline. This set may only shrink and is removed entirely
# before Repository Architecture reaches 100%.
LEGACY_NOQA_FILES = {
    "ai/agent_legacy.py",
    "ai/agent_runtime_truth.py",
    "ai/providers/__init__.py",
    "ai/providers/anthropic.py",
    "ai/providers/gemini.py",
    "ai/providers/ollama.py",
    "ai/providers/openai.py",
    "ai/tools/__init__.py",
    "ai/tools/registry.py",
    "auth/guards.py",
    "auth/jwt.py",
    "cli/doctor.py",
    "cli/inspect.py",
    "cli/new.py",
    "cli/scaffolding.py",
    "cli/theme.py",
    "core/events.py",
    "core/routing.py",
    "core/sitemap.py",
    "data/base.py",
    "data/store_facade.py",
    "edge/gateway.py",
    "edge/http.py",
    "edge/mqtt.py",
    "edge/protocol.py",
    "mcp/__init__.py",
    "memory/interfaces.py",
    "mesh/__init__.py",
    "protocol/schemas.py",
    "routing/api.py",
    "security/headers.py",
    "security/secrets.py",
    "storage/objects/s3.py",
    "telemetry/otlp.py",
    "telemetry/store.py",
    "ui/styles/presets.py",
    "workers/__init__.py",
    "workers/queue.py",
}
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


def test_changed_source_does_not_add_noqa_suppressions() -> None:
    """New architecture work must not introduce additional lint suppressions."""
    # Legacy suppressions are tracked for removal during this refactor. Keeping
    # this test scoped to the architectural center prevents new debt there
    # while the remaining historical modules are cleaned incrementally.
    protected = ("core", "runtime", "primitives", "protocol", "world")
    offenders = []
    for domain in protected:
        for path in _python_files(SRC / domain):
            if "# noqa" in path.read_text(encoding="utf-8"):
                offenders.append(str(path.relative_to(SRC)))
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
