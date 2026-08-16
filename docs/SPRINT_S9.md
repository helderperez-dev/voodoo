# Sprint 9 — Freeze & Release

> Implementation tracking for S9. Derived from IMPLEMENTATION_PLAN.md §6.
> **Status**: Planned

---

## Goal

Ship Voodoo 1.0 with a stable, small, documented API. Tag the release.

---

## Workstreams

### S9-1: Freeze public API
- [ ] Contract tests marked `semver: 1.0`
- [ ] No new exports without version bump
- [ ] `__all__` frozen

### S9-2: Cleanup
- [ ] Remove dead/duplicate code found since Phase 0
- [ ] Remove accidental exports
- [ ] Deprecation notices accurate
- [ ] Final docs pass

### S9-3: Release validation
- [ ] Full suite + benchmarks from clean environment
- [ ] Changelog written
- [ ] README final
- [ ] Tag release
- [ ] Announce with honest positioning ("built for the future of adaptive
      applications", never "self-evolving today")

---

## File Changes

| File | Action | Description |
|---|---|---|
| `tests/test_contract_api.py` | MODIFY | Mark semver: 1.0 |
| `CHANGELOG.md` | NEW | 1.0 changelog |
| `README.md` | MODIFY | Final pass |
| `voodoo/__init__.py` | MODIFY | Version bump to 1.0.0 |

---

## Exit Criteria (Definition of Done — §15)

- [ ] `App` finalized · routing finalized · component API finalized
- [ ] PascalCase components · lowercase decorators — verified by contract test
- [ ] Semantic HTML components · accessibility defaults
- [ ] Reactive state · Python-native events · WS hidden behind state/event APIs
- [ ] Tailwind isolated as adapter · custom CSS supported · theme final
- [ ] Model API simplified · auth hardened · security reviewed
- [ ] Workers/queue stabilized · retries/timeouts/telemetry
- [ ] Tool abstraction final (one tool → Python/Agent/MCP/Mesh)
- [ ] Real Agent provider abstraction (openai/anthropic/gemini/ollama)
- [ ] Agent streaming · agent tools · agent runs
- [ ] MCP consumes Tool Registry · Mesh API final
- [ ] Agent↔Mesh↔MCP integration proven · AI token/cost telemetry
- [ ] Telemetry unified + correlation IDs end-to-end
- [ ] CLI finalized · scaffolding finalized · file-based pages work
- [ ] Public API contract tests · security tests · integration tests
- [ ] Performance baseline not regressed
- [ ] Documentation complete (16 sections) · README rewritten
- [ ] Killer AI application (`examples/ai_saas`) demonstrates full chain
- [ ] Clean install verified
- [ ] No proprietary CSS framework · no React abstractions · no Evolution Engine
- [ ] **Voodoo 1.0 tagged and released** (version bump: 1.0.22 → 1.0.0)
