# Protocol Schemas & Versioning

> **Sprint 21** — Canonical entity schemas as the stable semantic boundary for
> cross-language interop.

---

## Overview

The `voodoo.protocol` package defines **18 canonical Pydantic models** that
represent every entity in the Voodoo runtime. These schemas are the **stable
semantic boundary** — external consumers (TypeScript, Go, Rust SDKs) can
serialize, deserialize, and validate these models without depending on
Python internals.

Every entity carries a `schema_version` field (integer, ≥ 1) so consumers
can evolve independently and reject unknown major versions.

---

## Entities

| Entity | Description |
|---|---|
| `Identity` | Stable identity for any runtime entity |
| `Capability` | A granted capability with scope and constraints |
| `Constraint` | A constraint on execution (time, cost, policy) |
| `Resource` | Resource accounting (cost, latency, tokens) |
| `TimeSpec` | Time-related constraints (deadline, retries) |
| `ComputeSpec` | How a computation should be performed |
| `Intent` | What an entity wants to accomplish |
| `Effect` | A side-effect produced by an execution |
| `Execution` | A durable execution — the central runtime entity |
| `Task` | A queued work item (worker task) |
| `Event` | A mesh event envelope |
| `ObjectRef` | A reference to a stored object |
| `Error` | A structured error |
| `TelemetrySpan` | An OTel-compatible telemetry span |
| `Approval` | A human-in-the-loop approval request |
| `AgentEntity` | A registered agent entity |
| `AgentRun` | A record of an agent run |
| `MemoryEntry` | A memory entry (layered memory system) |

---

## Quick Start

```python
from voodoo.protocol import Execution, Intent, SCHEMA_VERSION

# Create an execution
intent = Intent(id="intent-1", name="summarize", params={"text": "hello"})
execution = Execution(id="exec-1", trace_id="trace-1", intent=intent)

# Serialize to JSON
data = execution.model_dump(mode="json")

# Round-trip
restored = Execution.model_validate(data)

# Export JSON Schema
from voodoo.protocol import export_json_schemas

schemas = export_json_schemas()
```

---

## JSON Schema Export

Export JSON Schema definitions for all protocol entities:

```bash
# All entities to stdout
voodoo protocol export

# Single entity
voodoo protocol export --entity Execution

# Write to file
voodoo protocol export --output schemas.json

# List entity names
voodoo protocol list
```

Programmatic export:

```python
from voodoo.protocol import export_json_schemas, export_json_schemas_json, schema_for

# Dict of all schemas
schemas = export_json_schemas()

# JSON string
json_str = export_json_schemas_json(indent=2)

# Single entity schema
exec_schema = schema_for("Execution")
```

---

## Enums

| Enum | Values |
|---|---|
| `ExecutionStatus` | `created`, `planned`, `authorized`, `running`, `waiting`, `completed`, `failed`, `cancelled`, `timed_out` |
| `IntentStatus` | `created`, `queued`, `evaluating`, `executing`, `paused`, `completed`, `rejected`, `expired`, `cancelled` |
| `EffectStatus` | `pending`, `executing`, `succeeded`, `failed`, `rolled_back` |
| `TaskStatus` | `pending`, `running`, `retrying`, `completed`, `failed` |
| `ApprovalStatus` | `pending`, `approved`, `denied` |
| `ComputeKind` | `deterministic`, `probabilistic`, `reasoning`, `inference`, `search`, `optimization`, `simulation`, `symbolic`, `human` |

---

## Compatibility Policy

### Rules

1. **Additive within a major version.** New optional fields can be added
   without breaking consumers. Consumers must ignore unknown fields.

2. **Breaking changes require a major version bump.** Removing or renaming
   fields, changing field types, or making optional fields required are
   all breaking changes.

3. **`schema_version` is an integer.** Consumers should reject data with
   an unknown major version (e.g., if `schema_version // 1000` doesn't
   match the expected major).

4. **Enums are extensible.** New enum values can be added within a major
   version. Consumers must handle unknown values gracefully.

5. **Nested models follow the same rules.** A breaking change in a nested
   model (e.g., `Intent` inside `Execution`) is a breaking change in the
   parent.

### Version Semantics

```
schema_version = 1    →  Initial release (Sprint 21)
schema_version = 2    →  First breaking change
schema_version = 100  →  Additive change within major version 1
```

Consumers should check:

```python
if data["schema_version"] // 1000 != expected_major:
    raise IncompatibleSchemaError(data["schema_version"])
```

### Migration Path

When a breaking change is introduced:

1. Bump `SCHEMA_VERSION` in `voodoo/protocol/schemas.py`.
2. Update all entity models as needed.
3. Add migration logic in `voodoo/protocol/migration.py` (if needed).
4. Update this document.
5. Bump the Voodoo minor version.

---

## Design Principles

- **JSON-friendly** — All fields use JSON primitives or nested protocol
  models. No Python-specific types.
- **Flat** — No circular references. Nested models are shallow.
- **Explicit** — Every field has a type annotation and description.
- **Inspectable** — `model_dump()` and `model_json_schema()` work on
  every entity.
- **Cross-language** — Schemas can be exported to TypeScript, Go, Rust,
  or any language with JSON Schema support.

---

## File Structure

```
src/voodoo/protocol/
├── __init__.py      # Re-exports all entities and functions
├── schemas.py       # 18 Pydantic models, 6 enums, SCHEMA_VERSION
└── export.py        # JSON Schema export functions
```

---

## See Also

- [Primitives](primitives.md) — The 8 architectural primitives
- [Execution Model](execution-model.md) — How executions work
- [Agents](agents.md) — Agent entities and runs
- [Telemetry](telemetry.md) — Telemetry spans and tracing
