# Workers

## What it is

Voodoo has two related worker surfaces:

- `@task` for retry/timeout/telemetry semantics around callable work;
- the durable queue runtime for background delivery, leasing, retries and crash recovery.

On a fresh application, durable queued work is stored in the same
`.voodoo/application.vstore` used by the rest of the Runtime. The default broker
is **not** an in-memory `asyncio.Queue` and is **not** SQLite.

## Minimal task

```python
from voodoo.workers import task


@task(retries=3, timeout=30)
async def sync_crm(contact_id: int):
    await crm_api.sync(contact_id)


await sync_crm(42)
```

## Durable queue worker

```python
from voodoo.workers.queue import enqueue, queue


@queue("send-email")
async def send_email(payload: dict) -> None:
    await mailer.send(payload["to"], payload["subject"])


await enqueue(
    "send-email",
    {"to": "ada@example.com", "subject": "Hello"},
    max_attempts=3,
    idempotency_key="welcome:ada@example.com",
)
```

The job is persisted before a worker claims it. A process restart does not turn
the queue into an in-memory best-effort buffer.

## Default Store semantics

The Store-backed queue supports:

- durable submit/read;
- handler-filtered claim;
- lease ownership and generation;
- heartbeat;
- complete/fail/release;
- expired-lease reclaim;
- retry;
- delayed availability;
- priority;
- idempotency keys;
- status/list/stats/history;
- trace metadata propagation.

Each claimed application attempt executes through the canonical
`ExecutionEngine`, so worker delivery does not create a second execution model.

```text
Store Job
   |
 claim + lease
   |
 worker
   |
 Intent
   |
 Capability + Policy
   |
 canonical Execution
```

## Crash recovery

If a worker dies while holding a lease, the queue reaper can release expired
jobs for another claim according to queue semantics. External side effects still
need an idempotency strategy: durable delivery is not a promise that an external
API can never observe a duplicate request.

## Tracing

When a job is enqueued, the current trace id is persisted in the queue envelope.
The worker restores it before entering canonical Execution, preserving lineage
across the background boundary.

## Explicit Redis adapter

```bash
pip install "voodoo-framework[redis]"
```

```toml
[queue]
provider = "redis"
url = "redis://redis:6379/0"
```

Redis becomes the queue implementation only when explicitly selected.

## Explicit PostgreSQL queue

Where supported by the configured adapter stack, PostgreSQL can be selected as
an explicit durable queue backend. Configure the database/queue provider rather
than relying on a hidden fallback.

## Explicit legacy SQLite queue

SQLite remains a compatibility adapter for applications that deliberately
select it. It is not the fresh-app queue default.

## Runtime Store ownership

`VoodooStoreQueue` acquires/reuses the Runtime-owned Store. It does not open a
second writer to the same `.vstore` file. App shutdown resets cached queue
handles so a later Runtime lifecycle cannot retain a stale closed Store.

## Current guarantees

- local Store queue delivery is durable;
- leases make ownership explicit;
- retries are bounded by configured attempts;
- idempotency keys are persisted;
- external effects are not globally exactly-once;
- a queue job does not bypass Capability/Policy/Execution semantics.

## API reference

- `@task(...)` — inline task retry/timeout/telemetry wrapper.
- `@queue(name)` — register a durable queue handler.
- `enqueue(name, payload, *, max_attempts=1, idempotency_key=None)` — submit durable work.
- `start_workers()` / `stop_workers()` — worker lifecycle used by the App lifespan.
- `VoodooStoreQueue` — Store-backed implementation of the durable queue contract.
