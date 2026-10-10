"""Verify that every Runtime durable domain declares a native Store boundary.

This is intentionally a small source-level guardrail: it does not claim that
the migration behavior is correct (the domain tests do that), but it prevents
new durable domains from silently adding only another prefixed KV encoding.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]

# ``source`` is relative to the Framework package root.  Each domain must
# expose a canonical collection/stream marker and retain an explicit legacy
# prefix for idempotent read-through and cleanup.
DOMAINS = {
    "goals": ("src/voodoo/runtime/agency/goal_store.py", ("_GOAL_PREFIX", "_COLLECTION")),
    "identity": ("src/voodoo/runtime/identity_store.py", ("_PREFIX", "_COLLECTION")),
    "workflows": ("src/voodoo/runtime/workflow_store.py", ("_PREFIX", "_NATIVE_INDEX_COLLECTION")),
    "outbox": ("src/voodoo/runtime/transaction.py", ("_OUTBOX_PENDING_PREFIX", "_OUTBOX_PENDING_COLLECTION")),
    "membership": ("src/voodoo/runtime/distributed/membership.py", ("_MEMBERSHIP_PREFIX", "_MEMBERSHIP_COLLECTION")),
    "leases": ("src/voodoo/runtime/distributed/fabric.py", ("_LEASE_PREFIX", "_LEASE_COLLECTION")),
    "scheduler": ("src/voodoo/storage/scheduler/store.py", ("_META_PREFIX", "_META_COLLECTION")),
    "agents": ("src/voodoo/agents/registry.py", ("_AGENT_PREFIX", "_AGENT_COLLECTION", "_RUN_COLLECTION")),
    "execution": ("src/voodoo/storage/execution/store.py", ("_EXECUTION_PREFIX", "_EXECUTION_COLLECTION", "_EVENT_PREFIX")),
}


def main() -> int:
    errors: list[str] = []
    for name, (relative, markers) in DOMAINS.items():
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"{name}: missing source {relative}")
            continue
        text = path.read_text(encoding="utf-8")
        missing = [marker for marker in markers if marker not in text]
        if missing:
            errors.append(f"{name}: missing durable markers {', '.join(missing)}")
        if "create_collection" not in text and "append_stream" not in text:
            errors.append(f"{name}: no native collection/stream operation")
    if errors:
        raise SystemExit("native domain inventory failed:\n- " + "\n- ".join(errors))
    print(f"native domain inventory passed ({len(DOMAINS)} durable domains)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
