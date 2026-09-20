# Repository migration map

The repository architecture migration (RA1–RA6) completed on 2026-09-20 and was
merged by PR #70. This file records the resulting ownership decisions and the
compatibility surfaces intentionally retained.

| Namespace | Status | Canonical owner / rationale |
| --- | --- | --- |
| `core/` | canonical | application facade and framework lifecycle |
| `runtime/` | canonical | adaptive runtime; internally grouped by execution, reconciliation, scheduling, agency, distributed and inspection |
| `primitives/` | canonical | stable semantic contracts/value objects |
| `world/` | canonical | entities, observations and operational state |
| `protocol/` | canonical | transport-neutral protocol contracts |
| `ui/` | canonical | reactive presentation |
| `data/` | canonical | developer-facing model/data API |
| `storage/` | canonical for storage contracts | provider implementations; distinct from application data and native Voodoo Store |
| `auth/` | canonical | application authentication |
| `security/` | canonical | HTTP/runtime security mechanics |
| `ai/` | canonical semantic domain | model/provider contracts, routing, agents and tools |
| `integrations/ai/` | canonical vendor implementations | SDK-backed OpenAI, Anthropic, Gemini and Ollama providers |
| `agents/` | retained | durable participant identity/registry is broader than vendor AI |
| `tools/` | compatibility | canonical tools live in `ai/tools` |
| `edge/` | canonical | device/physical-world boundary |
| `mesh/` | compatibility/application surface | distributed authority lives in `runtime/distributed`; event bus/client semantics remain mesh-facing |
| `workers/` | compatibility/application surface | durable orchestration lives in `runtime/scheduling` |
| `memory/` | retained | semantic memory used across compute/agents |
| `observability/` | canonical | native telemetry, middleware and inspection state |
| `telemetry/` | compatibility | aliases canonical observability; OTLP export lives in `integrations/otel.py` |
| `adapters/` | retained | framework capability/style abstractions |
| `routing/` | retained boundary | routing implementation supporting Core/App |
| `integrations/mcp/` | canonical integration | MCP server/client implementation |
| `mcp/` | compatibility | preserves public MCP imports |
| package-root facades | frozen | existing paths may preserve compatibility; new paths require API decision |

## Runtime ownership

```text
runtime/
├── execution/       Execution + ExecutionEngine authority
├── reconciliation/  deterministic reconciliation
├── scheduling/      work, workers, dispatch and handoff
├── agency/          goals and adaptive behavior
├── distributed/     fabric, membership and distributed participation
└── inspection/      lineage and runtime inspection
```

Old module paths remain facades where compatibility requires them. New
implementation belongs in the canonical owner, never in the facade.

## Integration ownership

Vendor usage does not automatically mean `integrations/`. The rule is semantic:

- vendor model SDK implementations → `integrations/ai/`;
- MCP interoperability → `integrations/mcp/`;
- OpenTelemetry export → `integrations/otel.py`;
- Redis/S3 implementations remain `storage/` because they implement Storage
  contracts;
- framework-owned capability and style adapters remain `adapters/`.

## Migration result

RA1–RA6 reached 100%. The final architecture head passed Python 3.12, Python
3.13, Ruff/format, Mypy, Store-first installation, architecture invariants,
CodeQL, and the same gates again after merge to `main`.

The migration baseline for source `# noqa` suppressions is now zero. It is an
invariant, not a transitional allowance.

See `docs/architecture/governance.md` for rules governing future changes.
