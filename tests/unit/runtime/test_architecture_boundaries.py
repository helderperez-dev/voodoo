from pathlib import Path

CORE_RUNTIME = Path("src/voodoo/runtime")
VENDOR_TOKENS = ("posthog", "stripe", "resend", "supabase")


def test_runtime_core_has_no_vendor_integration_imports():
    violations = []
    for path in CORE_RUNTIME.rglob("*.py"):
        source = path.read_text(encoding="utf-8").lower()
        for vendor in VENDOR_TOKENS:
            if f"import {vendor}" in source or f"from {vendor}" in source:
                violations.append(f"{path}:{vendor}")

    assert violations == []


def test_runtime_core_contains_no_noqa_suppressions():
    violations = [
        str(path)
        for path in CORE_RUNTIME.rglob("*.py")
        if "# noqa" in path.read_text(encoding="utf-8").lower()
    ]

    assert violations == []
