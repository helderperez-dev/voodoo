# Sprint 8 — Quality & Docs

> Implementation tracking for S8. Derived from IMPLEMENTATION_PLAN.md §5.1–5.4.
> **Status**: Planned

---

## Goal

Complete the test pyramid, write documentation, build the killer AI SaaS demo,
and validate packaging from a clean environment.

---

## Workstreams

### S8-1: Test pyramid completion
- [ ] Contract suite: public API pinned; compatibility tests for deprecated paths
- [ ] Integration: full reactive loop; mesh→worker→agent→tool→db;
      auth-guarded routes; MCP tool exposure
- [ ] Security suite per §10; deterministic mock LLM provider (no network in CI)
- [ ] Benchmarks: baseline vs Phase 0 numbers; regression gate in CI (warn-level)
- [ ] **Files**: `tests/test_integration.py`, `tests/test_security.py` (extend),
      `scripts/benchmark.py` (extend)

### S8-2: Documentation
- [ ] Docs pages: Installation · Hello World · Components · Routing · State ·
      Events · Data · Auth · Agents · Tools · MCP · Mesh · Workers ·
      Telemetry · Deployment · Architecture
- [ ] Page formula: *What it is → minimal example → common usage → advanced →
      API reference*
- [ ] README rewritten around the AI-native thesis
- [ ] **Files**: `docs/` (new pages), `README.md` (rewrite)

### S8-3: Killer example — AI SaaS demo (G19)
- [ ] `examples/hello_world/`, `examples/dashboard/`, `examples/realtime/`,
      `examples/ai_agent/`, `examples/ai_saas/`
- [ ] The `ai_saas` demo exercises the full chain:
      UI → mesh → agent → tool → MCP → worker → db → telemetry
- [ ] **Files**: `examples/` (new)

### S8-4: Packaging & installation (G17, G20)
- [ ] Optional extras wired: `voodoo[ai]`, `voodoo[mcp]`, `voodoo[dev]`
- [ ] Core install stays lean (providers lazy)
- [ ] Clean-env validation: `uv tool install voodoo-framework` → `voodoo new`
      → `voodoo dev` works with zero manual steps
- [ ] **Files**: `pyproject.toml` (finalize)

---

## File Changes

| File | Action | Description |
|---|---|---|
| `tests/test_integration.py` | NEW | Cross-subsystem integration tests |
| `tests/test_security.py` | MODIFY | Threat model coverage |
| `scripts/benchmark.py` | MODIFY | Full benchmark suite |
| `docs/*.md` | NEW | 16 documentation pages |
| `README.md` | MODIFY | Rewrite on AI-native thesis |
| `examples/` | NEW | 5 example apps |
| `pyproject.toml` | MODIFY | Optional extras finalized |

---

## Exit Criteria

- [ ] Quality gate green: pytest + mypy + ruff + package build + install test
- [ ] Integration tests: UI→state→mesh→worker→agent→tool→db
- [ ] Security tests cover §10 threat model
- [ ] Benchmarks not regressed from Phase 0
- [ ] Documentation complete (16 sections)
- [ ] `examples/ai_saas` runs end-to-end
- [ ] Clean install works: `uv tool install` → `voodoo new` → `voodoo dev`
- [ ] Full suite green; ruff clean; committed (no version bump)
