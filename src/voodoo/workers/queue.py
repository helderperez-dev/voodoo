"""Durable async queue & worker runtime.

Workers poll a ``VoodooQueue`` provider (SQLite by default, memory optional)
for claimable tasks. Each task is executed through the runtime engine; on
success the task is completed, on failure it's retried with backoff until
``max_attempts`` is exhausted.

The ``@queue`` decorator and ``enqueue``/``start_workers``/``stop_workers``
functions form the public API; swapping the provider (see
``VOODOO_QUEUE_PROVIDER``) changes the backend without touching application
code.
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
_worker_tasks: list[asyncio.Task] = []
_queue: VoodooQueue | None = None

logger = logging.getLogger("voodoo.queue")


def _get_provider() -> str:
    from voodoo.config import get_config

    return get_config().queue.provider.lower()


async def _get_queue() -> VoodooQueue:
    """Resolve the active queue backend.

    Resolved using the central ProviderRegistry and VoodooConfig (Spec §31).
    """
    global _queue
    if _queue is not None:
        return _queue

    from voodoo.adapters.registry import registry
    from voodoo.config import get_config
    from voodoo.data.base import _database, get_db

    cfg = get_config().queue
    provider = cfg.provider.lower()

    if provider == "memory":
        _queue = registry.get_queue(cfg)
    else:
        # SQLiteQueue requires a database
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


async def enqueue(name: str, payload: Any):
    """Enqueue *payload* as a durable task of type *name*."""
    from voodoo.telemetry import trace_id_var

    q = await _get_queue()
    await q.enqueue(
        name,
        payload,
        trace_id=trace_id_var.get(),
        max_attempts=1,
    )


async def _run_worker(name: str, worker_id: str):
    """Poll the durable queue for tasks of type *name* and execute them."""
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

            token = trace_id_var.set(task.trace_id or str(uuid.uuid4()))
            try:
                intent = Intent(name=f"worker:{name}", params={"payload": task.payload})

                async def compute(ctx, _func=func, _payload=task.payload):
                    if is_async:
                        return await _func(_payload)
                    return _func(_payload)

                await runtime_engine.execute(intent, compute, actor=f"worker:{name}")
                await q.complete(task.id, worker_id)
            except Exception as exc:
                logger.error("Error in worker %s task %d: %r", name, task.id, exc)
                await q.fail(task.id, worker_id, str(exc))
            finally:
                trace_id_var.reset(token)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("Worker %s poll loop error: %r", name, exc)
            await asyncio.sleep(1.0)


async def _reaper():
    """Background task that reclaims expired leases from dead workers."""
    while True:
        try:
            q = await _get_queue()
            reclaimed = await q.release_expired()
            if reclaimed:
                logger.info("reclaimed %d expired task(s)", reclaimed)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("reaper error: %r", exc)
        await asyncio.sleep(5.0)


async def start_workers():
    """Start one poller per registered worker type plus a lease reaper."""
    for name in _workers:
        worker_id = f"{name}:{os.getpid()}"
        task = asyncio.create_task(_run_worker(name, worker_id))
        _worker_tasks.append(task)
    if _workers:
        _worker_tasks.append(asyncio.create_task(_reaper()))


async def stop_workers():
    """Cancel all worker tasks and reclaim any in-flight leases."""
    for task in _worker_tasks:
        task.cancel()
    if _worker_tasks:
        await asyncio.gather(*_worker_tasks, return_exceptions=True)
    _worker_tasks.clear()
