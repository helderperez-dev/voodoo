# Voodoo Runtime — Implementation Roadmap & Task List

Source of truth: `SPEC.md` §65 *Suggested Implementation Order* and §66 *Definition of Done for the Core Runtime*.

Status legend:

```text
[x] done            [~] in progress       [ ] pending
```

---

## Phase 0 — Audit (complete baseline)

- [x] Architecture map — `docs/architecture.md`, `docs/ai/ARCHITECTURE.md`
- [x] Execution path map — routes (`voodoo.routing.api`), pages (`voodoo.routing.pages`), workers (`voodoo.workers.queue`), mesh (`voodoo.mesh`), MCP (`voodoo.mcp`)
- [x] Primitive map — `src/voodoo/primitives/*` (Intent, Capability, Compute, Constraint, Resource, Effect, State, Time)
- [x] Dependency map — `voodoo.core.app` creates the Starlette app; workers/queue seam documented in `voodoo.workers.queue`
- [x] Technical debt list — in-memory telemetry store, blocking CLI scaffolding fetch, no persistence before Phase 11

---

## Phase 1 — Execution Context

Files: `src/voodoo/runtime/context.py`

- [x] `ExecutionContext` — execution_id, trace_id, parent_execution_id, actor, intent
- [x] parent/child creation (`child()`), inheritance of trace + narrowed capabilities
- [x] lifecycle flags (created_at, deadline, cancelled)
- [x] cancellation (`cancel()`), deadline (`with_deadline`, `deadline_expired`, `remaining_seconds`)
- [x] telemetry propagation — `use_context()` mirrors trace_id onto `voodoo.telemetry.trace_id_var`
- [x] capability grant/hold (`grant`, `has_capability`), constraint registration (`constrain`)
- [x] effect accumulation (`add_effect`) — agent tool calls land on the Execution record

Accepted by: `tests/test_runtime.py::TestExecutionContext` (8 tests).

---

## Phase 2 — Execution Core

Files: `src/voodoo/runtime/execution.py`

- [x] `Execution` model — serializable, status lifecycle (`created → planned → authorized → running → waiting → completed|failed|cancelled|timed_out`)
- [x] Intent integration (`intent`, `add_effect`)
- [x] Compute integration (`compute` spec, resources)
- [x] Effect integration (`effects`, `add_effect`)
- [x] State integration (`state_changes`, `record_state_change`)
- [x] cost/duration/success queries + `describe()`

Accepted by: `tests/test_runtime.py::TestExecutionEngine`.
Structured error model: `src/voodoo/runtime/errors.py` (`ExecutionError` + subclasses that retain execution_id/trace_id).

---

## Phase 3 — Capability Enforcement

Files: `src/voodoo/runtime/capability.py`

- [x] capability resolution (`CapabilityResolver.resolve` → allowed / denied / requires_approval)
- [x] scope matching (exact scope when required)
- [x] authorization (`authorize()` raises `CapabilityDenied` / `ApprovalRequired`)
- [x] delegation — child contexts narrow authority; `Engine.delegate()` caps privilege escalation
- [x] revocation — revoked/expired capabilities resolve denied
- [x] audit surface — `describe()` lists registered + approval-gated capabilities; `voodoo inspect capabilities`

Accepted by: `tests/test_runtime.py::TestCapabilityResolver` (7 tests).

---

## Phase 4 — Resource / Constraint Enforcement

Files: `src/voodoo/runtime/constraint.py`

- [x] constraint evaluation (`ConstraintEnforcer.evaluate` → continue | stop | fail | request_approval)
- [x] resource accounting (`ResourceAccountant` — cost, tokens, latency budgets + `remaining()`)
- [x] timeouts — deadline enforcement pre + post compute
- [x] cost limits — post-compute enforcement against accumulated usage
- [x] token limits
- [x] iteration limits
- [x] approval requirements (`Constraint.approval_required()` → `ApprovalRequired`)
- [x] cancellation → `ExecutionCancelled`
- [x] retry decision surfaced to adaptive runtime (Phase 13 hook)

Accepted by: `tests/test_runtime.py::TestConstraintEnforcer`, `TestResourceAccountant`.

---

## Phase 5 — Agent Integration

Files: `src/voodoo/ai/agent.py`, `src/voodoo/runtime/engine.py`

- [x] `Agent(capabilities=[...])` — capability grants
- [x] tool calls gated by `ToolSpec.permissions` (agent grant OR active runtime context)
- [x] unauthorized tool calls denied before side effect, recorded as failed `Effect`
- [x] `tool.called` / `tool.completed` mesh events
- [x] tool effects lifted onto the parent `Execution` record (via `ExecutionContext.add_effect`)
- [x] existing Agent API preserved (run/stream/tool-loop contracts)

Accepted by: `tests/test_agent_runtime.py` (7 tests), `tests/test_agent.py` (no regression).

---

## Phase 6 — Tool / MCP Integration

- [x] Tools: `ToolSpec.permissions` enforced in Agent path (`src/voodoo/ai/tools/registry.py`)
- [x] MCP dispatch (`voodoo.mcp.MCPServer._run_tool_call`) routed through the runtime with capability gate
- [x] `voodoo inspect tool` already lists recent calls; extend to MCP-originated calls
- [x] MCP calls produce `Execution` records (intent `mcp:<tool>`)

Accepted by: `tests/test_mcp_runtime.py` (3 tests) + `tests/test_mcp.py` (no regression).

---

## Phase 7 — Task

Files: `src/voodoo/runtime/task.py`

- [x] `Task` — first-class executable unit through the common engine
- [x] agent as compute (`Task(agent=...)`)
- [x] deterministic compute (`Task(compute=...)`)
- [x] human compute (`Task(human=True, approval_capability=...)`) — raises `ApprovalRequired`, resumable
- [x] `depends_on` composition
- [x] capabilities / constraints / resources / timeout compile onto Intent
- [x] retries with fresh intent + `ExecutionError` on exhaustion
- [x] conditional skip (`condition`)

Accepted by: `tests/test_runtime.py::TestTask`, `tests/test_agent_runtime.py`, `tests/test_human.py::TestTaskHuman`.

---

## Phase 8 — Workflow

Files: `src/voodoo/runtime/workflow.py`, `src/voodoo/runtime/human.py`

- [x] sequential (dependency-ordered)
- [x] parallel (dependency-aware `asyncio.gather`)
- [x] conditional (per-task conditions + strategy)
- [x] iterative (`until` predicate + `max_iterations`)
- [x] delegated (child executions per task)
- [x] hierarchical (nested Workflows)
- [x] retry — expressed per-task (`Task.retries`)
- [x] human approval inside a workflow — engine `approve`/`deny` implemented + workflow-level test
- [x] adaptive (Phase 13) — `WorkflowStrategy.ADAPTIVE` delegates to planner + supervisor

Accepted by: `tests/test_runtime.py::TestWorkflow` (5 tests), `tests/test_human.py::TestWorkflowHuman`.

---

## Phase 9 — Execution Graph

Files: `src/voodoo/runtime/graph.py`

- [x] `ExecutionGraph` from engine records (roots = no parent, children by `parent_execution_id`)
- [x] `describe()` tree for inspect
- [x] `find(execution_id)`

Accepted by: `tests/test_runtime.py::TestExecutionGraph`.

---

## Phase 10 — CLI Inspection

Files: `src/voodoo/cli/inspect.py`, `src/voodoo/cli/recover.py`

- [x] `voodoo inspect run [id|--json]` — list + single execution (status, intent, capabilities, effects, cost, duration)
- [x] `voodoo inspect agent` — recent agent runs
- [x] `voodoo inspect tool` — recent tool calls
- [x] `voodoo inspect task` — task-driven executions
- [x] `voodoo inspect workflow [trace]` — execution tree grouped by trace
- [x] `voodoo inspect state` — observable state changes recorded on executions
- [x] `voodoo inspect capabilities` — registered capabilities + tool permission requirements
- [x] `voodoo inspect mesh` — exposed functions, event handlers, active nodes
- [x] `voodoo inspect approvals` — pending/decided human approvals
- [x] `voodoo recover [--store ...] [--json]` — reload unfinished executions from the store

Accepted by: `tests/test_cli_inspect.py` (16 tests).

---

## Phase 11 — Durable Recovery

Files: `src/voodoo/runtime/persistence.py`, `src/voodoo/runtime/engine.py`

- [x] `ExecutionStore` protocol (persistence seam)
- [x] `InMemoryExecutionStore`
- [x] `JSONFileExecutionStore` — append-only JSONL, corrupt-line tolerant
- [x] `Engine.use_store(store)` attachment
- [x] checkpointing — `_persist` on every terminal state + on `waiting` (approval)
- [x] `Engine.recover()` — reload unfinished (created/planned/authorized/running/waiting) executions
- [x] resume semantics for re-running approved executions after restart (test)
- [x] checkpointing mid-workflow (per-task) rather than only at terminal/waiting

Accepted by: `tests/test_persistence.py` (12 tests).

---

## Phase 12 — Planner

Files: `src/voodoo/runtime/planner.py` (new)

- [x] inputs: Intent + available Capabilities + Constraints + registered Compute participants (agents, workers, tools, humans)
- [x] output: selected strategy + compute participant assignment
- [x] deterministic first: exact capability → compute resolution
- [x] `WorkflowStrategy.ADAPTIVE` delegates to planner
- [x] `voodoo inspect plan <intent>` debug surface

Accepted by: `tests/test_planner_adaptive.py` (6 planner tests).

---

## Phase 13 — Adaptive Runtime

Files: `src/voodoo/runtime/adaptive.py` (new)

- [x] supervisor loop — decisions: continue | retry | delegate | fallback | wait | request_approval | fail
- [x] dynamic planning (planner consulted per step)
- [x] compute selection (agent vs deterministic vs human based on capability/constraint)
- [x] delegation (child executions with narrowed authority)
- [x] fallback (secondary compute participant on failure)
- [x] resource optimization (cost/latency budget steering)

Accepted by: `tests/test_planner_adaptive.py` (13 tests: 6 planner + 7 adaptive).

---

## Definition of Done — Core Runtime integrations

From SPEC §66: **all of these must run through the same execution system and expose execution_id / trace_id / status / effects / state / cost / error / parent-execution:**

| Participant | Status | Engine surface |
|---|---|---|
| HTTP request | [x] | `voodoo.routing.api` route wrapper → `engine.execute` |
| Agent | [x] | `Task(agent=...)`, `Engine.execute(compute=agent_fn)` |
| Tool | [x] | capability-gated in `Agent._execute_tool_call` |
| MCP tool | [x] | `MCPServer._run_tool_call` dispatch through engine |
| Worker | [x] | `voodoo.workers.queue._run_worker` executes via engine |
| Task | [x] | `Task.run()` |
| Workflow | [x] | `Workflow.run()` |
| Human approval | [x] | `Engine.approve` / `Engine.deny`, `ask_human`, waiting-state |
| Event handler | [x] | `voodoo.mesh` handler execution as child executions |

Each integration must expose: `execution_id`, `trace_id`, `status`, `effects`, `state`, `cost`, `error`, `parent_execution_id`.

---

## Validation

```bash
uv run pytest -q -o addopts="" -k "not sync_ai_assets and not ai_init"   # full suite
uv run ruff check src/voodoo/runtime src/voodoo/cli/inspect.py src/voodoo/ai/agent.py tests/
```

Current state: **547 tests passing**, ruff clean. (7 deselected tests are pre-existing network-dependent CLI scaffolding tests.)

New test files added:

- `tests/test_human.py` — approval flow, approve/deny/resume, `Task(human=True)`, workflow approval (6 tests)
- `tests/test_persistence.py` — JSONL store round-trip, corrupt lines, `recover()`, approval survival, mid-workflow checkpointing (12 tests)
- `tests/test_http_runtime.py` — API route → Execution record (5 tests)
- `tests/test_workers.py` — worker job → Execution record (2 new tests added)
- `tests/test_mcp_runtime.py` — MCP `tools/call` → capability gate + Execution (3 tests)
- `tests/test_mesh.py` — mesh handler → child execution (2 new tests added)
- `tests/test_planner_adaptive.py` — capability → compute resolution + supervisor decisions + resource budget + constraint retry hook (13 tests)
- `tests/test_cli_inspect.py` — `inspect approvals` + `voodoo recover` + `inspect plan` (6 new tests added, 18 total)
