"""Durable async queue & worker runtime.

Workers poll a ``VoodooQueue`` provider for claimable tasks. Each claimed task
performs exactly one canonical Runtime execution attempt. The queue owns durable
delivery, leasing, retry scheduling, and crash recovery; it never executes
application code itself.

The ``@queue`` decorator and ``enqueue``/``start_workers``/``stop_workers``
functions form the public API; swapping the provider changes infrastructure
without touching application code.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import os
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from voodoo.storage.queue import VoodooQueue

_workers: dict[str, Callable] = {}
_worker_backoff: dict[str, float] = {}
_worker_tasks: list[asyncio.Task] = []
_queue: VoodooQueue | None = None

logger = logging.getLogger("voodoo.queue")


def _get_provider() -> str:
    from voodoo.config import get_config

    return get_config().queue.provider.lower()


async def _get_queue() -> VoodooQueue:
    """Resolve the active queue backend from central runtime configuration."""
    global _queue
    if _queue is not None:
        return _queue

    from voodoo.adapters.registry import registry
    from voodoo.config import get_config

    cfg = get_config().queue
    provider = cfg.provider.lower()

    if provider == "voodoo":
        from voodoo.storage.queue.store import VoodooStoreQueue

        _queue = VoodooStoreQueue()
    elif provider in {"memory", "redis"}:
        _queue = registry.get_queue(cfg)
    else:
        from voodoo.data.base import _database, get_db

        db = _database
        if db is None:
            await get_db()
            from voodoo.data.base import _database as active_db

            db = active_db
        if db is None:
            db = registry.get_database()
            await db.connect()
        _queue = registry.get_queue(cfg, db=db)

    await _queue.setup()
    return _queue


def queue(name: str):
    def decorator(func: Callable):
        _workers[name] = func
        return func

    return decorator


async def enqueue(
    name: str,
    payload: Any,
    *,
    max_attempts: int = 1,
    idempotency_key: str | None = None,
) -> None:
    """Enqueue *payload* as a durable task of type *name*."""
    from voodoo.telemetry import trace_id_var

    q = await _get_queue()
    await q.enqueue(
        name,
        payload,
        trace_id=trace_id_var.get(),
        max_attempts=max(1, max_attempts),
        idempotency_key=idempotency_key,
    )


async def _run_worker(name: str, worker_id: str) -> None:
    """Poll the durable queue for tasks of type *name* and execute one attempt."""
    from voodoo.primitives.intent import Intent
    from voodoo.runtime.engine import engine as runtime_engine
    from voodoo.telemetry import trace_id_var

    func = _workers[name]
    is_async = inspect.iscoroutinefunction(func)

    while True:
        try:
            q = await _get_queue()
            task = await q.claim(worker_id, types=(name,))
            if task is None:
                await asyncio.sleep(0.5)
                continue

            resolved_trace = task.trace_id or str(uuid.uuid4())
            token = trace_id_var.set(resolved_trace)
            try:
                from voodoo.runtime.context import ExecutionContext, use_context

                intent = Intent(name=f"worker:{name}", params={"payload": task.payload})
                ctx = ExecutionContext(trace_id=resolved_trace, actor=f"worker:{name}")

                async def compute(ctx, _func=func, _payload=task.payload):
                    if is_async:
                        return await _func(_payload)
                    return _func(_payload)

                async with use_context(ctx):
                    await runtime_engine.execute(
                        intent, compute, actor=f"worker:{name}", parent=ctx
                    )
                await q.complete(task.id, worker_id)
            except Exception as exc:  # noqa: BLE001
                logger.error("Error in worker %s task %d: %r", name, task.id, exc)
                await q.fail(
                    task.id,
                    worker_id,
                    str(exc),
                    backoff_base=_worker_backoff.get(name, 1.0),
                )
            finally:
                trace_id_var.reset(token)
        except asyncio.CancelledError:
            break
        except Exception as exc:  # noqa: BLE001
            logger.error("Worker %s poll loop error: %r", name, exc)
            await asyncio.sleep(1.0)


async def _reaper() -> None:
    """Reclaim expired leases from workers that died mid-attempt."""
    while True:
        try:
            q = await _get_queue()
            reclaimed = await q.release_expired()
            if reclaimed:
                logger.info("reclaimed %d expired task(s)", reclaimed)
        except asyncio.CancelledError:
            break
        except Exception as exc:  # noqa: BLE001
            logger.error("reaper error: %r", exc)
        await asyncio.sleep(5.0)


async def start_workers() -> None:
    """Start one poller per registered worker type plus a lease reaper."""
    for name in _workers:
        worker_id = f"{name}:{os.getpid()}"
        worker_task = asyncio.create_task(_run_worker(name, worker_id))
        _worker_tasks.append(worker_task)
    if _workers:
        _worker_tasks.append(asyncio.create_task(_reaper()))


async def stop_workers() -> None:
    """Cancel worker tasks and release cached provider handles for next lifecycle."""
    global _queue

    for worker_task in _worker_tasks:
        worker_task.cancel()
    if _worker_tasks:
        await asyncio.gather(*_worker_tasks, return_exceptions=True)
    _worker_tasks.clear()
    _queue = None
