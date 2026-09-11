"""Regression tests for inline versus durable worker retry semantics."""

from __future__ import annotations

import pytest

from voodoo.workers import TaskError, task
from voodoo.workers import queue as worker_queue


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
