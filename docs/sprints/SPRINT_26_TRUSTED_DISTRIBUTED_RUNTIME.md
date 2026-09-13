# Sprint 26 — Trusted Distributed Execution Fabric

> Status: **COMPLETE**
> Closed: **2026-09-13**
> Theme: Remote work crosses the same governed Runtime boundary as local work.

## Outcome

Sprint 26 turned Mesh from an event/RPC transport with a privileged remote-call
path into a governed distributed execution boundary that preserves Voodoo's
single-Runtime model.

The implemented remote path is now:

```text
Remote participant
  ↓
Participant credential / authentication evidence
  ↓
Resolved immutable participant identity
  ↓
RemoteExecutionRequest
  ↓
Intent
  ↓
Server-side capability authority
  ↓
Contextual Policy / World target
  ↓
ExecutionEngine
  ↓
COMPLETED / FAILED / WAITING
  ↓
Correlated RemoteExecutionOutcome
```

The north-star invariant remains:

> **The network may move an Intent. It may never move execution outside the Runtime.**

## Delivered slices

| Slice | Delivered | Evidence |
|---|---|---|
| 26.1 | Transport-independent `RemoteExecutionRequest`, stable request/lineage model | PR #43 |
| 26.2 | Governed Mesh ingress through the existing `ExecutionEngine`; direct remote callable bypass removed | PR #43 · merge `37a740c7` |
| 26.3 | Server-side remote authority, capability parity and contextual Policy enforcement | PR #44 · merge `48407141` |
| 26.4 | Duplicate suppression, semantic request fingerprints, concurrent replay protection and durable SQLite replay | PR #45 · merge `8ee68dfd` |
| 26.5 | Structured distributed outcomes, including durable HITL `WAITING` and lifecycle refresh | PR #46 · merge `849c5e28` |
| 26.6 | Participant authentication resolver seam, credential-bound identity and pre-authority authentication | PR #49 · merge `44e0afc6` |
| 26.7 | Zero-infrastructure two-node acceptance matrix | PR #50 · merge `696bf7f5` |

## Architectural guarantees now implemented

1. **One Runtime.** Remote work uses the same `ExecutionEngine` lifecycle as
   local work.
2. **Identity before authority when authentication is configured.** A resolved
   participant identity replaces any actor label asserted by the request
   payload.
3. **Capability before compute.** Network connectivity does not grant authority;
   remote grants are assigned server-side.
4. **Policy parity.** Remote work reaches the same contextual Policy engine and
   target-Entity/World context as local work.
5. **Execution is canonical truth.** `RemoteExecutionOutcome` and replay records
   are projections/correlation records, not alternate execution state.
6. **WAITING is not success.** HITL waiting state crosses the distributed
   boundary explicitly and resumes the same canonical Execution after approval.
7. **Replay is explicit.** Stable `request_id` plus semantic fingerprinting
   suppress duplicate governed execution and reject conflicting reuse.
8. **Lineage survives the boundary.** Request, correlation, parent execution,
   target entity, actor, execution and trace identities remain inspectable.
9. **Local-first remains complete.** The full acceptance matrix requires no
   broker, cloud service or external identity provider.

## Reliability semantics

The replay layer provides deterministic duplicate handling for a receiving node:

- same `request_id` + same semantic request → existing outcome/Execution;
- same `request_id` + different request → `RemoteReplayConflict`;
- concurrent duplicate delivery → one governed compute path;
- SQLite replay can survive process restart;
- a replayed WAITING request follows canonical Execution state after approval.

This is intentionally **not** a claim of globally distributed exactly-once
network delivery. Downstream Effects continue to own their own idempotency and
external-system guarantees.

## Authentication seam

Sprint 26 introduced `ParticipantResolver`, `ParticipantEvidence` and immutable
`ParticipantIdentity`, plus an in-memory credential-backed implementation for
local/development systems.

Authentication and authority remain separate:

```text
credential evidence
    ↓
ParticipantResolver
    ↓
identity
    ↓
server-side authority
    ↓
Capability + Policy
```

A node that explicitly configures a participant resolver rejects missing or
invalid credentials before capability evaluation or Execution creation.

For backwards compatibility, a Mesh node without a resolver can still use the
legacy asserted-actor path. That compatibility mode is not an authenticated
identity claim.

## Two-node acceptance evidence

`tests/test_mesh_two_node_acceptance.py` proves the integrated contract using
two local nodes:

- authenticated success with forged payload actor replacement;
- request/trace/parent/target lineage;
- missing capability denial before compute;
- contextual Policy denial;
- WAITING/HITL, duplicate delivery, approval and resume on the same Execution;
- callable failure as a canonical FAILED Execution;
- lost-response/retry behavior without duplicate compute;
- unknown operation rejection without creating an Execution;
- authentication failure before Runtime work;
- malformed request rejection before application execution.

The final implementation passed Ruff format/lint, Python 3.12, Python 3.13 and
CodeQL before merge.

## Explicit non-claims / deferred product work

Sprint 26 does **not** implement or claim:

- production PKI or certificate authority;
- OIDC/cloud identity integration;
- production mTLS policy or certificate rotation;
- hardware-backed participant identity;
- global exactly-once network delivery;
- distributed consensus/leader election;
- fleet scheduling or multi-device mission planning;
- physical ESP32 reference firmware;
- Edge semantic event → `Observation` / World Model ingestion;
- multi-language SDK generation;
- cloud/control-plane productization.

The core seams now exist for those systems without coupling them to Mesh or
creating a second Runtime.

## Next step

No Sprint 27 scope is declared here. After Sprint 26, the repository should be
reviewed again as a whole — Runtime, World/Ontology, Agency, UI, Edge, Mesh,
protocol and developer experience — and the next initiative should be chosen
from the highest-value remaining architectural gap rather than by inertia.
