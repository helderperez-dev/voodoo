# Sprint 6 — Tools & Providers

> Implementation tracking for S6. Derived from IMPLEMENTATION_PLAN.md §4.1–4.2.
> **Status**: Planned

---

## Goal

Build the Tool Registry (`@tool` → `ToolSpec`) and the LLM Provider
abstraction (`LLMProvider` interface with openai/anthropic/gemini/ollama).
These are the foundation for the Agent sprint.

---

## Workstreams

### S6-1: Tool Registry (G5) — build FIRST
- [ ] `@tool` decorator → `ToolSpec` (name, description, schemas from typing,
      permissions, source metadata, stable string identity)
- [ ] `ToolRegistry` single source of truth
- [ ] Consumers: Agent (S7), MCP (S7), CLI, docs, telemetry
- [ ] Permission metadata extension point (`permissions=["leads:read"]`)
- [ ] **File**: `voodoo/tools/__init__.py` (new), `voodoo/tools/registry.py` (new)

### S6-2: Provider abstraction (G6)
- [ ] `LLMProvider` interface: `complete`, `stream` (normalized events),
      token/cost accounting
- [ ] Providers: `openai` (existing dep), `anthropic`, `gemini`, `ollama`
- [ ] **Optional extras**, lazy imports, provider not installed →
      actionable `ConfigurationError`
- [ ] `model="provider:model"` resolution
- [ ] **File**: `voodoo/ai/providers/__init__.py` (new), per-provider modules

### S6-3: Exports & contract
- [ ] Export `tool`, `ToolSpec`, `ToolRegistry`, `LLMProvider` from `voodoo`
- [ ] Packaging extras: `voodoo[ai]` (all providers)
- [ ] Update `__all__` and contract test
- [ ] **Files**: `voodoo/__init__.py`, `pyproject.toml`, `tests/test_contract_api.py`

### S6-4: Tests
- [ ] `tests/test_tools.py`: @tool registration, ToolSpec, permissions, registry
- [ ] `tests/test_providers.py`: mock provider, complete/stream, token accounting
- [ ] `model="provider:model"` resolution tests
- [ ] Full suite green; ruff clean; commit

---

## File Changes

| File | Action | Description |
|---|---|---|
| `voodoo/tools/__init__.py` | NEW | @tool decorator, ToolSpec, ToolRegistry |
| `voodoo/tools/registry.py` | NEW | Registry implementation |
| `voodoo/ai/__init__.py` | NEW | AI package init |
| `voodoo/ai/providers/__init__.py` | NEW | LLMProvider interface |
| `voodoo/ai/providers/openai.py` | NEW | OpenAI provider |
| `voodoo/ai/providers/anthropic.py` | NEW | Anthropic provider |
| `voodoo/ai/providers/gemini.py` | NEW | Gemini provider |
| `voodoo/ai/providers/ollama.py` | NEW | Ollama provider |
| `voodoo/ai/providers/mock.py` | NEW | Deterministic mock for CI |
| `voodoo/__init__.py` | MODIFY | Export tool, providers |
| `pyproject.toml` | MODIFY | Optional extras |
| `tests/test_tools.py` | NEW | Tool registry tests |
| `tests/test_providers.py` | NEW | Provider tests |

---

## Exit Criteria

- [ ] `@tool` produces a `ToolSpec` with schemas from typing
- [ ] `ToolRegistry` is the single source of truth for tools
- [ ] `LLMProvider` interface with `complete`, `stream`, token/cost
- [ ] `model="openai:gpt-4"` resolves correctly
- [ ] Missing provider → actionable `ConfigurationError`
- [ ] Mock provider works for CI (no network)
- [ ] Full suite green; ruff clean; committed (no version bump)
