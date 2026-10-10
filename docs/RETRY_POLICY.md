# Retry policy

Voodoo retries are owned by the execution layer that can durably schedule the
work. Inline `@task` calls retry in process; durable workers record one attempt
and delegate retry scheduling to the configured queue provider.

The Python inline, memory, SQLite, and Postgres paths use exponential backoff
with bounded symmetric jitter (±10%). Redis applies the same bound inside its
atomic Lua transition, and the native Store applies deterministic 90–110%
jitter inside the Rust durable job engine. This reduces synchronized retry
storms without moving scheduling out of the owner. The shared Python
`retry_delay()` helper accepts an injected random function so timing behavior
can be tested deterministically.

Redis and the native Store queue retain their backend-native retry primitives;
their retry schedules must not be reimplemented in the Runtime. Compensation
metadata and an operational retry budget remain release-readiness work.

All scheduler timestamps are normalized to UTC. Compensation is an explicit
application workflow: a reversible `Effect` can call
`configure_compensation(name, payload=...)`, which records a stable
`compensate:<effect-id>` idempotency key by default. The Runtime does not
silently execute that operation; an application or workflow must call
`enqueue_compensation(...)` explicitly after recording the original failure and
last error.

For workflows that want a policy-driven trigger, declare
`configure_compensation(..., trigger="on_failure")`. When the canonical
Execution Engine transitions an execution to failed or timed-out, it enqueues
compensations for successful effects with that trigger. Queue idempotency keeps
recovery and repeated failure handling safe; the default `trigger="manual"`
preserves explicit application control. Compensation enqueue failures are
redacted, observable diagnostics and never replace the original execution
failure.
