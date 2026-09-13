# Sprint 26 — Trusted Distributed Execution Fabric

> Status: PLANNING
> Theme: Remote work must cross the same governed Runtime boundary as local work.
> Purpose: Turn Mesh from a useful event/RPC transport into a trusted distributed execution fabric without creating a second runtime.

## Product thesis

Voodoo already has the pieces required for governed local agency:

```text
Entity / World
  ↓
Goal / Intent
  ↓
Capability + Policy
  ↓
ExecutionEngine
  ↓
Effect / Result
  ↓
Observation / World
```

The distributed boundary must preserve that model.

A remote participant must not gain a privileged path simply because work arrived
over WebSocket, HTTP, MQTT or another transport. Remote work must become a
normal Voodoo `Intent`, evaluated with the same identity, capability, contextual
policy, approval, execution, telemetry and failure semantics as local work.

The target path is:

```text
Remote participant
  ↓
Authenticated identity / participant context
  ↓
Remote request envelope
  ↓
Intent
  ↓
Capability + contextual Policy
  ↓
ExecutionEngine
  ↓
Effect / Result / WAITING / Failure
  ↓
Correlated remote response + telemetry
```

This sprint is not a new RPC framework. It is the architectural seam that lets
Voodoo execute governed work across process and machine boundaries.

## Baseline found in code

The current Mesh implementation already has several useful foundations:

- local Mesh event handlers execute through the existing `ExecutionEngine`;
- nested local handlers preserve parent Execution context when one exists;
- remote event envelopes already carry a stable message `id`, timestamp,
  `source`, and `correlation_id`;
- Mesh is JSON-RPC-shaped and transport-facing behavior is already separated
  from local handler registration;
- exposed functions are explicitly registered rather than ambiently callable;
- remote events are converted into local handler execution rather than directly
  mutating subsystem state.

The critical gap is remote `call` handling. Today, when a connected node sends a
JSON-RPC `call`, Mesh resolves an entry from `exposed_functions` and invokes the
Python callable directly. That path does **not** currently establish a governed
remote actor, create an `Intent`, enter `ExecutionEngine`, enforce a capability,
consult contextual Policy, preserve canonical Execution lineage, provide replay
protection, or preserve WAITING/HITL as a first-class remote outcome.

The current event envelope also documents auth/signing/replay protection as
future concerns rather than implemented guarantees.

Sprint 26 closes that gap incrementally.

## Non-negotiable architectural laws

1. **One Runtime.** Distributed execution never introduces a second
   `ExecutionEngine`, remote task engine or alternate lifecycle.
2. **Identity before authority.** Governed remote execution always has an actor
   identity or an explicitly anonymous/untrusted identity class.
3. **Capability before compute.** Transport connectivity is not authority.
4. **Policy sees the same World.** Remote operations use the same contextual
   policy path and target-entity semantics as local operations.
5. **Execution is canonical truth.** Remote request/result records are protocol
   projections of the canonical Execution lifecycle, not a second source of
   truth.
6. **WAITING is not success.** Durable HITL and other waiting states cross the
   network as waiting states.
7. **Transport is not semantics.** WebSocket/HTTP/MQTT may carry messages, but
   actor, intent, capability, lineage, result and failure semantics live above
   transport adapters.
8. **Replay is explicit.** Stable request identities and idempotency rules exist
   before the system can claim safe distributed side effects.
9. **Lineage survives the network.** Request ID, correlation/trace identity,
   actor, target entity, parent Execution and resulting Execution remain
   inspectable.
10. **Local-first remains complete.** The full contract can be tested with two
    local Runtime/Mesh nodes and no external infrastructure.

## Out of scope for Sprint 26

The following are intentionally deferred:

- a production PKI or certificate authority;
- a specific cloud identity provider;
- distributed consensus or leader election;
- exactly-once network delivery claims;
- fleet scheduling or multi-device mission planning;
- physical ESP32 firmware;
- Edge semantic event → World Model ingestion;
- a new message broker;
- multi-language SDK generation beyond any protocol schema needed by this
  sprint;
- Voodoo Studio, Store, Identity product UIs or cloud control-plane
  productization.

Sprint 26 creates seams for these systems without pretending to implement them.

---

# 26.1 — Canonical remote request contract

## Goal

Replace ad-hoc `call` parameters with a stable semantic request model that can
be validated before execution.

## Proposed model

A request must have, at minimum:

```text
request_id
protocol/schema version
actor / participant identity
operation / exposed capability name
arguments
correlation_id / trace lineage
optional parent_execution_id
optional target_entity_id
metadata
```

The model should be transport-independent and serializable without requiring a
provider SDK.

## Requirements

- stable request identity supplied by the caller or generated at the boundary;
- explicit actor identity separate from node/network address;
- operation name resolves only against explicitly exposed operations;
- caller correlation/trace identity may be preserved but never trusted as
  authority;
- target entity is semantic context for Policy, not arbitrary transport data;
- malformed requests fail before compute begins;
- legacy JSON-RPC `{name, arguments}` may remain temporarily compatible, but it
  must be normalized into the canonical request contract before execution;
- protocol errors and runtime failures are distinguishable.

## Acceptance

Given a valid remote request, Voodoo can construct a deterministic normalized
request object independent of WebSocket transport.

Given malformed or unsupported input, no application callable executes.

---

# 26.2 — Governed Mesh ingress

## Goal

Make every governed remote call enter the existing `ExecutionEngine`.

## Target execution path

```text
JSON-RPC / transport message
  ↓
parse + normalize RemoteExecutionRequest
  ↓
resolve exposed operation metadata
  ↓
construct Intent
  ↓
ExecutionEngine.execute(... actor=<remote actor> ...)
  ↓
capability / policy / approval / compute
  ↓
Execution status + result projection
  ↓
remote response
```

## Exposed operation metadata

`mesh.expose(...)` should evolve from a raw callable registry into an explicit
operation registration seam. Registration should be able to declare semantic
metadata such as:

- operation name;
- required capability;
- optional intent name override;
- optional target resolution hint;
- documentation/description.

Compatibility matters: existing `@mesh.expose()` usage should continue to work,
but an undeclared capability must not silently become proof of authority. The
compatibility path should be explicit and documented while the stronger API is
introduced.

## Requirements

- no direct `func(**args)` path for governed remote calls;
- `ExecutionEngine` remains the only execution lifecycle;
- remote actor is recorded on the canonical Execution;
- errors raised by the callable produce failed Executions;
- Execution IDs are available in the remote response/projection;
- parent/trace lineage is preserved when the request legitimately supplies or
  inherits it;
- existing local Mesh event behavior remains unchanged.

## Acceptance

A test that patches/observes the registered Python callable must prove that the
callable is reached only after an `Execution` is created through the engine.

A remote callable failure must be visible as a failed canonical Execution, not
only as a JSON-RPC error string.

---

# 26.3 — Remote capability and contextual Policy enforcement

## Goal

Make remote authority identical in principle to local authority.

## Requirements

- operation registration maps to an explicit required capability when the
  operation is governed;
- the remote actor's capabilities are resolved through the existing capability
  model rather than Mesh-local ACLs;
- contextual Policy runs after capability possession and before compute;
- target entity / WorldSnapshot context is available to the same Policy engine
  used by local execution;
- Policy DENY is a failed/denied governed outcome;
- REQUIRE_APPROVAL enters the existing durable HITL path;
- Mesh does not implement its own approval system.

## Acceptance

The same operation invoked locally and remotely with equivalent actor/world
context receives equivalent capability/policy decisions.

A connected node without the required capability cannot execute the callable.

---

# 26.4 — Idempotency and replay semantics

## Goal

Make duplicate network delivery deterministic.

## Requirements

- canonical `request_id` is stable across retries;
- a durable or pluggable request ledger maps request identity to canonical
  Execution identity/outcome;
- duplicate delivery does not start a second governed Execution after the first
  request has reached a terminal or safely resumable state;
- duplicates of WAITING work resolve to the existing Execution rather than
  creating a second approval/effect path;
- request identity is scoped sufficiently to avoid accidental cross-actor
  collision;
- old/expired request IDs have an explicit retention/expiry policy;
- replay rejection is observable in telemetry.

## Non-claim

This does not claim exactly-once network delivery. It provides idempotent
runtime handling for at-least-once request delivery.

---

# 26.5 — Structured distributed outcomes

## Goal

Stop collapsing distributed lifecycle state into `result` vs arbitrary error
strings.

## Result contract

Remote responses should be able to represent at least:

```text
COMPLETED
FAILED
DENIED
WAITING
```

with:

- request ID;
- Execution ID;
- correlation/trace ID;
- structured result when completed;
- structured error category/message when failed or denied;
- approval/wait handle or resumable reference when waiting;
- schema/protocol version.

## Requirements

- WAITING/HITL never serializes as successful completion;
- runtime errors remain distinguishable from malformed protocol messages;
- response objects are JSON-safe projections, not persistence models;
- retrying a WAITING request uses idempotency to resolve the same Execution;
- a later completion can be queried or delivered without inventing a second
  Execution.

---

# 26.6 — Trusted participant/session seam

## Goal

Create the runtime interface where real authentication/signing mechanisms can
plug in without coupling execution semantics to one auth technology.

## Requirements

- participant identity resolution is a contract/interface;
- transport adapters provide credentials/session evidence to that resolver;
- resolved identity is immutable for one normalized request;
- authentication failure happens before authority evaluation;
- signing/verification adapters can be added later without changing Intent or
  Execution semantics;
- the default local acceptance implementation may use an in-memory test
  resolver/credential.

## Deferred

Production PKI, certificate rotation, OIDC, mTLS policy, hardware identity and
cloud tenancy are adapter/product concerns after the core seam exists.

---

# 26.7 — Two-node acceptance system

## Goal

Prove the complete distributed contract with two local Voodoo nodes.

## Acceptance scenario

```text
Node A actor
  ↓ remote request
Node B Mesh ingress
  ↓ identity
required capability
  ↓ contextual Policy
ExecutionEngine
  ↓
Python operation
  ↓
Execution result
  ↓ correlated response
Node A
```

The acceptance suite must also cover:

- denied capability;
- Policy denial;
- callable failure;
- WAITING/HITL;
- duplicate request delivery;
- disconnect followed by retry;
- lineage inspection;
- unknown operation;
- malformed protocol payload.

No external broker or cloud service is required for the acceptance path.

---

## Implementation order

The sprint should land in reviewable slices rather than one large rewrite:

1. **26.1 + 26.2 — Remote request + governed ingress.** Smallest architecture
   correction: direct remote calls stop bypassing the Runtime.
2. **26.3 — Authority parity.** Required capabilities and contextual Policy.
3. **26.4 + 26.5 — Reliability/lifecycle truth.** Idempotency and structured
   outcomes including WAITING.
4. **26.6 — Authentication seam.** Participant/session resolver contract.
5. **26.7 — Full local two-node acceptance.** Failure/retry/security matrix.

Each slice should have its own PR and be based on the latest merged `main`.

## First implementation slice: exact scope

The first implementation PR should be intentionally narrow.

### Add

- canonical `RemoteExecutionRequest` (name may be adjusted to existing protocol
  naming conventions);
- normalized request parser for current JSON-RPC Mesh `call` messages;
- exposed-operation metadata structure;
- adapter from normalized request → `Intent`;
- governed remote ingress through the existing `ExecutionEngine`;
- structured success/failure response containing canonical Execution identity;
- tests for normalization, unknown operation, successful engine-backed call,
  failed engine-backed call and lineage.

### Do not add yet

- persistent replay ledger;
- cryptographic signing;
- production credential backend;
- fleet concepts;
- new broker/transports;
- cloud control plane;
- Edge/World semantic ingestion.

This boundary keeps the first PR easy to reason about while removing the most
important architectural bypass immediately.

## Definition of Done

Sprint 26 is complete when all of the following are true:

- governed remote application work cannot bypass `ExecutionEngine`;
- remote actors have explicit identity before authority evaluation;
- remote and local work share capability, Policy, HITL and failure semantics;
- duplicate delivery cannot duplicate an already-accepted governed execution;
- request → Execution → result lineage is inspectable end-to-end;
- WAITING is represented as WAITING across the network;
- disconnect/retry paths are deterministic and tested;
- transport adapters do not own semantic authorization logic;
- the complete acceptance path works locally with zero external infrastructure;
- CI and CodeQL are green.

## North-star invariant

> **The network may move an Intent. It may never move execution outside the Runtime.**
