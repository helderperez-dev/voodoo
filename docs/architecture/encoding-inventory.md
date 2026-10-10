# Durable encoding and ownership inventory

This inventory records where Voodoo stores structured data and which subsystem
owns its encoding. It is a design boundary, not a promise that every external
adapter uses the native Store format.

| Domain | Current encoding | Owner | Durability / migration rule |
| --- | --- | --- | --- |
| Application `Model` records | Native Store collection records, UTF-8 canonical JSON payload, `schema_version=1`, indexed fields | `voodoo.data.store_backend` + Store | Collection creation is idempotent; schema changes require a versioned migration fixture |
| Runtime identity and registry records | Runtime dictionaries projected into Store-owned collections | Runtime domain + Store | `from_record`/`to_record` codecs must preserve explicit timestamps and enum values |
| Edge device, replay, and response records | Native Store collections (`runtime.edge_*`) with version-1 JSON records or bounded response bytes | `voodoo.edge.store_voodoo` + Store | Collection creation is idempotent; legacy prefixed KV keys remain read-through during migration |
| Runtime workflow/execution records | Native Store workflow primitives with a version-1 JSON workflow-index collection; execution records use Runtime codecs and Store-backed persistence | `voodoo.runtime` | Add a codec version before changing field meaning; legacy prefixed workflow indexes remain read-through and migrate to the collection on the next checkpoint; retain prior fixture during migration |
| Durable events/outbox | Version-1 JSON event envelope in native Store outbox events or the version-1 `runtime.outbox_pending`/`runtime.outbox_delivered` collections; external adapters retain their explicit schemas | `voodoo.storage.events.codec` + Runtime transaction owner | Event type and payload are versioned independently; publish rejects future/invalid schemas and replay rejects malformed/future envelopes with diagnostics; collection fallback moves pending→delivered atomically through the Store transaction and legacy prefixed keys remain read-through; adapter fixtures live in `tests/contracts/test_eventbus.py` and `tests/integration/test_voodoo_store_events.py` |
| Scheduler and task payloads | JSON payload plus typed scheduling metadata | `voodoo.storage.scheduler` / queue owner | Retry/idempotency metadata is part of the record; adapters may use SQLite/Postgres/Redis schemas |
| Execution artifacts and observations | Adapter-owned JSON columns or native Store records | execution/observability owner | Treat provider payloads as opaque; redact before persistence and migration |
| Object bytes | Native Store object API or explicit S3/local adapter | object storage owner | Bytes are not embedded in JSON records; metadata and lifecycle are separate |
| Session/UI state | In-memory session state and transport patches | Runtime/UI session owner | Ephemeral by default; never infer durable recovery from a browser patch |
| External compatibility adapters | SQLite/Postgres/Redis/S3 native schemas and JSON fields | explicit adapter | Adapter compatibility is documented separately; no hidden fallback over native Store |

## Invariants

- Every durable native Store collection declares a schema version and codec.
- Encodings are deterministic and bounded; arbitrary Python pickle is not a
  supported persistence format.
- Runtime owns record meaning and migration policy; Store owns checksums,
  transactions, recovery, and file-format compatibility.
- A migration adds a fixture and a forward/backward compatibility test before
  changing an existing durable record.

**Inventory baseline:** 2026-10-06. Review when a new durable domain or Store
primitive is introduced.
