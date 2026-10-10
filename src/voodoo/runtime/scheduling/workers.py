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
import time
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from voodoo.storage.queue import VoodooQueue

_workers: dict[str, Callable[..., Any]] = {}
_worker_backoff: dict[str, float] = {}
_worker_tasks: list[asyncio.Task] = []
_queue: VoodooQueue | None = None

logger = logging.getLogger("voodoo.runtime.scheduling.workers")


def _safe_failure_reason(error: BaseException) -> str:
    """Return a bounded, redacted reason safe for durable queue history."""
    from voodoo.security.redaction import redact_string

    return redact_string(f"{type(error).__name__}: {error}")[:512]


def registered_workers() -> tuple[tuple[str, Callable[..., Any]], ...]:
    """Public, read-only worker registry for Runtime inspection."""
    return tuple(sorted(_workers.items(), key=lambda item: item[0]))


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


def queue(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
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
    from voodoo.observability import trace_id_var

    q = await _get_queue()
    await q.enqueue(
        name,
        payload,
        trace_id=trace_id_var.get(),
        max_attempts=max(1, max_attempts),
        idempotency_key=idempotency_key,
    )


async def enqueue_compensation(
    effect: Any,
    *,
    reason: str | None = None,
    max_attempts: int = 3,
) -> Any:
    """Durably enqueue a declared Effect compensation operation.

    Compensation is explicit: this helper never runs the operation inline.
    The payload includes the original effect identity and failure reason, and
    the stable compensation key deduplicates retries across worker restarts.
    """
    name = getattr(effect, "compensation_name", None)
    if not name:
        raise ValueError("effect has no declared compensation")
    from voodoo.observability import trace_id_var

    q = await _get_queue()
    key = getattr(effect, "compensation_idempotency_key", None) or (
        f"compensate:{effect.id}"
    )
    payload = {
        "version": 1,
        "effect_id": effect.id,
        "effect_name": effect.name,
        "effect_payload": getattr(effect, "compensation_payload", None),
        "reason": reason,
    }
    return await q.enqueue(
        name,
        payload,
        trace_id=trace_id_var.get(),
        max_attempts=max(1, int(max_attempts)),
        idempotency_key=key,
    )


async def _run_worker(name: str, worker_id: str) -> None:
    """Poll the durable queue for tasks of type *name* and execute one attempt."""
    from voodoo.observability import telemetry_store, trace_id_var
    from voodoo.primitives.intent import Intent
    from voodoo.runtime.execution.engine import engine as runtime_engine

    func = _workers[name]
    is_async = inspect.iscoroutinefunction(func)

    while True:
        try:
            q = await _get_queue()
            claim_started = time.perf_counter()
            task = await q.claim(worker_id, types=(name,))
            if task is None:
                await asyncio.sleep(0.5)
                continue
            telemetry_store.record_trace(
                "worker.claimed",
                (time.perf_counter() - claim_started) * 1000,
                error=False,
            )
            attempt_started = time.perf_counter()

            resolved_trace = task.trace_id or str(uuid.uuid4())
            token = trace_id_var.set(resolved_trace)
            try:
                from voodoo.runtime.context import ExecutionContext, use_context

                intent = Intent(name=f"worker:{name}", params={"payload": task.payload})
                ctx = ExecutionContext(trace_id=resolved_trace, actor=f"worker:{name}")

                async def compute(
                    ctx: Any,
                    _func: Callable[..., Any] = func,
                    _payload: Any = task.payload,
                ) -> Any:
                    if is_async:
                        return await _func(_payload)
                    return _func(_payload)

                async with use_context(ctx):
                    await runtime_engine.execute(
                        intent, compute, actor=f"worker:{name}", parent=ctx
                    )
                await q.complete(task.id, worker_id)
                telemetry_store.record_trace(
                    "worker.completed",
                    (time.perf_counter() - attempt_started) * 1000,
                    error=False,
                )
            except Exception as exc:
                telemetry_store.record_trace(
                    "worker.failed",
                    (time.perf_counter() - attempt_started) * 1000,
                    error=True,
                )
                logger.error(
                    "Worker task failed: worker=%s task_id=%s error_type=%s",
                    name,
                    task.id,
                    type(exc).__name__,
                )
                await q.fail(
                    task.id,
                    worker_id,
                    _safe_failure_reason(exc),
                    backoff_base=_worker_backoff.get(name, 1.0),
                )
            finally:
                trace_id_var.reset(token)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error(
                "Worker poll loop failed: worker=%s error_type=%s",
                name,
                type(exc).__name__,
            )
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
        except Exception as exc:
            logger.error("Worker lease reaper failed: error_type=%s", type(exc).__name__)
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
