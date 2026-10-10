"""Validate that every declared durable domain stays in the architecture inventory."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]
INVENTORY = ROOT / "docs/architecture/encoding-inventory.md"

# Keep this list intentionally explicit. Adding a durable domain must update the
# inventory and its ownership/migration rule in the same change.
REQUIRED_DOMAINS: dict[str, tuple[str, ...]] = {
    "Application `Model` records": ("voodoo.data.store_backend", "schema_version=1"),
    "Runtime identity and registry records": ("voodoo.runtime", "explicit timestamps"),
    "Edge device, replay, and response records": (
        "voodoo.edge.store_voodoo",
        "legacy prefixed KV keys remain read-through",
    ),
    "Runtime workflow/execution records": ("voodoo.runtime", "codec version"),
    "Durable events/outbox": ("voodoo.storage.events", "replay"),
    "Scheduler and task payloads": ("voodoo.storage.scheduler", "idempotency"),
    "Execution artifacts and observations": ("execution/observability", "redact"),
    "Object bytes": ("object storage owner", "metadata and lifecycle"),
    "Session/UI state": ("Ephemeral by default", "browser patch"),
    "External compatibility adapters": ("explicit adapter", "hidden fallback"),
}

REQUIRED_INVARIANTS = (
    "Every durable native Store collection declares a schema version and codec.",
    "Encodings are deterministic and bounded; arbitrary Python pickle is not a",
    "Runtime owns record meaning and migration policy; Store owns checksums,",
    "A migration adds a fixture and a forward/backward compatibility test",
)


def main() -> int:
    if not INVENTORY.is_file():
        raise SystemExit(f"missing durable encoding inventory: {INVENTORY}")
    text = INVENTORY.read_text(encoding="utf-8")
    missing: list[str] = []
    for domain, evidence in REQUIRED_DOMAINS.items():
        if domain not in text:
            missing.append(f"domain: {domain}")
        for marker in evidence:
            if marker not in text:
                missing.append(f"{domain}: {marker}")
    for invariant in REQUIRED_INVARIANTS:
        if invariant not in text:
            missing.append(f"invariant: {invariant}")
    if missing:
        raise SystemExit("encoding inventory contract failed:\n- " + "\n- ".join(missing))
    print(f"encoding inventory contract passed ({len(REQUIRED_DOMAINS)} domains)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
