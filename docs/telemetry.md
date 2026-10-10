# Telemetry

## Store operational metrics

Adapters report semantic Store operations through
`telemetry_store.record_store_operation(...)`. The bounded metric contract
covers commit latency, recovery, object I/O, compaction, lock wait, queue lag,
errors, and bytes without recording keys or payloads. `/voodoo/metrics` exposes
the aggregate counters and a short redacted recent-operation window.

## What it is

Voodoo has built-in observability: correlation IDs, request latency tracking, agent token/cost accounting, tool call metrics, and custom trace spans. All telemetry is collected in-process by the `TelemetryStore` and exposed via a metrics endpoint.

## Minimal example

```python
from voodoo.observability import trace


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

For Prometheus-compatible scrapers, use the bounded numeric exposition:

```bash
curl http://localhost:8000/voodoo/metrics/prometheus
```

The endpoint emits only numeric aggregate metrics (no paths, keys, payloads,
or recent trace records) and uses stable `voodoo_` names. Protect metrics
routes with the same network/authentication boundary as other operational
endpoints when exposing them beyond localhost.

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

1. `TelemetryMiddleware` accepts safe `X-Trace-ID` and `X-Correlation-ID` headers or generates IDs, then binds them via `ContextVar`s.
2. Response headers echo both IDs, and structured request metrics include method, path, status, latency, and IDs.
3. The IDs propagate through agents, tool calls, queue items, and mesh events.
4. `TelemetryStore` collects metrics in memory (ring buffers prevent unbounded growth).
5. The `/voodoo/metrics` endpoint exposes a summary and
   `/voodoo/metrics/prometheus` exposes scrapeable numeric aggregates.
   Exception messages and tracebacks pass through the centralized redaction
   guard before logging.

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
- Accepts validated incoming IDs or generates a UUID trace_id per request
- Emits `X-Trace-ID` and `X-Correlation-ID` response headers
- Records structured request latency, status, error, and correlation metadata
- Resets the trace_id after the request completes
- Logs request completion with the trace_id after redaction

## API reference

- `trace(name=None)` — decorator for tracing function blocks. Now also creates an OTel-compatible span with parent hierarchy.
- `telemetry_store` — global `TelemetryStore` singleton.
- `trace_id_var` — `ContextVar` holding the current trace ID.
- `correlation_id_var` — `ContextVar` holding the current request correlation ID.
- `new_trace_id()` — generate a new UUID4 hex trace ID.
- `Span` — frozen dataclass: `trace_id`, `span_id`, `parent_span_id`, `name`, `start_time`, `end_time`, `status`, `attributes`. Has `duration_ms` property and `to_dict()`.
- `start_span(name, attributes=None)` — async context manager creating child spans with automatic parent tracking.
- `TelemetryStore.record_request(latency_ms, error=False, ...)` — record an HTTP request and optional structured correlation metadata.
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
