# Sprint 24 — Agency Foundation, Ontology & World Model

**Status:** WIP  
**Target release:** 2.7.0  
**Branch:** `feat/agency-foundation`  
**Purpose:** close the gap between a durable operational runtime and a persistent, world-aware AI runtime before the first physical reference implementation.

---

## 1. Why this sprint exists

Voodoo already has a real execution substrate: durable `Execution`, capabilities, workers, HITL, scheduling, agent runs, memory storage, Mesh, protocol schemas, and an Edge gateway. The remaining gap is no longer “build more framework features.” The gap is that the runtime can execute work reliably, but it does not yet maintain a coherent model of the world that autonomous software can observe, reason over, change, and verify.

The architectural target for this sprint is:

```text
Entity
  ↓
Observation
  ↓
World Model / Relationships / State
  ↓
Goal / Intent
  ↓
Planner
  ↓
Capability + Policy
  ↓
Execution
  ↓
Effect
  ↓
Outcome / ACK
  ↓
Observation
  └───────────────────────↺
```

The sprint also fixes runtime truth gaps discovered during code review so the AI layer never disagrees with the canonical `Execution` lifecycle.

---

## 2. Non-negotiable invariants

1. **Execution remains the only operational source of truth.** Agent, Tool, Mesh, Worker, Human, and Device work must not invent parallel lifecycle semantics.
2. **Entity is identity; State is mutable fact; Observation is evidence.** These must not be collapsed into one object.
3. **World Model is a projection, not a second database runtime.** It consumes facts and relationships and exposes query semantics; it does not replace `Model`, Memory, or `ExecutionStore`.
4. **Effects are commands or side effects; observations are what was actually seen.** Desired state and observed state are distinct.
5. **Capabilities grant authority. Policies narrow authority using runtime context.** No ambient authority.
6. **AI is a compute participant, not the runtime itself.** Deterministic compute, humans, workers, and devices stay first-class.
7. **Local-first remains zero-infra.** New core functionality must work with only the base package and in-memory/SQLite storage.
8. **Durability claims require restart/failure-path tests.** No feature is considered durable because a class has a `save()` method.
9. **Remote execution crosses the same authorization boundary as local execution.** Mesh RPC cannot bypass `ExecutionEngine` or capability checks.
10. **No physical-system shortcut.** Edge events must eventually become observations/intents routed through world state and runtime policy, not ad-hoc callbacks.

---

## 3. Definition of Done

Sprint 24 is complete only when all of the following are true:

- Agent failure is reflected as failed `Execution`, not a successful execution containing a failed `AgentRun`.
- Agent registry records the canonical `execution_id` and correct `trace_id`.
- Episodic memory is isolated by stable `agent_id` and references canonical execution IDs.
- Task upstream results are correctly available to agent prompts and compute participants.
- Adaptive execution can invoke agent participants, respects `max_iterations`, tracks step-local retries, and has tests for replanning/fallback boundaries.
- Remote Mesh calls enter `ExecutionEngine`, preserve trace/correlation identity, and enforce capabilities before side effects.
- A first-class ontology/world package exists with `Entity`, `Relationship`, `Observation`, and `WorldModel` semantics.
- World state can be reconstructed from observations after process restart using a durable local store.
- Relationships can be queried in both directions and constrained by type/predicate.
- Observations preserve source, confidence, time, trace, and execution lineage.
- Agent context can recall relevant world facts without directly owning the world store.
- A policy layer can allow/deny an effect based on actor, capability, target entity, world state, and constraints.
- Edge semantic events can be mapped to observations and runtime intents; heartbeat remains telemetry-only.
- Effect delivery can update world state only after an observed/acknowledged outcome, never merely because a command was issued.
- Protocol schemas include world entities so non-Python clients can exchange them.
- A complete canary demonstrates: observation → world update → agent/planner decision → authorized execution → effect → acknowledgement → world update.
- Quality gates are green on supported Python versions, including mypy and lean-package smoke tests.

---

## 4. Work breakdown

### Phase 0 — Runtime truth and quality gates

**Goal:** remove contradictions before adding autonomy.

- [ ] Finish CI truth work: actual Python matrix, mypy, lean wheel smoke.
- [ ] Fix agent error propagation into `ExecutionEngine`.
- [ ] Fix Agent Registry `execution_id` lineage.
- [ ] Isolate episodic memory by `agent_id`.
- [ ] Store canonical execution ID in episodic memory.
- [ ] Fix Task upstream result propagation.
- [ ] Resolve outstanding resource-lifecycle warnings instead of suppressing them.

**Acceptance:** an intentionally failing provider/tool produces a failed canonical execution and a linked failed agent run after persistence/reload.

### Phase 1 — Ontology kernel

**Goal:** introduce the minimum stable semantic model of the world.

Core concepts:

- `Entity`: stable identity + type + properties + metadata.
- `Relationship`: directed typed edge between entities.
- `Observation`: evidence about an entity/property from a source at a point in time.
- `WorldModel`: query and projection API over entities, relationships, and observation history.
- `WorldStore`: persistence protocol; in-memory first, SQLite durable implementation before phase completion.

Required operations:

```python
world.put_entity(entity)
world.relate(source, "located_in", target)
world.observe(entity_id, "battery.level", 0.82, source="telemetry")
world.entity(entity_id)
world.relationships(entity_id, predicate="located_in")
world.neighbors(entity_id, direction="out")
world.history(entity_id, "battery.level")
world.snapshot(entity_id)
```

Rules:

- observations are append-only evidence;
- entity properties are projections of the latest accepted observation;
- confidence and observation time are retained;
- stale observations do not overwrite newer projected state unless explicitly forced;
- relationships are stable IDs, not anonymous tuples;
- world model must be serializable through Voodoo Protocol later in this sprint.

**Acceptance:** create entities, relate them, apply observations, query current state and history, close the store, reopen it, and recover identical world semantics.

### Phase 2 — Cognitive memory and world recall

**Goal:** move memory from “storage of text” toward useful runtime recall without forcing vector infrastructure.

- [ ] Add a `RecallContext` projection combining episodic memory and world facts.
- [ ] Agent recall is scoped by `agent_id`.
- [ ] Add deterministic lexical/ranked recall baseline.
- [ ] Add optional embedding adapter later, not as a core dependency.
- [ ] Keep memory entries distinct from world facts: memory is what an entity remembers; world model is what the runtime currently believes.
- [ ] Add consolidation hooks from completed Executions into episodic memory.
- [ ] Add source execution and trace lineage to recalled context.

**Acceptance:** two agents sharing a world see the same current world fact but retrieve different private episodic histories.

### Phase 3 — Adaptive planning becomes executable agency

**Goal:** turn the current capability matcher/supervisor into a dependable agency loop.

- [ ] A `ComputeParticipant` may execute deterministic compute, Agent, Human, Worker delegate, or remote capability.
- [ ] Agent participants are invoked natively by AdaptiveSupervisor.
- [ ] `max_iterations` is an actual hard stop.
- [ ] Retry counters are step-local, not global across unrelated steps.
- [ ] Add plan-step outputs as inputs to following steps.
- [ ] Introduce explicit goal decomposition seam; deterministic planner remains default.
- [ ] Add optional AI planner adapter behind the same `Plan` contract.
- [ ] Replan after meaningful world change or failed capability resolution.
- [ ] Record every planning/supervisor decision with execution lineage.

**Acceptance:** a goal requiring two capabilities can choose participants, fail one path, select a fallback, request approval for a sensitive step, resume, and complete without losing lineage.

### Phase 4 — Contextual operational policy

**Goal:** evolve capabilities from static grants into constrained authority.

Policy decision input:

```text
actor
capability
target entity
intent
current world snapshot
execution context
constraints
```

Example policy:

```text
agent.inspect may control robot-17
only while mission-31 is active
only inside warehouse-2
speed <= 0.5 m/s
battery > 20%
human override always wins
```

- [ ] Add `PolicyDecision` (`allow`, `deny`, `require_approval`).
- [ ] Add composable policy evaluators.
- [ ] Integrate policy after capability resolution and before effectful compute.
- [ ] Make policy decisions observable and testable.
- [ ] Never bury policy logic in Agent prompts.

**Acceptance:** the same capability is allowed or denied based on world/context conditions without changing agent code.

### Phase 5 — Mesh becomes a trusted execution fabric

**Goal:** remote calls obey the same runtime rules as local calls.

- [ ] Remote `call` resolves an exposed capability into an Intent.
- [ ] Execute through `ExecutionEngine`; no direct `func(**args)` side-effect path.
- [ ] Carry source identity, correlation ID, trace ID, and parent execution identity.
- [ ] Capability authorization before remote side effects.
- [ ] Add replay/idempotency protection for request IDs.
- [ ] Add signing/authentication seam without introducing mandatory infrastructure.
- [ ] Keep events and RPC semantically distinct.

**Acceptance:** an unauthorized remote caller cannot execute an exposed side effect; an authorized call produces a persisted Execution and traceable response.

### Phase 6 — Edge ↔ World integration

**Goal:** connect physical observations to the same semantic world model.

- [ ] Map device identity to `Entity`.
- [ ] Map state sync to versioned observations.
- [ ] Map semantic device events to observations + Intents.
- [ ] Keep heartbeat as telemetry-only.
- [ ] Effects target entities/capabilities explicitly.
- [ ] Effect submission does not mutate observed world state.
- [ ] Effect ACK/outcome creates an observation and closes the feedback loop.
- [ ] Preserve message idempotency across world updates.

**Acceptance:** simulator sends state/event → world changes → runtime decides an effect → simulator receives and ACKs → world records observed outcome.

### Phase 7 — Protocol and multi-language boundary

**Goal:** make world/agency concepts transportable beyond Python.

Add protocol schemas for:

- Entity
- Relationship
- Observation
- WorldSnapshot
- PolicyDecision
- Plan / PlanStep where needed

- [ ] JSON Schema export.
- [ ] Backward-compatible schema versioning.
- [ ] Round-trip tests.
- [ ] Define SDK generation input contract.
- [ ] TypeScript reference SDK may follow as Sprint 25/26; no hand-written SDK sprawl inside this sprint unless needed by acceptance testing.

**Acceptance:** protocol schemas round-trip world messages without importing runtime implementation classes.

### Phase 8 — Canary: persistent autonomous operational loop

Build one executable reference application using only public APIs:

```text
virtual device / simulator
    ↓ observation
WorldModel
    ↓ current facts
Goal
    ↓
Planner / Agent
    ↓
Policy
    ↓
Execution
    ↓
Effect
    ↓
device simulator
    ↓ ACK / observation
WorldModel
```

The canary must include:

- restart in the middle of the flow;
- one denied operation;
- one human approval;
- one retry/fallback;
- one relationship query;
- one agent recall;
- complete trace/execution lineage.

This canary becomes the acceptance reference before a physical ESP32/reference robot sprint.

---

## 5. Proposed package ownership

```text
src/voodoo/
  world/
    __init__.py
    models.py          # Entity, Relationship, Observation, snapshots
    store.py           # WorldStore protocol + in-memory baseline
    sqlite.py          # durable local store
    model.py           # WorldModel projection/query service
    policy.py          # contextual policy contracts/evaluation
  runtime/
    planner.py         # planning contracts; no world persistence
    adaptive.py        # supervision / replanning loop
  ai/
    agent.py           # compute participant + recall integration
  mesh/
    ...                # transport/fabric, not business workflow ownership
  edge/
    ...                # device boundary; feeds world/runtime
  protocol/
    schemas.py         # wire contracts only
```

The package boundaries are intentional:

- `world` knows semantic entities and observations;
- `runtime` knows how work executes;
- `ai` reasons as a participant;
- `mesh` transports messages;
- `edge` adapts devices;
- `protocol` defines stable wire shapes.

No package may create a second execution engine.

---

## 6. Milestones / merge sequence

To keep reviewable PRs and avoid a giant rewrite, implementation should land in this order:

1. **24.1 — World kernel:** models + in-memory WorldModel + tests + sprint spec.
2. **24.2 — Runtime truth:** agent lineage/error/memory/upstream fixes.
3. **24.3 — Durable world:** SQLite world store + recovery tests.
4. **24.4 — Adaptive agency:** agent participants, iteration/retry correctness, step outputs.
5. **24.5 — Policy:** contextual authority before effects.
6. **24.6 — Trusted Mesh:** remote calls through runtime authorization/execution.
7. **24.7 — Edge-world loop:** observations/effects/ACK integration.
8. **24.8 — Protocol + canary:** schemas and full restart-safe acceptance application.
9. **24.9 — Hardening:** mypy, load/recovery tests, warnings, docs, public API review.

Each milestone must be independently green and mergeable.

---

## 7. Testing strategy

Every milestone adds tests at the correct layer:

- unit tests for pure semantic rules;
- contract tests for store/provider boundaries;
- restart tests for every durability claim;
- integration tests for runtime/world/agent crossing points;
- one end-to-end canary for the complete feedback loop;
- no tests that prove behavior by mocking away the boundary being tested.

Mandatory final gate:

```bash
just format
just lint
just test
uv run mypy src/voodoo
```

CI must also prove the declared Python support matrix and a clean base-wheel install.

---

## 8. Explicitly deferred

The following are valuable but are not required to call Sprint 24 complete:

- production vector database;
- full Palantir-style ontology editor/UI;
- distributed consensus;
- fleet-scale scheduler;
- GPU inference runtime;
- TypeScript/Go/Rust SDK families beyond the protocol/generation contract;
- physical ESP32/reference robot firmware;
- cloud control plane / hosted Voodoo Runtime.

They become much safer after the semantic/runtime loop in this sprint is proven.

---

## 9. First implementation slice — 24.1

The first code slice starts immediately with the world kernel because it is additive, dependency-free, and establishes the semantic vocabulary every later phase consumes.

Deliverables:

- [x] Sprint specification recorded.
- [ ] `Entity`, `Relationship`, `Observation`, `WorldSnapshot`.
- [ ] `WorldStore` protocol and in-memory implementation.
- [ ] `WorldModel` current-state projection and relationship/history queries.
- [ ] stale-observation handling.
- [ ] unit tests for identity, relationships, projection, history, confidence/lineage, and stale observations.

Once 24.1 is green, the next milestone is 24.2 Runtime Truth before adding durability or Edge integration.
