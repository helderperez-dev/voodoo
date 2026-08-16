# Sprint 7 — Agent, Mesh & MCP

> Implementation tracking for S7. Derived from IMPLEMENTATION_PLAN.md §4.3–4.7.
> **Status**: Planned

---

## Goal

Deliver the `Agent` class with real provider execution, tool calling, streaming,
and run records. Finalize Mesh (`emit`/`on`/`expose`) and MCP integration with
the Tool Registry. AI telemetry with token/cost accounting.

---

## Workstreams

### S7-1: Agent (G6)
- [ ] `Agent(model=..., tools=[...])`; execution loop: prompt → model →
      tool calls (via registry) → final
- [ ] `run()` returns `AgentRun` record (`run_id`, model, provider, timings,
      tokens, cost, tool calls, status, error)
- [ ] `stream()` yields normalized events: `text | tool_started |
      tool_finished | thinking | error | completed`
- [ ] Lifecycle states: created → configured → running → (tool_call ⇄
      thinking) → completed | error → retry/failed
- [ ] Explicit `context={...}` parameter; context ≠ memory ≠ database
- [ ] **File**: `voodoo/ai/agent.py` (new, replaces stub)

### S7-2: Unified AI events over Mesh (G12)
- [ ] Agent lifecycle publishes namespaced mesh events: `agent.started`,
      `agent.output`, `agent.tool.started`, `agent.tool.completed`,
      `agent.failed`, `agent.completed`
- [ ] UI reacts to agent activity through Mesh — no special agent/WS plumbing
- [ ] Prove the flagship pattern in tests

### S7-3: MCP integration (G5)
- [ ] MCP layer consumes `ToolRegistry` (no separate `@mcp_tool`)
- [ ] Existing `MCPClient`/`mcp` stabilized
- [ ] Tools exposable via MCP with schema generation from `ToolSpec`
- [ ] **File**: `voodoo/mcp.py` (refactor onto ToolRegistry)

### S7-4: Mesh stabilization (G12)
- [ ] Finalize `mesh.emit / mesh.on / mesh.expose`
- [ ] Event envelope (id, ts, source, correlation_id)
- [ ] Namespaced event names enforced
- [ ] `expose` = explicit remote capability with permission awareness
- [ ] Local event ≠ remote event: boundary documented
- [ ] **File**: `voodoo/mesh.py` (refactor)

### S7-5: AI telemetry (G14)
- [ ] Per-run records: model, provider, latency, tokens, cost, tool calls,
      errors, retries
- [ ] Agent/tool spans correlated with originating request (S5 carrier)
- [ ] **File**: `voodoo/telemetry.py` (extend)

### S7-6: Exports & contract
- [ ] Export `Agent`, `AgentRun` from `voodoo`
- [ ] Update `__all__` and contract test
- [ ] **Files**: `voodoo/__init__.py`, `tests/test_contract_api.py`

### S7-7: Tests
- [ ] `tests/test_agent.py`: run, stream, tool calls, lifecycle, errors, retries
- [ ] `tests/test_mesh.py`: emit/on/expose, envelope, namespaces
- [ ] `tests/test_mcp.py`: tool registry integration, schema generation
- [ ] Full suite green; ruff clean; commit

---

## File Changes

| File | Action | Description |
|---|---|---|
| `voodoo/ai/agent.py` | NEW | Agent class, run/stream, lifecycle |
| `voodoo/mcp.py` | MODIFY | Refactor onto ToolRegistry |
| `voodoo/mesh.py` | MODIFY | Envelope, namespaces, finalize API |
| `voodoo/telemetry.py` | MODIFY | AI telemetry, run records |
| `voodoo/__init__.py` | MODIFY | Export Agent, AgentRun |
| `tests/test_agent.py` | NEW | Agent tests (mock provider) |
| `tests/test_mesh.py` | NEW | Mesh tests |
| `tests/test_mcp.py` | NEW | MCP + ToolRegistry tests |

---

## Exit Criteria

- [ ] `Agent(model="mock:test").run(prompt)` returns `AgentRun` with tokens/cost
- [ ] `Agent.stream()` yields normalized events (text, tool_started, etc.)
- [ ] Agent publishes mesh events (`agent.started`, `agent.completed`, etc.)
- [ ] Same `@tool` invoked by: python call, agent run, MCP consumer
- [ ] Mesh `emit`/`on`/`expose` finalized with event envelope
- [ ] Token/cost accounting on every run
- [ ] Full suite green; ruff clean; committed (no version bump)
