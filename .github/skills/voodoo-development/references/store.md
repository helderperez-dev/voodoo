# Store Usage

Default durable substrate:

```text
.voodoo/application.vstore
```

One Runtime process owns the Store lifecycle and writer.

## Native primitives

Prefer native:

- Collections
- KV for genuinely key/value concerns
- Jobs / Queue
- Scheduler / Cron
- Topics / Streams
- Consumer Groups
- Objects / named refs
- Outbox
- RPC
- CDC
- Workflow / HITL
- health/checkpoint/compaction/restore

## Transactions

Voodoo Store supports local transaction boundaries across supported native domains.

Do not describe current behavior as global consensus, global serializability, or distributed exactly-once unless a future implementation explicitly proves those guarantees.

## External adapters

PostgreSQL, Redis, SQLite, S3-compatible storage and similar systems are explicit adapters or compatibility choices, not automatic defaults.

Do not introduce an external service when Store already provides the required durable primitive.
