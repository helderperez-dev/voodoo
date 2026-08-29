# Telemetry

## What it is

Voodoo has built-in observability: correlation IDs, request latency tracking, agent token/cost accounting, tool call metrics, and custom trace spans. All telemetry is collected in-process by the `TelemetryStore` and exposed via a metrics endpoint.

## Minimal example

```python
from voodoo import trace


@trace("data_pipeline")
async def run_pipeline(data):
    # ... heavy work ...
    pass
```

## Common usage

### Tracing a function

```python
@trace
async def fetch_stats():
    return await db.query("SELECT count(*) FROM users")
```

### Accessing the telemetry store

```python
from voodoo.telemetry import telemetry_store

summary = telemetry_store.get_summary()
print(summary["requests_total"])
print(summary["agent_tokens_in"])
print(summary["tool_calls_total"])
```

### Metrics endpoint

```bash
curl http://localhost:8000/voodoo/metrics
```

Returns:
```json
{
  "requests_total": 42,
  "errors_total": 0,
  "average_latency_ms": 2.5,
  "db_queries": 15,
  "agent_tokens_in": 1200,
  "agent_tokens_out": 800,
  "agent_cost": 0.003,
  "tool_calls_total": 5,
  "tool_errors": 0
}
```

## How it works

1. `TelemetryMiddleware` assigns a unique `trace_id` (UUID) to every HTTP/WebSocket request via a `ContextVar`.
2. The `trace_id` propagates through agents, tool calls, queue items, and mesh events.
3. `TelemetryStore` collects metrics in memory (ring buffers prevent unbounded growth).
4. The `/voodoo/metrics` endpoint exposes a summary.

## Advanced

### Correlation ID propagation

```python
from voodoo.telemetry import trace_id_var

trace_id = trace_id_var.get()  # current trace ID
token = trace_id_var.set("custom-id")
try:
    # ... work ...
finally:
    trace_id_var.reset(token)
```

### Agent run records

```python
telemetry_store.metrics["agent_runs"]  # list of run dicts
telemetry_store.metrics["tool_calls"]  # list of tool call dicts
```

### Custom traces

```python
telemetry_store.record_trace("my_operation", latency_ms=42.5, error=False)
```

### TelemetryMiddleware

The middleware is auto-installed. It:
- Generates a UUID trace_id per request
- Records request latency and error status
- Resets the trace_id after the request completes
- Logs request completion with the trace_id

## API reference

- `trace(name=None)` — decorator for tracing function blocks. Now also creates an OTel-compatible span with parent hierarchy.
- `telemetry_store` — global `TelemetryStore` singleton.
- `trace_id_var` — `ContextVar` holding the current trace ID.
- `new_trace_id()` — generate a new UUID4 hex trace ID.
- `Span` — frozen dataclass: `trace_id`, `span_id`, `parent_span_id`, `name`, `start_time`, `end_time`, `status`, `attributes`. Has `duration_ms` property and `to_dict()`.
- `start_span(name, attributes=None)` — async context manager creating child spans with automatic parent tracking.
- `TelemetryStore.record_request(latency_ms, error=False)` — record an HTTP request.
- `TelemetryStore.record_trace(name, latency_ms, error=False)` — record a custom trace.
- `TelemetryStore.record_span(span)` — store a Span in the ring buffer (max 1000) and forward to OTLP exporter if configured.
- `TelemetryStore.record_agent_run(run_record)` — record an agent run.
- `TelemetryStore.record_tool_call(tool_name, latency_ms, error=False)` — record a tool call.
- `TelemetryStore.get_summary() -> dict` — summary of all metrics including `spans_total`.

## Span model (Sprint 20)

The `Span` dataclass is OTel-compatible and tracks hierarchical execution:

```python
from voodoo.telemetry import Span, start_span, telemetry_store

# Manual span creation
span = Span(trace_id="abc123", name="db.query", attributes={"table": "users"})
telemetry_store.record_span(span)

# Context manager with automatic parent tracking
async with start_span("outer") as outer:
    async with start_span("inner") as inner:
        # inner.parent_span_id == outer.span_id
        pass
```

Spans are stored in an in-memory ring buffer (max 1000). The `trace()` decorator now automatically creates spans alongside trace records.

## OTLP export (Sprint 20)

Optional OpenTelemetry export is available behind the `[otel]` extra:

```bash
pip install voodoo[otel]
```

Enable by setting the `VOODOO_OTEL_EXPORTER` environment variable:

```bash
export VOODOO_OTEL_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317  # default
```

When enabled, every `record_span()` call forwards the span to the OTLP endpoint via a lazy-initialized `TracerProvider` with `BatchSpanProcessor`. If the SDK is not installed or the env var is unset, export is silently skipped.

## Telemetry persistence (Sprint 20)

Rolling counters are persisted to `.voodoo/telemetry_summary.json` every 50 requests and restored on startup:

```json
{
  "requests_total": 150,
  "errors_total": 3,
  "db_queries": 420,
  "agent_tokens": 15000
}
```

This is best-effort (no new dependencies) and ensures `voodoo status` shows meaningful data after a restart.

## CLI commands (Sprint 20)

### `voodoo status`

Displays a runtime health overview:

```bash
voodoo status
```

Shows: requests total, errors, error rate, avg latency, DB queries, agent runs, tokens in/out, cost, tool calls/errors, spans recorded, OTLP export status.

### `voodoo workers`

Shows registered workers and queue state:

```bash
voodoo workers
```

Displays: registered worker names, queue depth, running worker task count.

### `voodoo doctor` (upgraded)

Now includes queue depth, registered workers, scheduler DB health, and OTLP exporter availability checks.
