"""Smoke-check one optional dependency family in isolation."""

from __future__ import annotations

import importlib
import os
import sys

EXTRA_MODULES = {
    "ai": ("openai", "anthropic", "google.generativeai", "ollama"),
    "browser": ("playwright.sync_api",),
    "edge": ("paho.mqtt.client",),
    "otel": ("opentelemetry", "opentelemetry.sdk.trace"),
    "postgres": ("psycopg",),
    "redis": ("redis",),
    "s3": ("boto3", "botocore"),
}


def main() -> int:
    extra = os.environ.get("VOODOO_OPTIONAL_EXTRA")
    if extra not in EXTRA_MODULES:
        print(
            f"VOODOO_OPTIONAL_EXTRA must be one of {sorted(EXTRA_MODULES)}",
            file=sys.stderr,
        )
        return 2
    missing: list[str] = []
    for module in EXTRA_MODULES[extra]:
        try:
            importlib.import_module(module)
        except Exception as error:  # provider import diagnostics must be explicit
            missing.append(f"{module}: {error}")
    if missing:
        print(f"optional extra {extra!r} failed:", file=sys.stderr)
        print("\n".join(missing), file=sys.stderr)
        return 1
    print(f"optional extra passed: {extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
