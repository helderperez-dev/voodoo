"""Regression tests for inline versus durable worker retry semantics."""

from __future__ import annotations

import pytest

from voodoo.primitives.effect import Effect
from voodoo.runtime.scheduling import TaskError, task
from voodoo.runtime.scheduling import workers as worker_queue


@pytest.mark.asyncio
async def test_enqueued_task_persists_decorator_retry_budget(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_enqueue(name, payload, **kwargs):
        captured.update(name=name, payload=payload, **kwargs)

    monkeypatch.setattr(worker_queue, "enqueue", fake_enqueue)
    task_name = "test_durable_retry_budget"

    @task(retries=3, name=task_name, backoff=0.25)
    async def job(payload):
        return payload

    try:
        await job.enqueue("hello")
        assert captured["name"] == task_name
        assert captured["payload"] == "hello"
        assert captured["max_attempts"] == 4
        assert worker_queue._worker_backoff[task_name] == pytest.approx(0.25)
    finally:
        worker_queue._workers.pop(task_name, None)
        worker_queue._worker_backoff.pop(task_name, None)


@pytest.mark.asyncio
async def test_background_worker_performs_one_attempt_per_queue_claim() -> None:
    calls = 0
    task_name = "test_one_attempt_per_claim"

    @task(retries=5, name=task_name, backoff=0.001)
    async def flaky(payload):
        nonlocal calls
        calls += 1
        raise RuntimeError("boom")

    try:
        registered_worker = worker_queue._workers[task_name]
        with pytest.raises(TaskError) as exc_info:
            await registered_worker("payload")

        assert calls == 1
        assert exc_info.value.attempts == 1
    finally:
        worker_queue._workers.pop(task_name, None)
        worker_queue._worker_backoff.pop(task_name, None)


@pytest.mark.asyncio
async def test_inline_task_keeps_in_process_retry_semantics() -> None:
    calls = 0
    task_name = "test_inline_retries"

    @task(retries=2, name=task_name, backoff=0)
    async def flaky_then_ok():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise RuntimeError("retry")
        return "ok"

    try:
        assert await flaky_then_ok() == "ok"
        assert calls == 3
    finally:
        worker_queue._workers.pop(task_name, None)
        worker_queue._worker_backoff.pop(task_name, None)


@pytest.mark.asyncio
async def test_task_error_reason_is_redacted_and_bounded() -> None:
    task_name = "test_redacted_task_error"

    @task(retries=0, name=task_name)
    async def leaking_task():
        raise RuntimeError("authorization=Bearer secret-token")

    try:
        with pytest.raises(TaskError) as exc_info:
            await leaking_task()
        assert "secret-token" not in str(exc_info.value)
        assert "[REDACTED]" in str(exc_info.value)
    finally:
        worker_queue._workers.pop(task_name, None)
        worker_queue._worker_backoff.pop(task_name, None)


@pytest.mark.asyncio
async def test_enqueue_compensation_is_durable_and_idempotent(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeQueue:
        async def enqueue(self, name, payload, **kwargs):
            captured.update(name=name, payload=payload, **kwargs)
            return "queued"

    async def fake_get_queue():
        return FakeQueue()

    monkeypatch.setattr(worker_queue, "_get_queue", fake_get_queue)
    effect = Effect(name="charge_card", reversible=True).configure_compensation(
        "refund_card", payload={"amount": 10}
    )

    result = await worker_queue.enqueue_compensation(effect, reason="timeout")

    assert result == "queued"
    assert captured["name"] == "refund_card"
    assert captured["idempotency_key"] == f"compensate:{effect.id}"
    assert captured["payload"] == {
        "version": 1,
        "effect_id": effect.id,
        "effect_name": "charge_card",
        "effect_payload": {"amount": 10},
        "reason": "timeout",
    }


@pytest.mark.asyncio
async def test_enqueue_compensation_rejects_missing_declaration() -> None:
    with pytest.raises(ValueError, match="no declared compensation"):
        await worker_queue.enqueue_compensation(Effect(name="send_email"))


@pytest.mark.asyncio
async def test_engine_failure_policy_enqueues_successful_effect_compensation(monkeypatch):
    from voodoo.primitives.intent import Intent
    from voodoo.runtime.context import ExecutionContext
    from voodoo.runtime.execution import Execution
    from voodoo.runtime.execution.engine import ExecutionEngine

    queued: list[tuple[str, str]] = []

    async def fake_enqueue(effect, *, reason=None, max_attempts=3):
        queued.append((effect.name, reason or ""))
        return "queued"

    monkeypatch.setattr(worker_queue, "enqueue_compensation", fake_enqueue)
    engine = ExecutionEngine()
    execution = Execution(id="failed-run", trace_id="trace", intent=Intent(name="run"), actor="test")
    effect = Effect(name="charge", reversible=True)
    effect.configure_compensation("refund", trigger="on_failure")
    effect.mark_succeeded()
    execution.add_effect(effect)
    context = ExecutionContext(trace_id="trace", actor="test")

    from voodoo.runtime.errors import ExecutionError

    with pytest.raises(ExecutionError, match="boom"):
        await engine._handle_failure(execution, context, RuntimeError("boom"))
    assert queued == [("charge", "boom")]
