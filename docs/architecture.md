# Architecture

## What it is

Voodoo is an AI-native application framework for Python. It combines reactive UIs, APIs, agents, background workers, realtime systems, MCP tools, and data-driven applications in one Python runtime.

## Design principles

1. **AI-native by design** — Agents, tools, and MCP are first-class primitives, not add-ons.
2. **Agents as application primitives** — `Agent()` sits next to `Button()` and `Card()`.
3. **One tool, many consumers** — `@tool` serves Python, agents, MCP, and mesh simultaneously.
4. **Observability everywhere** — Correlation IDs + telemetry as the sensory system.
5. **Zero-config runtime** — `voodoo new` → `voodoo dev` → working app.

## System layers

```
┌─────────────────────────────────────────────┐
│                  UI Layer                    │
│  Components (Div, Card, Button, ...)         │
│  Reactive State (State, StateRenderer)       │
│  WebSocket Transport (ws_manager, events)    │
├─────────────────────────────────────────────┤
│                AI Layer                      │
│  Agent (run, stream, tool calling)           │
│  LLM Providers (OpenAI, Anthropic, Mock)     │
│  Tool Registry (@tool, ToolSpec)            │
├─────────────────────────────────────────────┤
│              Realtime Layer                  │
│  Voodoo Mesh (events, expose, WS nodes)      │
│  MCP Server (SSE, tools/list, tools/call)     │
├─────────────────────────────────────────────┤
│              Worker Layer                     │
│  @task (retries, timeout, telemetry)         │
│  Async Queue (enqueue, start_workers)        │
├─────────────────────────────────────────────┤
│               Data Layer                     │
│  Model / BaseModel (async CRUD)              │
│  SQLite (aiosqlite) with RLS policies        │
├─────────────────────────────────────────────┤
│             Infrastructure                    │
│  Auth (JWT, API keys, RBAC)                  │
│  Security (CORS, CSRF, rate limit, headers)  │
│  Telemetry (trace_id, metrics, spans)         │
│  Config (env vars, YAML)                    │
└─────────────────────────────────────────────┘
```

## Request lifecycle

1. HTTP request enters the ASGI app
2. Middleware stack processes: SecurityHeaders → CORS → RateLimit → CSRF → Telemetry → I18n → Auth
3. TelemetryMiddleware assigns a `trace_id` (UUID)
4. AuthMiddleware resolves user from token/API key/cookie
5. Routing dispatches to page handler or API endpoint
6. Handler runs, renders component tree to HTML
7. Response flows back through middleware

## Reactive loop

1. Browser sends event over WebSocket (`{"type": "event", "event": "increment", ...}`)
2. Event handler mutates `State` cell
3. `StateRenderer` re-renders the page function
4. DOM patch broadcast to all WebSocket clients
5. Client swaps `outerHTML` of the target element

## Agent execution loop

```
prompt → provider → tool call? → execute tool → feed result back → final answer
```

1. Agent builds messages from prompt + system_prompt + context
2. Provider (OpenAI/Anthropic/Mock) processes the messages
3. If the response contains a tool-call marker, the tool is invoked from the registry
4. The tool result is appended to messages and the loop continues
5. When no more tool calls are requested, the final answer is returned

## Correlation ID propagation

Every request gets a `trace_id` (UUID) via `ContextVar`. This ID propagates through:
- HTTP request telemetry
- Agent runs (recorded in `AgentRun.trace_id`)
- Tool call telemetry
- Queue items (stored in envelope, restored in worker)
- Mesh event envelopes (`correlation_id` field)

## Key design decisions

- **Starlette as ASGI base** — not reinventing the wheel; Starlette handles routing, middleware, responses.
- **SQLite default** — zero-config persistence; PostgreSQL is a future optional extra.
- **Single-process queue** — asyncio.Queue today; distributed backend (Redis) is a seam.
- **Lazy provider imports** — `voodoo[ai]` installs SDKs, but they're imported only when a provider is used.
