"""Framework migrations for execution extras (artifacts + approvals).

Sprint 6 artifacts/provenance (spec §46) and Sprint 4 approvals were
originally created inline by ``SQLiteExecutionStore._migrate()`` on its own
connection. They are extracted here as numbered framework migrations so the
*migration runner* used by ``PostgresDatabase`` (and any future backend)
creates the same tables with the same schema — one source of truth for both
the SQLite store (which executes these statements on its own connection)
and the server-backed stores.
"""

from __future__ import annotations

from voodoo.storage.database.interfaces import Migration
from voodoo.storage.database.sqlite import register_framework_migration

# Versions follow the global framework namespace: … 6 events, 7 artifacts,
# 8 approvals.
EXECUTION_ARTIFACTS_MIGRATION_VERSION = 7
EXECUTION_APPROVALS_MIGRATION_VERSION = 8

EXECUTION_ARTIFACTS_MIGRATION = Migration(
    version=EXECUTION_ARTIFACTS_MIGRATION_VERSION,
    name="execution_artifacts",
    statements=(
        # Artifacts + provenance (Sprint 6, spec §46).
        """
        CREATE TABLE IF NOT EXISTS artifacts (
            id TEXT PRIMARY KEY,
            execution_id TEXT NOT NULL,
            parent_artifact_id TEXT,
            created_by TEXT,
            tool TEXT,
            model TEXT,
            checksum TEXT,
            metadata TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_artifacts_execution "
        "ON artifacts (execution_id)",
    ),
)

EXECUTION_APPROVALS_MIGRATION = Migration(
    version=EXECUTION_APPROVALS_MIGRATION_VERSION,
    name="execution_approvals",
    statements=(
        # Approvals (Sprint 4) — pending human decisions survive restarts.
        """
        CREATE TABLE IF NOT EXISTS approvals (
            id TEXT PRIMARY KEY,
            execution_id TEXT NOT NULL,
            trace_id TEXT,
            capability TEXT,
            question TEXT,
            requested_by TEXT,
            status TEXT NOT NULL,
            decided_by TEXT,
            decided_at TEXT,
            reason TEXT,
            created_at TEXT NOT NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_approvals_execution "
        "ON approvals (execution_id)",
    ),
)

register_framework_migration(EXECUTION_ARTIFACTS_MIGRATION)
register_framework_migration(EXECUTION_APPROVALS_MIGRATION)

__all__ = [
    "EXECUTION_APPROVALS_MIGRATION",
    "EXECUTION_APPROVALS_MIGRATION_VERSION",
    "EXECUTION_ARTIFACTS_MIGRATION",
    "EXECUTION_ARTIFACTS_MIGRATION_VERSION",
]
