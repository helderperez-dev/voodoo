import asyncio
import inspect
import logging
from collections.abc import Callable
from typing import Any

_queues: dict[str, asyncio.Queue] = {}
_workers: dict[str, Callable] = {}
_worker_tasks: list[asyncio.Task] = []

logger = logging.getLogger("voodoo.queue")


def queue(name: str):
    def decorator(func: Callable):
        if name not in _queues:
            _queues[name] = asyncio.Queue()
        _workers[name] = func
        return func

    return decorator


async def enqueue(name: str, payload: Any):
    if name not in _queues:
        _queues[name] = asyncio.Queue()
    from voodoo.telemetry import trace_id_var

    trace_id = trace_id_var.get()
    await _queues[name].put({"payload": payload, "trace_id": trace_id})


async def _run_worker(name: str):
    q = _queues[name]
    func = _workers[name]
    import uuid

    from voodoo.telemetry import trace_id_var

    while True:
        try:
            item = await q.get()
            payload = item.get("payload")
            trace_id = item.get("trace_id") or str(uuid.uuid4())
            token = trace_id_var.set(trace_id)
            try:
                if inspect.iscoroutinefunction(func):
                    await func(payload)
                else:
                    func(payload)
            except Exception as e:
                logger.error(f"Error in worker {name}: {e}")
            finally:
                trace_id_var.reset(token)
                q.task_done()
        except asyncio.CancelledError:
            break


async def start_workers():
    for name in _workers.keys():
        task = asyncio.create_task(_run_worker(name))
        _worker_tasks.append(task)


async def stop_workers():
    for task in _worker_tasks:
        task.cancel()
    if _worker_tasks:
        await asyncio.gather(*_worker_tasks, return_exceptions=True)
    _worker_tasks.clear()
