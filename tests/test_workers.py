import asyncio

import pytest

from voodoo.mesh import mesh
from voodoo.telemetry import telemetry_store
from voodoo.workers import TaskError, task


def _spans_for(name: str) -> list[dict]:
    return [t for t in telemetry_store.metrics["custom_traces"] if t["name"] == name]


@pytest.mark.asyncio
async def test_task_runs_and_records_telemetry_span():
    telemetry_store.metrics["custom_traces"].clear()

    @task
    async def add():
        return 42

    result = await add()
    assert result == 42

    spans = _spans_for("task:add")
    assert len(spans) == 1
    assert spans[0]["error"] is False


@pytest.mark.asyncio
async def test_task_retries_then_succeeds():
    attempts: list[int] = []

    @task(retries=3, backoff=0.001)
    async def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise RuntimeError("boom")
        return "ok"

    result = await flaky()
    assert result == "ok"
    assert len(attempts) == 3


@pytest.mark.asyncio
async def test_task_exhausts_retries_raises_task_error():
    @task(retries=2, backoff=0.001)
    async def always_fails():
        raise ValueError("nope")

    with pytest.raises(TaskError) as exc_info:
        await always_fails()

    err = exc_info.value
    assert err.task_name == "always_fails"
    assert err.attempts == 3  # 1 initial + 2 retries
    assert isinstance(err.__cause__, ValueError)


@pytest.mark.asyncio
async def test_task_timeout_raises_task_error():
    @task(retries=0, timeout=0.05)
    async def slow():
        await asyncio.sleep(1)
        return "done"

    with pytest.raises(TaskError):
        await slow()


@pytest.mark.asyncio
async def test_task_telemetry_records_error_spans_per_attempt():
    telemetry_store.metrics["custom_traces"].clear()

    @task(retries=1, backoff=0.001)
    async def boom():
        raise RuntimeError("x")

    with pytest.raises(TaskError):
        await boom()

    spans = _spans_for("task:boom")
    assert len(spans) == 2  # one span per attempt
    assert all(s["error"] for s in spans)


@pytest.mark.asyncio
async def test_task_with_explicit_name():
    @task(retries=0, name="custom_name")
    async def whatever():
        return "ok"

    assert whatever.task_name == "custom_name"
    result = await whatever()
    assert result == "ok"
    assert _spans_for("task:custom_name")


@pytest.mark.asyncio
async def test_task_enqueue_runs_in_background():
    from voodoo.queue import start_workers, stop_workers

    processed: list[str] = []

    @task(retries=0, name="bg_job")
    async def bg_job(payload):
        processed.append(payload)

    await bg_job.enqueue("hello")
    await start_workers()
    await asyncio.sleep(0.1)
    await stop_workers()

    assert "hello" in processed


@pytest.mark.asyncio
async def test_task_attributes_exposed():
    @task(retries=5, timeout=12, name="attr_job")
    async def job():
        return None

    assert job.is_task is True
    assert job.retries == 5
    assert job.timeout == 12
    assert job.task_name == "attr_job"
    assert callable(job.enqueue)


@pytest.mark.asyncio
async def test_mesh_on_to_task_chain():
    """`@mesh.on` stacked over `@task` runs the handler with retries + span."""
    telemetry_store.metrics["custom_traces"].clear()
    received: list[str] = []

    @mesh.on("lead.created")
    @task(retries=2, backoff=0.001, name="mesh_handler")
    async def handle_lead(payload):
        received.append(payload)

    # Broadcasting the event should invoke the @task-wrapped handler inline.
    await mesh.broadcast("lead.created", "Ada")
    assert received == ["Ada"]
    assert _spans_for("task:mesh_handler")
