# Repository migration map

This document records ownership decisions discovered during the repository
architecture audit. A directory is moved only when its target owner is clearer
than its current owner.

| Current namespace | Decision | Canonical owner / rationale |
| --- | --- | --- |
| `core/` | keep | application facade and framework lifecycle |
| `runtime/` | keep, group internally | canonical adaptive runtime |
| `primitives/` | keep | stable semantic contracts/value objects |
| `world/` | keep | entities, observations and operational state |
| `protocol/` | keep | transport-neutral protocol contracts |
| `ui/` | keep | reactive presentation |
| `data/` | keep | developer-facing model/data API |
| `storage/` | keep for this release | provider implementations; do not confuse with application `data` or native Store |
| `auth/` | keep | application authentication surface |
| `security/` | keep | HTTP/runtime security mechanics distinct from identity/auth |
| `ai/` | keep semantic domain | provider contracts, model routing, tools and mock provider remain AI-owned; vendor SDK implementations live in `integrations/ai` |
| `agents/` | keep | durable participant identity/registry is broader than AI |
| `tools/` | compatibility only | canonical tool implementation is `ai/tools` |
| `edge/` | keep | device/physical-world boundary |
| `mesh/` | migrate deliberately | legacy distributed transport concepts overlap Runtime distributed fabric; requires dependency audit |
| `workers/` | migrate deliberately | task/queue facade overlaps Runtime execution but remains public compatibility surface |
| `memory/` | keep pending model review | semantic memory is used by compute/agents and is not merely AI-provider code |
| `telemetry/` | compatibility only | canonical native implementation is `observability/`; OTLP integration is `integrations/otel.py`; legacy module aliases preserve identity |
| `adapters/` | keep | provider capability negotiation and UI style adapters are framework abstractions, not external integrations |
| `routing/` | keep compatibility boundary | routing implementation supports Core/App facade |
| `mcp/` | compatibility only | canonical MCP server/client implementation is `integrations/mcp`; legacy module aliases preserve public imports |
| package-root facades | freeze | no new root modules; existing paths are compatibility surface |

## Integration ownership

External dependencies are classified by semantic ownership, not merely by whether a third-party library is imported.

- `integrations/ai/` owns SDK-backed model providers (OpenAI, Anthropic, Gemini and Ollama); `ai/providers/` retains contracts, routing/registry, mock behavior and compatibility aliases.
- `integrations/mcp/` owns MCP interoperability; `mcp/` is the compatibility surface.
- `integrations/otel.py` owns optional OpenTelemetry export; native metrics/tracing state remains in `observability/`.
- Redis cache/queue and S3 object storage remain in `storage/` because they implement Storage contracts. Vendor usage alone does not make a module an application integration.
- `adapters/` remains framework-owned: capability negotiation and UI style adaptation are semantic framework mechanisms.

## Runtime grouping candidates

The current flat runtime package is the highest-value physical reorganization.
The target groups are implementation ownership boundaries, while
`voodoo.runtime` remains the public facade.

```text
runtime/
├── execution/
├── reconciliation/
├── scheduling/
├── agency/
├── distributed/
└── inspection/
```

Before moving a module into a group:

1. inventory internal and external imports;
2. identify public imports covered by API/contract tests;
3. add/reuse a compatibility export at `voodoo.runtime`;
4. move one cohesive cluster;
5. run Python 3.12/3.13, Ruff, Mypy and Store-first gates.

## Suppression debt

The audit found legacy `# noqa` suppressions in source. Repository Architecture
tracks an explicit transitional baseline: no new suppression is allowed and the
baseline may only shrink. RA6 requires the baseline to reach zero. Mechanical
suppressions are removed first; complexity suppressions are removed by
refactoring the underlying function rather than disabling lint rules.

## Non-goals

- turning Voodoo into a JavaScript-style monorepo for appearance;
- splitting every domain into separately versioned Python distributions;
- renaming namespaces without semantic benefit;
- changing runtime behavior while moving files;
- hiding circular dependencies with lazy imports solely to make a move pass.
