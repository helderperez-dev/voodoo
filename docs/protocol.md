# Voodoo Protocol — schemas and compatibility

The `voodoo.protocol` package is the language-neutral semantic boundary for
participants that need to understand Voodoo without importing Python runtime
internals.

It is intentionally **not** a second Runtime. Protocol models describe data that
crosses a boundary; execution semantics continue to belong to the canonical
Voodoo Runtime.

## Current semantic surface

The original protocol vocabulary covers runtime/application concepts such as:

- `Identity`, `Capability`, `Constraint`, `Resource`, `TimeSpec`, `ComputeSpec`;
- `Intent`, `Effect`, `Execution`;
- `Task`, `Event`, `ObjectRef`, `Error`, `TelemetrySpan`;
- `Approval`, `AgentEntity`, `AgentRun`, `MemoryEntry`.

Sprint 27 converges the protocol with the operational runtime that landed in
Sprints 24–26. The exported schema set also includes:

- `Entity`;
- `Relationship`;
- `Observation`;
- `WorldSnapshot`;
- `Goal`, `GoalIntentRun`, `GoalRun`;
- `RemoteExecutionRequest`;
- `RemoteExecutionOutcome`.

This means a non-Python participant can represent World evidence, inspect Goal
state and exchange governed remote-execution data without reproducing Python
runtime classes.

## Quick start

```python
from voodoo.protocol import (
    Entity,
    Observation,
    RemoteExecutionRequest,
    WorldSnapshot,
    export_json_schemas,
)

schemas = export_json_schemas()
assert "WorldSnapshot" in schemas
assert "RemoteExecutionRequest" in schemas
```

Export through the CLI:

```bash
voodoo protocol export
voodoo protocol export --entity Execution
voodoo protocol export --entity Observation
voodoo protocol export --output schemas.json
voodoo protocol list
```

## Compatibility policy

`SCHEMA_VERSION` remains the per-entity compatibility version. Sprint 27 adds
new protocol entity families without changing the wire shape of the original
entities, so this convergence is **additive**, not a forced breaking version
bump.

Rules:

1. New optional fields and new entity schemas may be added compatibly.
2. Removing/renaming fields, changing field types, or making optional fields
   required is breaking and requires a schema version bump for the affected
   contract.
3. Consumers should ignore unknown optional fields but must not silently accept
   a schema version they explicitly do not support.
4. New enum values are treated as an evolution boundary; consumers must have a
   safe unknown-value strategy.
5. Nested model breakage is parent model breakage.
6. Runtime implementation classes are never the interoperability contract merely
   because they happen to serialize similarly.

## World semantics

The most important protocol distinction is:

```text
Effect != Observation
```

`Effect` describes attempted action. `Observation` describes evidence about
what actually happened and carries provenance such as source, confidence,
source/event time, trace and execution lineage.

A remote or physical participant should report evidence rather than assuming a
command changed the World successfully.

## Distributed execution semantics

`RemoteExecutionRequest` and `RemoteExecutionOutcome` are transport-neutral
semantic envelopes. HTTP, WebSocket, MQTT or another transport may carry them;
the network does not create a separate execution lifecycle.

The canonical path remains:

```text
remote identity
  → remote request
  → Intent
  → Capability + Policy
  → ExecutionEngine
  → COMPLETED / FAILED / WAITING
  → remote outcome
```

A remote request must never bypass server-side authority evaluation.

## JSON Schema export

```python
from voodoo.protocol import export_json_schemas, schema_for

all_schemas = export_json_schemas()
observation_schema = schema_for("Observation")
```

Each exported schema includes:

- JSON Schema draft metadata;
- a stable Voodoo URN;
- `x-voodoo-schema-version`.

## SDK direction

Python is the primary Runtime implementation. TypeScript, Go, Rust and embedded
SDKs should primarily consume protocol schemas and transport contracts rather
than reimplement `ExecutionEngine`, Policy, World projection or Goal semantics.

Full generated SDK families are a post-Sprint-27 productization concern. Sprint
27's responsibility is to make the semantic boundary complete enough that
those SDKs can be generated without inventing missing concepts.

## See also

- `docs/primitives.md`
- `docs/execution-model.md`
- `docs/public-api-3.md`
- `docs/sprints/SPRINT_27_CONVERGENCE_3_0_READINESS.md`
