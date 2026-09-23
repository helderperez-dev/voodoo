# Architecture Instructions

> Read before touching cross-layer boundaries or introducing a new subsystem.

## North star

Voodoo is one programmable Runtime for adaptive applications and operational
systems:

```text
World → Observation → Goal → Intent → Plan
      → Capability + Policy
      → Execution → Effect → Participant
      → ACK / Observation → World
```

**AI is Compute, not authority.** **Effect is not Observation.**

## Runtime / infrastructure shape

```text
                         Application
                             |
                       Voodoo Runtime
                             |
      Identity ------ Capability + Policy ------ World/Agency
                             |
                     canonical Execution
                             |
       Data / Work / Events / Objects / Workflow / Edge
                             |
                        RuntimeStore
                             |
                  application.vstore
```

Voodoo Store is the fresh-app durable default. SQLite/PostgreSQL/Redis/S3 are
explicit adapters, never hidden fallbacks.

## Dependency/layer rules

- `primitives/`: foundational data/lifecycle concepts; no Runtime/UI/AI I/O dependencies.
- `runtime/`: canonical Execution, scheduling, agency, reconciliation, distributed ownership, Identity/Principal, workflows, policy and Store boundary.
- `runtime/scheduling/`: task semantics, durable queue orchestration, scheduler, dispatch and handoff.
- `storage/`: infrastructure contracts and adapters; mechanics, not application authority.
- `data/`: Store-first `Model` facade + explicit SQL compatibility.
- `world/`: entities, relationships, observations and operational truth.
- `edge/`: device/physical participant boundary; no second execution authority.
- `protocol/`: transport/language-neutral contracts.
- `ai/`: native agents/providers/tools as Compute participants.
- `integrations/`: vendor/interoperability boundaries such as MCP, provider SDK integrations and OpenTelemetry export.
- `observability/`: framework-owned trace, metric and inspection semantics.
- `ui/`: components/reactive state/browser events; UI state is not durable business state.
- `routing/`: HTTP/page/API dispatch.
- `mesh/`: communication/realtime transport surface; distributed authority belongs to Runtime.
- `auth/`: credential/session compatibility; Runtime Identity/Principal remains the semantic identity layer.

Lower/foundational layers must not casually import higher presentation/provider layers.
Use function-level imports where needed to avoid cycles and keep optional SDKs lazy.

## Architectural laws

1. One Runtime and one canonical Execution lifecycle.
2. `Execution` is for meaningful governed/durable/observable work, not every function call.
3. Identity, authentication and authority are distinct.
4. Capability + Policy governs effects.
5. Store owns durable mechanics; Runtime owns semantics and authority.
6. One process owns one live local Store writer.
7. Multiple Voodoo Nodes use node-local Stores; never shared-file multiwriter.
8. Scaling changes deployment topology, not app business code.
9. Distributed ownership precedes Store replication/sync.
10. Remote work re-enters canonical Execution at the destination.
11. Discovery/advertisement does not grant authority.
12. Do not claim consensus, global transactions or global exactly-once without an implemented protocol.
13. Voodoo 3.x has one semantic owner per concept; removed 2.x compatibility paths must not be recreated as facades or duplicate modules.

## Computational concepts

Before adding an abstraction, test whether it is already expressible as:

- Entity / Identity
- State
- Observation
- Goal
- Intent
- Capability
- Policy
- Execution
- Effect
- Compute
- Time
- Resource
- Constraint
- Relationship

New names should represent genuinely different semantics rather than duplicate
existing concepts.

## Store ownership

Store-backed code consumes the Runtime-owned `RuntimeStore`; it must not open
`.voodoo/application.vstore` independently.

```text
Process
  `-- RuntimeStore
        `-- application.vstore
              +-- Data
              +-- Queue
              +-- Events
              +-- Objects
              +-- Execution
              +-- Identity
              `-- Edge
```

A fresh Runtime defaults database/queue/events/objects to `voodoo`. If a
required Store capability is unavailable, fail clearly — do not fallback to
SQLite.

## Data

`Model` is the public Store-first persistence facade. `BaseModel` and `init_db`
are SQL compatibility surfaces. SQL-string RLS cannot be safely translated to
Store Collections and must fail clearly on the Store path until a policy-native
model contract exists.

## Runtime transactions

`RuntimeTransaction` supports only the atomicity actually provided locally:
Store KV/Collection mutation + durable Outbox in one Store transaction. Delivery
is at-least-once and external/node effects are outside that transaction.

## Runtime scheduling

Store Jobs are the default durable queue. Task/queue/scheduler ownership lives
under `voodoo.runtime.scheduling`. Queue ownership uses leases and retry
semantics; each attempt enters canonical Execution. The removed
`voodoo.workers` and `voodoo.queue` compatibility paths must not return.

Scheduler/Cron/Triggers are Store-backed. Store 0.2.2 cannot arbitrarily
reposition a schedule cursor; preserve the explicit failure instead of silently
changing semantics.

## Events / Objects

Current Store 0.2.x Python binding does not expose richer native Topics/Streams
or Object APIs. Store-backed compatibility implementations are valid architectural
boundaries. Do not replace them with old defaults or claim native binding support
that does not exist.

## Identity / authority

```text
Identity(user|agent|service|device|node)
        ↓
AuthenticationEvidence
        ↓
Principal
        ↓
Capability + Policy
        ↓
Execution
```

Roles/scopes/node advertisements may inform policy or compatibility APIs, but
they must not magically become Runtime Capability grants.

## Runtime Fabric

Multiple nodes retain the same application semantics:

```text
Runtime Router/Fabric
   +-- node-a -> a.vstore
   +-- node-b -> b.vstore
   `-- node-c -> c.vstore
```

Fabric concerns include membership, health, discovery, placement, ownership,
lease generations and bounded failover. Failover must respect retryability and
ambiguous external/physical effects.

## Edge

Edge reports Observations and receives Effects. It does not own an independent
DeviceExecutionEngine. Store-backed device/session/effect/replay state shares
the Runtime Store by default; SQLite device storage is explicit compatibility.

## Request/reactive boundaries

An HTTP request or UI callback does not automatically deserve a durable
Execution. Create Executions at meaningful boundaries where authorization,
effects, recovery, accounting, lineage or waiting matter. Reactive `state()` is
UI-local state, not persistent business data.

## Adding a subsystem

1. Identify its existing semantic concept(s).
2. Place it in the owning layer.
3. Check dependency direction.
4. Define a Protocol only when there is a genuine replaceable implementation boundary.
5. If durable, integrate through RuntimeStore or an explicit adapter — never an accidental second default.
6. If it causes effects, route authority through Capability + Policy + Execution.
7. Add failure/restart tests as appropriate.
8. Update public docs and coding-agent instructions.

## Do not build by shortcut

- no shared `.vstore` coordination trick;
- no implicit cloud dependency;
- no ambient autonomous authority;
- no second runtime for agents/devices/workers;
- no fake distributed consensus/exactly-once;
- no silent compatibility fallback that contradicts configured semantics;
- no new DSL when normal Python + existing primitives suffice.

## Current honest boundaries

Store replication/sync, distributed consensus, globally serializable cross-node
transactions, global exactly-once execution, production PKI/OIDC/mTLS and a
managed cloud control plane remain future work.
