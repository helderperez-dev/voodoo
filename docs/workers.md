# Workers

## What it is

The `@task` decorator turns an async function into a retried, timeout-bounded unit of work with telemetry spans. Tasks can be awaited directly (inline) or enqueued for background execution.

## Minimal example

```python
from voodoo.workers import task


@task(retries=3, timeout=30)
async def sync_crm(contact_id: int):
    await crm_api.sync(contact_id)


# Run inline
await sync_crm(42)

# Enqueue for background processing
await sync_crm.enqueue(42)
```

## Common usage

### Bare decorator

```python
@task
async def send_email(to: str, subject: str):
    await mailer.send(to, subject)
```

### With retries and timeout

```python
@task(retries=5, timeout=10)
async def fetch_api(url: str):
    response = await httpx.get(url)
    return response.json()
```

### Stacking with mesh events

```python
from voodoo.mesh import mesh


@mesh.on("lead.created")
@task(retries=3, timeout=10)
async def sync_crm(payload):
    await crm_api.sync(payload)
```

When the event fires, the task runs with retries, timeout, and a telemetry span.

### Enqueuing

```python
@task
async def process_file(path: str): ...


await process_file.enqueue("/data/input.csv")
```

## How it works

1. `@task` wraps the function with retries, timeout, and telemetry.
2. The wrapped function runs inline when awaited.
3. `.enqueue(payload)` submits to the single-process async queue.
4. The queue worker runs the task with the same retries/timeout.
5. Telemetry spans are recorded for every attempt.

## Advanced

### Queue internals

The broker is an `asyncio.Queue`; workers are `asyncio.Task` objects. The public surface (`@task`, `.enqueue`) is the seam for a future distributed backend (Redis, Celery, etc.) — only the internals would swap.

### TaskError

When a task exhausts its retries, `TaskError` is raised with structured context:

```python
try:
    await risky_task()
except TaskError as e:
    print(f"{e.task_name} failed after {e.attempts} attempts")
```

### Correlation ID propagation

When a task is enqueued, the current `trace_id` is captured and propagated to the worker, ensuring telemetry spans are correlated across the queue boundary.

## API reference

- `task(func=None, *, retries=0, timeout=None, name=None, backoff=0.1)` — decorator.
- `TaskError` — raised when retries are exhausted.
- `task.enqueue(payload)` — submit to the background queue.
