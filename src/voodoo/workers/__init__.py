"""Voodoo worker runtime — the ``@task`` decorator.

``@task`` turns an async function into a retried, timeout-bounded unit of
work that records a telemetry span for every execution attempt.  Tasks can
be awaited directly (inline) or enqueued onto the single-process queue
(:mod:`voodoo.queue`) for background execution.

Single-process scope & distributed backend boundary
-----------------------------------------------------
Today both the queue and the task runtime live in a single process: the
"broker" is an :class:`asyncio.Queue` and workers are :class:`asyncio.Task`
objects.  The public surface here (``@task``, ``task.enqueue``) is the seam
a future distributed backend (Redis/RQ, Celery, Dramatiq, …) can plug into
without changing application code — only the ``enqueue``/``_run_worker``
implementations in :mod:`voodoo.queue` and the registration below would be
swapped.

``@mesh.on`` → ``@task`` chain
------------------------------
Stacking the decorators is the intended pattern::

    @mesh.on("lead.created")
    @task(retries=3, timeout=10)
    async def sync_crm(payload):
        ...

``mesh.on`` registers the ``@task``-wrapped callable; when the event fires
the task runs with retries, timeout and a telemetry span.
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
    """Structured error raised when a ``@task`` exhausts its retries.

    The original exception is preserved on ``__cause__``; ``task_name``,
    ``attempts`` and ``timeout`` describe the execution context.
    """

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
    """Execute *func* with retries, timeout and a telemetry span per attempt."""
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
                # Sync tasks run inline; timeout is not enforced for sync code.
                result = func(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 — re-raised below
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
            # Exponential backoff before retrying.
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
    retries: int,
    timeout: float | None,
    backoff_base: float,
) -> None:
    """Register *func* as a background queue worker named *task_name*."""
    from voodoo.workers.queue import _workers

    async def worker(payload: Any) -> None:
        await _run_task(func, task_name, retries, timeout, backoff_base, (payload,), {})

    _workers[task_name] = worker


async def _enqueue_task(task_name: str, payload: Any) -> None:
    """Enqueue *payload* as a durable task of type *task_name*."""
    from voodoo.workers.queue import enqueue

    await enqueue(task_name, payload)


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

    The returned callable runs inline when awaited and also exposes
    ``.enqueue(payload)`` to submit the work to the background queue.  The
    task is registered as a queue worker so ``start_workers`` will consume
    enqueued items.
    """

    def decorator(func: Callable) -> Callable:
        task_name = name or func.__name__

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await _run_task(
                func, task_name, retries, timeout, backoff, args, kwargs
            )

        wrapper.task_name = task_name
        wrapper.retries = retries
        wrapper.timeout = timeout
        wrapper.is_task = True

        async def enqueue_method(payload: Any = None) -> None:
            await _enqueue_task(task_name, payload)

        wrapper.enqueue = enqueue_method

        _register_task_worker(task_name, func, retries, timeout, backoff)
        return wrapper

    if _func is not None and callable(_func):
        return decorator(_func)
    return decorator
