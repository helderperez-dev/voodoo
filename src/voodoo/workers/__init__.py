"""Voodoo worker runtime — the ``@task`` decorator.

``@task`` turns a function into a retried, timeout-bounded unit of work with a
telemetry span for every attempt. Tasks can be awaited directly or enqueued on
the configured :class:`~voodoo.storage.queue.VoodooQueue` provider.

Inline and durable retry semantics
----------------------------------
When a task is awaited directly, retries happen in-process because there is no
queue record to persist them. When ``task.enqueue(...)`` is used, the queue
persists ``max_attempts`` and owns retry scheduling/backoff. Each worker claim
runs exactly one function attempt; a failed attempt is returned to the durable
queue, so the remaining retry budget survives process failure and restart.

SQLite is the zero-infrastructure default. PostgreSQL and Redis providers can
be selected through Voodoo configuration; the in-memory provider is explicitly
ephemeral.

``@mesh.on`` → ``@task`` chain
------------------------------
Stacking the decorators runs the task inline with its normal retry semantics::

    @mesh.on("lead.created")
    @task(retries=3, timeout=10)
    async def sync_crm(payload):
        ...
"""

import asyncio
import functools
import inspect
import logging
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("voodoo.workers")

__all__ = ["task", "TaskError"]


class TaskError(Exception):
    """Structured error raised when a ``@task`` exhausts its retries."""

    def __init__(
        self,
        message: str,
        *,
        task_name: str,
        attempts: int,
        timeout: float | None,
    ) -> None:
        super().__init__(message)
        self.task_name = task_name
        self.attempts = attempts
        self.timeout = timeout


async def _run_task(
    func: Callable,
    task_name: str,
    retries: int,
    timeout: float | None,
    backoff_base: float,
    args: tuple,
    kwargs: dict,
) -> Any:
    """Execute *func* with in-process retries, timeout, and attempt telemetry."""
    from voodoo.telemetry import telemetry_store

    is_async = inspect.iscoroutinefunction(func)
    attempt = 0
    last_exc: BaseException | None = None

    while True:
        attempt += 1
        start = time.perf_counter()
        try:
            if is_async:
                coro = func(*args, **kwargs)
                if timeout is not None:
                    result = await asyncio.wait_for(coro, timeout=timeout)
                else:
                    result = await coro
            else:
                # Sync tasks run inline; timeout cannot pre-empt synchronous code.
                result = func(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 — converted to TaskError below
            last_exc = exc
            latency = (time.perf_counter() - start) * 1000
            telemetry_store.record_trace(f"task:{task_name}", latency, error=True)
            logger.warning(
                "task %s attempt %d/%d failed: %r",
                task_name,
                attempt,
                retries + 1,
                exc,
            )
            if attempt > retries:
                raise TaskError(
                    f"task {task_name!r} failed after {attempt} attempt(s): {exc}",
                    task_name=task_name,
                    attempts=attempt,
                    timeout=timeout,
                ) from last_exc
            delay = backoff_base * (2 ** (attempt - 1))
            await asyncio.sleep(delay)
            continue
        else:
            latency = (time.perf_counter() - start) * 1000
            telemetry_store.record_trace(f"task:{task_name}", latency, error=False)
            return result


def _register_task_worker(
    task_name: str,
    func: Callable,
    timeout: float | None,
    backoff_base: float,
) -> None:
    """Register a one-attempt background worker for a durable task type."""
    from voodoo.workers.queue import _worker_backoff, _workers

    async def worker(payload: Any) -> None:
        # Durable retries belong to VoodooQueue. A claim represents one attempt.
        await _run_task(func, task_name, 0, timeout, backoff_base, (payload,), {})

    _workers[task_name] = worker
    _worker_backoff[task_name] = backoff_base


async def _enqueue_task(task_name: str, payload: Any, max_attempts: int) -> None:
    """Enqueue *payload* with a durable attempt budget."""
    from voodoo.workers.queue import enqueue

    await enqueue(task_name, payload, max_attempts=max_attempts)


def task(
    _func: Callable | None = None,
    *,
    retries: int = 0,
    timeout: float | None = None,
    name: str | None = None,
    backoff: float = 0.1,
) -> Callable:
    """Decorator adding retries, timeout and telemetry spans to a function.

    Usable bare (``@task``) or parametrised (``@task(retries=3, timeout=30)``).
    Awaiting the wrapper retries locally. ``.enqueue(payload)`` persists the
    same retry budget as ``max_attempts=retries + 1`` and lets the queue own
    retry/recovery semantics across worker restarts.
    """

    def decorator(func: Callable) -> Callable:
        task_name = name or func.__name__

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await _run_task(
                func, task_name, retries, timeout, backoff, args, kwargs
            )

        # functools.wraps preserves the callable signature, while @task also
        # exposes runtime metadata/methods dynamically. Use an Any-typed alias
        # for those deliberate decorator extensions so static typing does not
        # mistake them for attributes declared by the original callable.
        task_wrapper: Any = wrapper
        task_wrapper.task_name = task_name
        task_wrapper.retries = retries
        task_wrapper.timeout = timeout
        task_wrapper.is_task = True

        async def enqueue_method(payload: Any = None) -> None:
            await _enqueue_task(task_name, payload, retries + 1)

        task_wrapper.enqueue = enqueue_method

        _register_task_worker(task_name, func, timeout, backoff)
        return wrapper

    if _func is not None and callable(_func):
        return decorator(_func)
    return decorator
