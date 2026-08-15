# Voodoo Baseline — Phase 0 Audit

> Internal ground truth recorded before any 1.0 implementation work.
> Re-run `just bench` and `just test` after each sprint; regressions against these numbers block release.

**Recorded:** 2026-08-15 · version `1.0.22` · Python 3.12 · macOS (Apple Silicon)

---

## 1. Test Baseline

| Metric | Value |
|---|---|
| Tests | **98 passed / 0 failed** |
| Duration | ~8.0 s |
| Warnings | 3 (starlette TestClient cookie deprecation) |

Suites present: auth, cli, components, data, i18n, queue, security, seo, theme, websocket.
Suites missing: agent, mesh, mcp, telemetry, routing/core, **public API contract**, integration, performance.

## 2. Performance Baseline (`just bench`)

| Metric | Baseline (median) | 1.0 target |
|---|---|---|
| `import voodoo` (fresh interpreter) | 110.6 ms | startup < 500 ms total |
| `create_app()` (warm) | 0.04 ms | — |
| `render_page()` small tree (SSR) | 0.01 ms | fast, no client-blocked render |
| `GET /openapi.json` (full middleware stack) | 1.02 ms | ≈ Starlette + ε |

## 3. Implementation Map (current flat layout)

| Subsystem | File (LOC) | State |
|---|---|---|
| App factory / WS / render | `core.py` (535) | Working; `create_app` + file-router + middleware wiring; debug hardcoded `True`; duplicated `(SEO, Component)` unpacking |
| Components | `components.py` (778) | Working; Tailwind strings embedded; **no HTML escaping**; two competing class conventions (CSS-var arbitrary values vs unresolved `bg-surface` names in auth forms); `Table.render` duplicates attribute builder |
| Auth | `auth.py` (836) | Feature-complete (PBKDF2, JWT, API keys, RBAC guards, middleware); needs hardening + surface reduction |
| Security | `security.py` (328) | Headers/CORS/CSRF/rate-limit with tests; CSRF off by default |
| API router | `api.py` (203) | DI + OpenAPI; **no `patch`**; version hardcoded `1.0.0`; securitySchemes declared but never attached |
| Data | `data.py` (219) | `BaseModel` + hooks + RLS (raw SQL WHERE); only `find_all`/`insert`/`update`; no delete/get/filters; async hooks fire-and-forget |
| Mesh | `mesh.py` (212) | expose/on/broadcast + WS; JSON-RPC-ish; no event envelope; `expose` auto-bridges to MCP; `websockets` legacy `.closed` compat bug |
| MCP | `mcp.py` (235) | SSE server + HTTP client (protocol mismatch); tools/list always empty schema; import-time route registration |
| Agent | `agent.py` (42) | **Simulated stub** — no provider, no tools, no streaming |
| Queue | `queue.py` (71) | In-memory asyncio queues, trace-id propagation; no retries/timeouts/persistence |
| Telemetry | `telemetry.py` (178) | trace decorator + in-memory store + middleware; no correlation propagation beyond queue |
| Theme | `theme.py` (122) | CSS vars + Tailwind config; `mode="system"` meaningless; `voodoo-*` colors unused by components |
| Config | `config.py` (158) | env + YAML merge (YAML silently wins); no `debug` flag; no `DATABASE_URL` |
| SEO | `seo.py` | Meta/OG/Twitter/GEO/JSON-LD + sitemap/robots — well tested |
| i18n / storage / status | flat modules | Working; untested (no test files) |
| CLI | `cli.py` (1,140) | new/dev/routes/doctor/auth/generate; oversized; scaffold docs advertise nonexistent `voodoo.navigate()` |
| Browser runtime | `client.js` (55) | WS connect/reconnect(1s fixed)/sendEvent/patch/append; no navigate, no backoff |

## 4. Public API Catalog (P0.4)

`voodoo.__all__` currently pins **123 names** (target: ~40). Breakdown:
components 34 + semantic 13 + auth components 4 + auth/security 40 + data 4 + infra 10 + config 4 + theme 3 + i18n 3 + mesh 1 + seo 5 + core 3.

Reduction strategy (Sprint 1): keep ~41 names; everything else resolves via PEP 562 `__getattr__` with `DeprecationWarning`, sourced from its defining submodule. `from voodoo import Div` used by dynamic test pages stays valid (Div remains exported).

## 5. Duplicates, Placeholders, Dead Code (P0.3)

- `Agent` — simulated token stream (replace in S6/S7)
- `MCPClient` — speaks plain HTTP JSON-RPC; incompatible with bundled SSE server
- `openai` — hard dependency, never imported
- `A.__init__` className reassignment — no-op
- `find_all` vestigial `params` list
- `(SEO, Component)` tuple unpacking — duplicated in `render_page` + route handler (dedupe in S1)
- `Table.render` — re-implements base attribute builder (dedupe in S2)
- Auth-form classes reference Tailwind names with no matching config (`bg-surface`, `primary-hover`, `text-danger`)
- Sync/async dispatch (`iscoroutinefunction`) repeated in 5 modules (extract shared helper later)
- Import-time global mutations: `mcp` mounts `/mcp/*`, `telemetry` mounts `/voodoo/metrics` on shared `api` singleton
- `pyproject.toml` packages `app*` dirs into wheels (packaging bug — fix in S1)
- Security-relevant: no HTML escaping in any render path; `Starlette(debug=True)` hardcoded; RLS policies return raw SQL strings; single shared aiosqlite connection

## 6. Golden Behavior (P0.6)

Pinned by existing suites (do not regress):
- Exact-string component renders — `tests/test_components.py`
- WS event protocol (`patch`/`append` messages) — `tests/test_websocket.py`
- SEO meta/JSON-LD/sitemap/robots output — `tests/test_seo.py`
- Auth flows (JWT/API-key/middleware precedence/RBAC) — `tests/test_auth.py`
- Queue processing + trace-id restore — `tests/test_queue.py`

## 7. Gap Confirmation

The §4.2 gap table in `IMPLEMENTATION_PLAN.md` (G1–G20) was verified against this audit; no corrections needed. Sprint sequence lives in the sprint plan (S0–S9).
