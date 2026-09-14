# Provider & Adapter Instructions

> Read before modifying `src/voodoo/adapters/`, `src/voodoo/storage/`, provider configuration, or adding infrastructure implementations.

## Provider law

Voodoo selects infrastructure through Runtime configuration, but a fresh
application is **Voodoo Store-first**. The default is not SQLite/PostgreSQL/Redis
or local filesystem persistence.

### Effective defaults

| Domain | Fresh-app default | Explicit alternatives |
|---|---|---|
| Durable Store | Voodoo Store | future Store providers |
| Model/Data | Voodoo Store Collections | SQLite, PostgreSQL |
| Queue/Jobs | Voodoo Store Jobs | Redis, PostgreSQL, compatibility SQLite |
| Scheduler | Voodoo Store schedules/Cron/triggers | compatibility adapters |
| Events | Voodoo Store-backed event contract | PostgreSQL/other registered adapters |
| Objects | Voodoo Store-backed object contract | S3-compatible adapters |
| Execution/HITL | Voodoo Store | SQLite, PostgreSQL explicit stores |
| Edge state | Voodoo Store | `SQLiteDeviceStore` explicit |
| Cache | memory | Redis |
| Models/LLMs | mock/local configured provider | OpenAI, Anthropic, Gemini, Ollama, custom |

**Never silently fall back from Voodoo Store to SQLite because Store is disabled,
missing, old, or failed.** Fail with a clear `ConfigurationError` and upgrade or
configuration guidance.

## Runtime Store ownership

All Store-backed infrastructure in one process reuses the Runtime-owned
`RuntimeStore`.

```text
Process / App
     |
 RuntimeStore
     |
 application.vstore
```

Adapters must not independently open the same Store file. Direct/standalone
infrastructure may use `acquire_runtime_store()`; App startup uses
`activate_runtime_store()` and may adopt a compatible shared handle.

One process = one live Store writer. Do not implement multi-process scaling by
sharing one `.vstore` file.

## Adapter contracts

Provider-neutral Framework contracts remain important even though Store is the
default:

- `VoodooDatabase`
- `VoodooQueue`
- `VoodooEventBus`
- `VoodooObjectStore`
- `VoodooCache`
- Execution persistence contracts
- Edge device-store contracts

External adapters replace the mechanics of the selected domain only. They do
not replace Identity, Capability, Policy or canonical Execution semantics.

## Capabilities

Adapter capabilities are factual feature declarations. Use boolean capability
flags and `require()` / `negotiate()` where appropriate. Never advertise a
feature the underlying binding cannot actually perform.

Example:

```python
from voodoo.adapters.capabilities import require

require(caps, "transactions")
```

A Store/node capability advertisement is also **not an authorization grant**.
Runtime authority belongs to Capability + Policy.

## Store binding rules

The framework currently targets:

```text
voodoo-store>=0.2.2,<0.3
```

When integrating a native Store capability:

1. verify the method exists in the installed Python binding;
2. fail clearly if a required API is missing;
3. hide native binding objects behind a Voodoo-owned semantic adapter;
4. share the active RuntimeStore lifecycle;
5. add restart/reopen acceptance tests for durable claims;
6. do not invent richer semantics that the binding does not expose.

Current intentional compatibility boundaries:

- Events use Store KV/transaction persistence until richer Topics/Streams Python bindings exist.
- Objects use Store KV/transaction persistence until richer native Object bindings exist.
- Store 0.2.2 supports schedule enable/disable but not arbitrary cursor repositioning.

## Adding an external infrastructure provider

1. Implement the relevant Framework Protocol.
2. Define accurate capabilities.
3. Register the provider in `voodoo.adapters.registry`.
4. Add provider-specific contract tests without weakening shared contracts.
5. Put third-party SDKs in an optional extra.
6. Use lazy imports for optional SDKs.
7. Raise `ConfigurationError` with install/config instructions when unavailable.
8. Update docs and `voodoo doctor`/inspection surfaces when applicable.

### Database example

```python
class MyDatabase:
    async def connect(self) -> None: ...
    async def execute(self, sql: str, params=()) -> None: ...
    async def fetchone(self, sql: str, params=()): ...
    async def fetchall(self, sql: str, params=()): ...
```

Selecting it must be explicit, for example:

```toml
[database]
provider = "mydb"
url = "..."
```

Do not change the fresh-app `database.provider = "voodoo"` law.

## Queue providers

The Store-backed queue is the default durable queue. External queue providers
must preserve the `VoodooQueue` contract: durable submit where promised,
claim/lease ownership, completion/failure, retry semantics, idempotency metadata
and status/stat inspection.

A provider may have weaker ordering/delivery guarantees; expose those honestly.
Never call an at-least-once system exactly-once.

## Event providers

Event providers must define durability/replay/ordering/delivery capabilities
accurately. Handler delivery and persistence are separate concerns.

For Store-backed events today, the compatibility implementation is deliberate;
do not replace it with SQLite merely because native Streams are not yet exposed.

## Object providers

S3-compatible storage is an explicit override, not a production default.
Presigning/multipart/checksum capabilities should be negotiated, not assumed.
The Store-backed object contract remains the local default.

## Cache providers

Cache is the main exception to durable Store convergence: transient cache may
remain in memory by default. Redis is an explicit cache provider. Do not use
cache as durable business truth.

## LLM providers

LLM SDKs remain optional and lazily imported. `MockProvider` is deterministic
and network-free for tests. Adding an LLM provider must not make AI mandatory for
the base Runtime.

Expected pattern:

```python
def get_provider(reference: str):
    # Resolve provider:model, import SDK only when chosen.
    ...
```

Missing SDKs must produce actionable installation errors.

## Contract testing

- Shared adapter contract suites should not be weakened to fit one provider.
- Provider-specific behavior belongs in provider-specific tests.
- Tests that require PostgreSQL/Redis/S3 must gate on env vars and optional SDK availability.
- Store-backed adapters need lifecycle/restart tests against one shared RuntimeStore.
- Test failure paths: Store disabled, missing binding capability, conflicting writer, expired lease, duplicate/idempotency behavior where relevant.

## Critical gotchas

1. **No silent SQLite fallback.** This is an architectural regression.
2. **No second Store writer.** Reuse RuntimeStore.
3. **No shared Store file between app workers/nodes.** Scale with node-local Stores.
4. **No fake native Store features.** Compatibility layers are preferable to false claims.
5. **No authority from discovery metadata.** Adapter/node capabilities do not grant Runtime Capability.
6. **No global atomicity from local transactions.** RuntimeTransaction is one local Store boundary.
7. **No exactly-once claim for external effects.** Use idempotency and explicit recovery semantics.

## Documentation sync

Provider/default changes require updates to `README.md`, `ARCHITECTURE.md`,
`docs/runtime.md`, the relevant subsystem doc, config examples and these agent
instructions. A code path and its public/documented default must agree before
release.
