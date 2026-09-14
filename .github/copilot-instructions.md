# Voodoo Framework — Coding Agent Instructions

> Entry point for Copilot and coding agents working in this repository.

## Quick reference

| What | Value |
|---|---|
| Language | Python >= 3.12 |
| Package manager | `uv` |
| Formatter/linter | Ruff |
| Type checker | mypy |
| Tests | pytest (`asyncio_mode = auto`) |
| Framework version | `src/voodoo/__init__.py` |
| Default durable substrate | Voodoo Store |
| Default Store path | `.voodoo/application.vstore` |

## Project identity

Voodoo is a **programmable runtime for adaptive applications and operational
systems**. Web, APIs, agents, workers, human workflows, distributed nodes and
physical devices converge on one Runtime and one canonical Execution model.

The zero-external-infrastructure default is **Voodoo Store**, not SQLite:

```text
Application
    |
    v
Voodoo Runtime
    |
    +-- Model / Data
    +-- Queue / Jobs
    +-- Scheduler / Cron / Triggers
    +-- Events / Outbox
    +-- Objects
    +-- Execution / Workflow / Goal / HITL
    +-- Identity
    +-- Edge
    |
    v
.voodoo/application.vstore
```

PostgreSQL, SQLite, Redis and S3 are explicit adapters. Never restore them as
silent defaults just to make a test pass.

## Architectural invariants

1. **One Runtime / one canonical Execution lifecycle.** Do not create competing execution engines for AI, workers, Edge or remote nodes.
2. **AI is Compute, not authority.** Capability + Policy govern effects.
3. **Identity is separate from authority.** Authentication, roles/scopes and node advertisements do not automatically grant Capability.
4. **Store-first local durability.** Fresh applications use Voodoo Store.
5. **One process owns one live local Store writer.** Do not open competing handles to the same `.vstore`.
6. **No shared-file multi-writer scaling.** Multiple Voodoo Nodes own separate local Stores.
7. **Distributed ownership before distributed storage.** Do not invent replication/sync before it is explicitly designed and tested.
8. **Scaling changes topology, not app architecture.** Application code must not need node addresses/retry plumbing merely because nodes are added.
9. **Remote work remains governed.** Routing/discovery never bypass Capability + Policy + Execution.
10. **No false guarantees.** Do not claim distributed consensus, global serializable transactions or global exactly-once execution.
11. **Effect != Observation.** A sent command is not proof that the World changed.
12. **Stable Framework contracts may use compatibility layers.** Store 0.2.x does not yet expose every richer native subsystem through Python.

## Store ownership rules

Infrastructure adapters reuse the Runtime-owned `RuntimeStore`. A subsystem must
not independently open `.voodoo/application.vstore`.

```text
Process / Runtime
       |
       v
 RuntimeStore
       |
       v
application.vstore
```

Standalone infrastructure used before `App` startup may acquire the shared
Runtime Store. `App` adopts a compatible shared handle. A conflicting *live*
writer is an error; an inert failed-startup registration may be replaced.

## Provider defaults

Effective fresh-app defaults:

```toml
[store]
provider = "voodoo"
path = ".voodoo/application.vstore"

[database]
provider = "voodoo"

[queue]
provider = "voodoo"

[events]
provider = "voodoo"

[objects]
provider = "voodoo"

[cache]
provider = "memory"
```

Cache is transient by default. Durable application infrastructure belongs in
Voodoo Store.

If the installed Store binding lacks a required capability, fail clearly and
tell the user to upgrade. **Never silently fall back to SQLite.**

## Runtime concepts

Use the existing ontology before introducing another abstraction:

```text
Entity / Identity
State
Goal
Intent
Capability
Policy
Execution
Effect
Observation
Compute
Time
Resource
Constraint
```

An `Execution` represents meaningful work worth authorizing, recovering,
observing, accounting for or waiting on. Do not create an Execution for every
helper call/render/state read.

## Data

`voodoo.Model` is Store-first. `BaseModel` / `init_db()` preserve explicit SQL
compatibility.

Legacy SQL-string `rls_policy()` is not valid Store semantics; the Store path
must fail clearly rather than silently bypassing it. Use an explicit SQL adapter
for applications that still depend on SQL-predicate RLS.

## Queue / workers

The default durable queue is `VoodooStoreQueue`, backed by Store Jobs. Leases,
heartbeat, retry and idempotency belong to the queue; application attempts enter
canonical Execution. External effects are not globally exactly-once.

## Transactions / outbox

`RuntimeTransaction` can atomically combine supported local Store KV/Collection
mutations and an `OutboxMessage`. Outbox delivery is at-least-once and is
outside the local transaction. Do not extend the atomicity claim to another
node or arbitrary external systems.

## Scheduler / Events / Objects limitations

- Store 0.2.2 cannot arbitrarily reposition an existing schedule cursor.
- Events currently use a Store-backed compatibility boundary; richer native Topics/Streams Python APIs are not exposed yet.
- Objects currently use a Store-backed compatibility boundary; richer native Object Python APIs are not exposed yet.

Preserve public contracts and document these limitations honestly.

## Identity / node fabric

Identity kinds include user, agent, service, device and node. The Runtime Fabric
supports durable membership, health, discovery, placement, ownership, leases and
bounded failover. Advertised capabilities are discovery metadata, not grants.

Each node owns its local Store:

```text
Runtime Fabric
  +-- node-a -> a.vstore
  +-- node-b -> b.vstore
  `-- node-c -> c.vstore
```

Retry/failover must respect work semantics. Do not automatically reissue
ambiguous physical/external effects when work is non-retryable.

## Edge

Edge device/credential/session/effect/replay state is Store-backed by default
and shares the Runtime Store. `SQLiteDeviceStore` is an explicit adapter only.

## Dependencies and imports

- Keep provider SDKs lazy and optional (`ai`, `postgres`, `redis`, `s3`, `otel`, `edge`, `sqlite`).
- Voodoo Store is a base dependency because it is the default durable substrate.
- Primitives must not depend on higher Runtime/UI/AI layers.
- Preserve compatibility import paths during the 2.x line.
- Public concepts should live in the namespace that owns them; the package root is a compatibility facade.

## Code style

- `from __future__ import annotations` in new Python modules.
- Type hints on public/new code.
- Prefer `str | None`, `list[T]`, `dict[K, V]`.
- Double quotes; Ruff formatting; 88-character target.
- Broad exception catches require a reason and `# noqa: BLE001` when appropriate.
- Raise structured Voodoo errors instead of silently swallowing configuration failures.
- Use Conventional Commits (`feat(scope): ...`, `fix(scope): ...`, etc.).

## Testing rules

- Fresh mutable instances per test.
- Contract tests for adapters remain authoritative.
- Python 3.12 and 3.13 must pass.
- Ruff, the declared mypy boundary and CodeQL must pass.
- Store lifecycle/restart behavior must be tested with close/reopen when durability is claimed.
- Fresh-user DX changes must execute the generated scaffold, not merely assert template strings.
- Never weaken architectural defaults to satisfy legacy tests; update tests that encode superseded defaults.

## Documentation sync

When behavior changes, update the public docs and these agent instructions in the
same PR. In particular verify:

- `README.md`
- `ARCHITECTURE.md`
- relevant `docs/*.md`
- `.github/instructions/*.md`
- examples/scaffolds
- Sprint/roadmap docs when scope changes.

## Development / PR discipline

1. Work on the intended feature/sprint branch.
2. Implement the smallest coherent semantic slice.
3. Add/update tests including failure paths and durability if applicable.
4. Run Ruff, mypy boundary and full pytest matrix.
5. Update documentation.
6. Keep the PR draft until the work is actually review-ready.
7. Do **not** merge or publish a release merely because a sprint is marked DONE; merge/release are separate explicit decisions.

## Current honest boundaries

Do not claim that Voodoo already provides:

- Store replication/sync between nodes;
- shared multi-writer `.vstore` files;
- distributed consensus;
- globally serializable cross-node transactions;
- global exactly-once execution;
- production PKI/OIDC/mTLS identity infrastructure;
- a managed Voodoo Cloud/fleet control plane.

When in doubt, prefer truthful explicit limitations over an implicit fallback or
an architectural shortcut.
