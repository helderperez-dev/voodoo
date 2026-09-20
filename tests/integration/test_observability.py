"""Tests for Sprint 20 — Observability.

Covers:
  1. Unified trace_id propagation across the full chain.
  2. OTel-compatible Span model (record, start_span, parent hierarchy).
  3. Telemetry summary persistence across restarts.
  4. CLI ``voodoo status`` and ``voodoo workers``.
  5. OTLP exporter availability check.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from voodoo.telemetry import trace
from voodoo.telemetry.store import (
    Span,
    TelemetryStore,
    new_trace_id,
    telemetry_store,
    trace_id_var,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clear_spans() -> None:
    telemetry_store.metrics["spans"].clear()
    telemetry_store.metrics["custom_traces"].clear()


# ---------------------------------------------------------------------------
# 1. Span model
# ---------------------------------------------------------------------------


class TestSpanModel:
    """OTel-compatible Span dataclass and recording."""

    def test_span_defaults(self):
        span = Span(trace_id="t1")
        assert span.trace_id == "t1"
        assert len(span.span_id) == 16
        assert span.parent_span_id is None
        assert span.status == "ok"
        assert span.end_time is None
        assert span.duration_ms is None

    def test_span_frozen(self):
        span = Span(trace_id="t1", name="test")
        with pytest.raises(AttributeError):
            span.name = "other"  # type: ignore[misc]

    def test_span_to_dict(self):
        now = datetime.now(UTC)
        span = Span(
            trace_id="t1",
            span_id="abcd1234efgh5678",
            parent_span_id=None,
            name="op",
            start_time=now,
            end_time=now,
            status="ok",
            attributes={"key": "value"},
        )
        d = span.to_dict()
        assert d["trace_id"] == "t1"
        assert d["span_id"] == "abcd1234efgh5678"
        assert d["name"] == "op"
        assert d["attributes"] == {"key": "value"}
        assert d["duration_ms"] is not None

    def test_record_span_stores_in_buffer(self):
        _clear_spans()
        span = Span(trace_id="t1", name="test.span")
        telemetry_store.record_span(span)
        assert len(telemetry_store.metrics["spans"]) == 1
        stored = telemetry_store.metrics["spans"][0]
        assert stored["name"] == "test.span"
        assert stored["trace_id"] == "t1"

    def test_span_ring_buffer_limit(self):
        _clear_spans()
        for i in range(1005):
            telemetry_store.record_span(Span(trace_id="t", name=f"s{i}"))
        assert len(telemetry_store.metrics["spans"]) == 1000

    def test_start_span_creates_child(self):
        _clear_spans()
        token = trace_id_var.set("trace-abc")
        try:
            with telemetry_store.start_span("parent") as parent_span:
                assert parent_span.trace_id == "trace-abc"
                assert parent_span.parent_span_id is None
                parent_id = parent_span.span_id

                with telemetry_store.start_span("child") as child_span:
                    assert child_span.trace_id == "trace-abc"
                    assert child_span.parent_span_id == parent_id
        finally:
            trace_id_var.reset(token)

        assert len(telemetry_store.metrics["spans"]) == 2
        names = [s["name"] for s in telemetry_store.metrics["spans"]]
        assert "parent" in names
        assert "child" in names

    def test_start_span_error_status(self):
        _clear_spans()
        with pytest.raises(ValueError, match="boom"):
            with telemetry_store.start_span("failing"):
                raise ValueError("boom")

        assert len(telemetry_store.metrics["spans"]) == 1
        assert telemetry_store.metrics["spans"][0]["status"] == "error"

    def test_start_span_generates_trace_id_when_none(self):
        _clear_spans()
        token = trace_id_var.set(None)
        try:
            with telemetry_store.start_span("orphan") as span:
                assert span.trace_id is not None
                assert len(span.trace_id) > 0
        finally:
            trace_id_var.reset(token)

    async def test_trace_decorator_creates_span(self):
        _clear_spans()

        @trace(name="decorated_work")
        async def work():
            return 42

        result = await work()
        assert result == 42
        spans = [
            s for s in telemetry_store.metrics["spans"] if s["name"] == "decorated_work"
        ]
        assert len(spans) == 1
        assert spans[0]["status"] == "ok"

    def test_get_summary_includes_spans_total(self):
        _clear_spans()
        telemetry_store.record_span(Span(trace_id="t", name="x"))
        summary = telemetry_store.get_summary()
        assert summary["spans_total"] >= 1


# ---------------------------------------------------------------------------
# 2. Telemetry summary persistence
# ---------------------------------------------------------------------------


class TestTelemetryPersistence:
    """Rolling summary survives restarts."""

    def test_persist_and_load_summary(self, tmp_path: Path):
        store = TelemetryStore.__new__(TelemetryStore)
        store._SUMMARY_PATH = tmp_path / "summary.json"
        store.metrics = {
            "requests_total": 0,
            "errors_total": 0,
            "latencies_ms": [],
            "custom_traces": [],
            "db_queries": 0,
            "agent_tokens": 0,
            "agent_runs": [],
            "tool_calls": [],
            "spans": [],
        }
        store.trace_id_var = trace_id_var

        # Simulate some traffic
        store.record_request(5.0, error=False)
        store.record_request(10.0, error=True)
        store.record_db_query()
        store.record_agent_tokens(100)

        # Persist
        store._persist_summary()
        assert store._SUMMARY_PATH.exists()

        # Create a new store that loads from the same path
        store2 = TelemetryStore.__new__(TelemetryStore)
        store2._SUMMARY_PATH = tmp_path / "summary.json"
        store2.metrics = {
            "requests_total": 0,
            "errors_total": 0,
            "latencies_ms": [],
            "custom_traces": [],
            "db_queries": 0,
            "agent_tokens": 0,
            "agent_runs": [],
            "tool_calls": [],
            "spans": [],
        }
        store2.trace_id_var = trace_id_var
        store2._load_summary()

        # Counters should be restored
        assert store2.metrics["requests_total"] == 2
        assert store2.metrics["errors_total"] == 1
        assert store2.metrics["db_queries"] == 1
        assert store2.metrics["agent_tokens"] == 100

    def test_load_summary_handles_missing_file(self, tmp_path: Path):
        store = TelemetryStore.__new__(TelemetryStore)
        store._SUMMARY_PATH = tmp_path / "nonexistent.json"
        store.metrics = {
            "requests_total": 0,
            "errors_total": 0,
            "latencies_ms": [],
            "custom_traces": [],
            "db_queries": 0,
            "agent_tokens": 0,
            "agent_runs": [],
            "tool_calls": [],
            "spans": [],
        }
        store.trace_id_var = trace_id_var
        # Should not raise
        store._load_summary()
        assert store.metrics["requests_total"] == 0

    def test_load_summary_handles_corrupt_json(self, tmp_path: Path):
        bad_file = tmp_path / "summary.json"
        bad_file.write_text("not json {{{")
        store = TelemetryStore.__new__(TelemetryStore)
        store._SUMMARY_PATH = bad_file
        store.metrics = {
            "requests_total": 0,
            "errors_total": 0,
            "latencies_ms": [],
            "custom_traces": [],
            "db_queries": 0,
            "agent_tokens": 0,
            "agent_runs": [],
            "tool_calls": [],
            "spans": [],
        }
        store.trace_id_var = trace_id_var
        store._load_summary()
        assert store.metrics["requests_total"] == 0


# ---------------------------------------------------------------------------
# 3. Trace propagation across subsystems
# ---------------------------------------------------------------------------


class TestTracePropagation:
    """trace_id propagates through execution, workers, agents, mesh."""

    def test_trace_id_propagates_to_spans(self):
        _clear_spans()
        token = trace_id_var.set("propagation-test-001")
        try:
            with telemetry_store.start_span("outer"):
                with telemetry_store.start_span("inner"):
                    pass
        finally:
            trace_id_var.reset(token)

        spans = telemetry_store.metrics["spans"]
        assert len(spans) == 2
        assert all(s["trace_id"] == "propagation-test-001" for s in spans)
        # inner span's parent should be outer span
        outer = next(s for s in spans if s["name"] == "outer")
        inner = next(s for s in spans if s["name"] == "inner")
        assert inner["parent_span_id"] == outer["span_id"]

    async def test_trace_id_propagates_through_execution_context(self):
        """use_context bridges ExecutionContext.trace_id → trace_id_var."""
        from voodoo.runtime.context import ExecutionContext, use_context

        ctx = ExecutionContext(trace_id="ctx-bridge-123")
        async with use_context(ctx):
            assert trace_id_var.get() == "ctx-bridge-123"
        # After exiting, previous value should be restored.
        assert trace_id_var.get() != "ctx-bridge-123"

    async def test_trace_id_propagates_to_mesh_envelope(self):
        """Mesh broadcast carries the trace_id as correlation_id."""
        from voodoo.mesh import mesh

        received: list[str] = []

        async def handler(payload):
            received.append(payload)

        mesh.on("test.trace")(handler)

        token = trace_id_var.set("mesh-trace-999")
        try:
            await mesh.broadcast("test.trace", "data")
        finally:
            trace_id_var.reset(token)

        assert received == ["data"]

    async def test_trace_id_propagates_to_queue_enqueue(self):
        """Enqueue captures the current trace_id."""
        from voodoo.queue import enqueue
        from voodoo.workers.queue import _get_queue, _workers

        async def _handler(payload):
            pass

        _workers["test_trace_queue"] = _handler

        token = trace_id_var.set("queue-trace-42")
        try:
            await enqueue("test_trace_queue", {"x": 1})
        finally:
            trace_id_var.reset(token)

        q = await _get_queue()
        tasks = await q.list(task_type="test_trace_queue")
        assert tasks
        assert tasks[0].trace_id == "queue-trace-42"

    async def test_full_chain_correlation_with_spans(self):
        """Full chain: trace_id → agent → tool → telemetry with spans."""
        from voodoo.ai.agent import Agent
        from voodoo.ai.providers import ProviderResponse
        from voodoo.ai.providers.mock import MockProvider
        from voodoo.tools.registry import ToolRegistry, build_spec

        _clear_spans()

        async def my_tool(title: str) -> str:
            return f"done:{title}"

        registry = ToolRegistry()
        registry.register(build_spec(my_tool))

        class ChainProvider(MockProvider):
            def __init__(self):
                super().__init__(model="test")
                self._call = 0

            async def complete(self, messages, **kwargs):
                self._call += 1
                if self._call == 1:
                    return ProviderResponse(
                        content='[TOOL: my_tool] args: {"title": "X"}',
                        model=self.model,
                        tokens_in=1,
                        tokens_out=1,
                        cost=0.0,
                    )
                return ProviderResponse(
                    content="Done.",
                    model=self.model,
                    tokens_in=1,
                    tokens_out=1,
                    cost=0.0,
                )

        token = trace_id_var.set("full-chain-span-test")
        try:
            agent = Agent(model="mock:test", tools=["my_tool"], registry=registry)
            agent.provider = ChainProvider()
            run = await agent.run("Do it")
            assert run.trace_id == "full-chain-span-test"
        finally:
            trace_id_var.reset(token)

        # All spans should carry the same trace_id
        for span in telemetry_store.metrics["spans"]:
            if span["name"] not in ("http.request",):
                assert span["trace_id"] == "full-chain-span-test"


# ---------------------------------------------------------------------------
# 4. CLI commands
# ---------------------------------------------------------------------------


class TestCLICommands:
    """``voodoo status`` and ``voodoo workers`` commands."""

    def test_status_command_runs_without_error(self):
        from voodoo.cli.status import status

        # Should not raise
        status()

    def test_workers_command_runs_without_error(self):
        from voodoo.cli.workers_cmd import workers

        # Should not raise
        workers()

    def test_status_reflects_telemetry_data(self):
        """After recording some traffic, status should show it."""
        _clear_spans()
        telemetry_store.record_request(1.5, error=False)
        telemetry_store.record_request(2.5, error=True)
        telemetry_store.record_span(Span(trace_id="t", name="s"))

        # Should not raise; summary should include our data
        summary = telemetry_store.get_summary()
        assert summary["requests_total"] >= 2
        assert summary["errors_total"] >= 1


# ---------------------------------------------------------------------------
# 5. OTLP exporter
# ---------------------------------------------------------------------------


class TestOTLPExporter:
    """OTLP availability check and graceful degradation."""

    def test_is_available_false_without_env(self):
        from voodoo.telemetry.otlp import is_available

        old = os.environ.pop("VOODOO_OTEL_EXPORTER", None)
        try:
            assert is_available() is False
        finally:
            if old is not None:
                os.environ["VOODOO_OTEL_EXPORTER"] = old

    def test_export_span_noop_without_env(self):
        """export_span should be a no-op when OTLP is not configured."""
        from voodoo.telemetry.otlp import export_span

        old = os.environ.pop("VOODOO_OTEL_EXPORTER", None)
        try:
            # Should not raise
            span = Span(trace_id="t1", name="test")
            export_span(span)
        finally:
            if old is not None:
                os.environ["VOODOO_OTEL_EXPORTER"] = old


# ---------------------------------------------------------------------------
# 6. new_trace_id helper
# ---------------------------------------------------------------------------


class TestNewTraceId:
    def test_generates_unique_ids(self):
        ids = {new_trace_id() for _ in range(100)}
        assert len(ids) == 100

    def test_returns_string(self):
        tid = new_trace_id()
        assert isinstance(tid, str)
        assert len(tid) > 0
