# Provider & Adapter Instructions

> **Read this before:** adding a new database, queue, event bus, object store, cache, or LLM provider. Also read before modifying `src/voodoo/adapters/` or `src/voodoo/storage/`.

---

## The Provider System

Voodoo selects infrastructure by **configuration, never code changes**. The same application code runs on SQLite (local dev) or PostgreSQL (production) by changing a config string.

### Provider Migration Matrix

| Capability | Local (Default) | Production | Future |
|---|---|---|---|
| Database | SQLite | PostgreSQL | CockroachDB |
| Queue | SQLite/Memory | PostgreSQL/Redis | SQS/NATS/RabbitMQ |
| Events | SQLite/Local | PostgreSQL | NATS/Kafka |
| Objects | Local FS | S3 (AWS/MinIO/R2) | R2/GCS |
| Cache | Memory | Redis | Memcached |
| Models | Mock/Ollama | OpenAI/Anthropic/Gemini | Custom/Router |

**Config precedence:** Explicit file (`voodoo.yaml`/`voodoo.toml`) > `VOODOO_*` env vars > Local zero-infra defaults.

---

## Infrastructure Adapters

### Protocols (`voodoo/storage/*/interfaces.py`)

Each category has a Protocol that all implementations must satisfy:

| Protocol | Location | Methods |
|---|---|---|
| `VoodooDatabase` | `storage/database/interfaces.py` | `execute`, `fetchone`, `fetchall`, `executemany`, `migrate`, `transaction` |
| `VoodooQueue` | `storage/queue/interfaces.py` | `enqueue`, `claim`, `complete`, `fail`, `release`, `stats` |
| `VoodooEventBus` | `storage/events/interfaces.py` | `publish`, `subscribe`, `replay` |
| `VoodooObjectStore` | `storage/objects/interfaces.py` | `upload`, `download`, `delete`, `url`, `presign` |
| `VoodooCache` | `storage/cache/interfaces.py` | `get`, `set`, `delete`, `exists`, `expire` |

### Capabilities (`voodoo/adapters/capabilities.py`)

Each adapter declares a `*Capabilities` frozen dataclass with **boolean** flags:

```python
from voodoo.adapters.capabilities import DatabaseCapabilities

class MyDatabaseCapabilities(DatabaseCapabilities):
    provider: str = "mydb"
    transactions: bool = True
    migrations: bool = True
    native_json: bool = False
    concurrent_writers: bool = True
```

**Critical rules:**
- Capabilities are **booleans**, never enums.
- `Feature` type stays out of `__all__` — capability names live only in `voodoo.adapters`.
- Contract tests assert `is True` / `is False`, not truthiness.

### Capability Checking

```python
from voodoo.adapters.capabilities import require, negotiate

# Hard requirement — raises CapabilityError if unsupported
require(caps, "transactions")

# Soft negotiation — returns True/False
if negotiate(caps, "presign_urls"):
    # use presigned URLs
else:
    # fall back to direct download
```

### Registry (`voodoo/adapters/registry.py`)

```python
from voodoo.adapters.registry import registry

# Register a new provider
registry.register_database("mydb", factory_fn)
registry.register_queue("myqueue", factory_fn)

# Get an instance
db = registry.get_database(cfg, migrations)
queue = registry.get_queue(cfg, db)
```

The `registry` singleton calls `_register_defaults()` at init, registering all built-in providers.

---

## Adding a New Infrastructure Provider

### Step-by-step

1. **Implement the Protocol**
   ```python
   # voodoo/storage/database/mydb.py
   from __future__ import annotations
   from voodoo.storage.database.interfaces import VoodooDatabase, Migration

   class MyDatabase(VoodooDatabase):
       async def execute(self, sql: str, params: list[Any]) -> None: ...
       async def fetchone(self, sql: str, params: list[Any]) -> dict[str, Any] | None: ...
       # ... implement all Protocol methods
   ```

2. **Create capabilities**
   ```python
   from voodoo.adapters.capabilities import DatabaseCapabilities

   class MyDatabaseCapabilities(DatabaseCapabilities):
       provider: str = "mydb"
       transactions: bool = True
       migrations: bool = True
       native_json: bool = True
       concurrent_writers: bool = True
   ```

3. **Register the factory**
   ```python
   # voodoo/adapters/registry.py → _register_defaults()
   def _register_mydb() -> VoodooDatabase:
       from voodoo.storage.database.mydb import MyDatabase
       return MyDatabase(config)

   registry.register_database("mydb", _register_mydb)
   ```

4. **Add contract tests**
   ```python
   # tests/contracts/test_database_mydb.py
   import pytest
   from .test_database import DatabaseContractTests

   psycopg = pytest.importorskip("mydb_sdk")

   @pytest.mark.skipif(
       not os.environ.get("VOODOO_TEST_MYDB_URL"),
       reason="VOODOO_TEST_MYDB_URL not set",
   )
   class TestMyDatabase(DatabaseContractTests):
       @pytest.fixture
       def db(self):
           # return fresh MyDatabase instance
           ...
   ```

5. **Gate on env vars** — Use `os.environ.get(...)` at module level (not `os.environ[...]`).

6. **Add optional extra** in `pyproject.toml`:
   ```toml
   [project.optional-dependencies]
   mydb = ["mydb-sdk>=1.0"]
   ```

7. **Update `voodoo doctor`** — Add the provider to the capability matrix output in `cli/doctor.py`.

---

## LLM Providers (`voodoo.ai.providers`)

### Architecture

```
LLMProvider (ABC)
├── complete() → ProviderResponse
├── stream() → AsyncIterator[ProviderEvent]
└── name: str

Implementations:
├── MockProvider      (deterministic, no network, cost=0)
├── OpenAIProvider    (lazy openai import)
├── AnthropicProvider (lazy anthropic import)
├── GeminiProvider    (lazy google-generativeai import)
└── OllamaProvider    (lazy ollama import)
```

### Factory

```python
from voodoo.ai.providers import get_provider

provider = get_provider("openai:gpt-4o")
# Resolves "provider:model" string → _PROVIDER_CLASSES["openai"] → OpenAIProvider(model="gpt-4o")
```

`_PROVIDER_CLASSES` maps provider name → fully-qualified class path. Uses `importlib.import_module()` for lazy loading.

### Adding a New LLM Provider

1. **Subclass `LLMProvider`**
   ```python
   # voodoo/ai/providers/myllm.py
   from __future__ import annotations
   from voodoo.ai.providers.base import LLMProvider, ProviderResponse, ProviderEvent

   class MyLLMProvider(LLMProvider):
       name = "myllm"

       async def complete(self, messages, **kwargs) -> ProviderResponse:
           import myllm_sdk  # lazy import
           ...

       async def stream(self, messages, **kwargs) -> AsyncIterator[ProviderEvent]:
           import myllm_sdk  # lazy import
           ...
   ```

2. **Register in `_PROVIDER_CLASSES`**
   ```python
   # voodoo/ai/providers/__init__.py
   _PROVIDER_CLASSES = {
       "mock": "voodoo.ai.providers.mock.MockProvider",
       "openai": "voodoo.ai.providers.openai.OpenAIProvider",
       "myllm": "voodoo.ai.providers.myllm.MyLLMProvider",
   }
   ```

3. **Use lazy imports** — `importlib.import_module()` or function-level `import`.

4. **Missing SDK handling** — Raise `ConfigurationError` with install instructions:
   ```python
   raise ConfigurationError(
       "myllm-sdk not installed. Install with: uv pip install voodoo-framework[ai]"
   )
   ```

5. **Add to `[ai]` extra** in `pyproject.toml` if new dependency.

6. **Test with MockProvider patterns** — Don't make real API calls in tests.

---

## Style Adapters (`voodoo.adapters`)

Style adapters generate CSS classes for components:

```python
from voodoo.ui.styles import set_style_adapter
from voodoo.adapters.tailwind import TailwindAdapter

# Switch to Tailwind
set_style_adapter(TailwindAdapter())
```

### Adding a New Style Adapter

1. Implement the `StyleAdapter` Protocol (`component_classes()` method).
2. Place in `voodoo/adapters/<name>.py`.
3. Register via `set_style_adapter()` at runtime.

---

## Critical Gotchas

1. **PostgreSQL FK ordering** — `execution_events.execution_id → executions.id` is enforced. Always upsert the parent row BEFORE appending journal events.
2. **PostgreSQL dict rows** — psycopg returns dict-like rows, so use `row["col"]` not `row[0]`.
3. **Database-backed queues** — SQLite/Postgres queues require a database instance passed or created.
4. **`_protocol_check`** — Place Protocol compliance checks at file BOTTOM under `if TYPE_CHECKING:`.
5. **Unknown provider** — Raise `ConfigurationError` with available providers list.
6. **Migrations** — Registered via `register_framework_migration()` at import time. Each migration has a version number and SQL string.
7. **WAL mode** — `SQLiteExecutionStore` uses WAL mode with `busy_timeout=5000`.
8. **Redis Lua scripts** — `RedisQueue` uses atomic Lua scripts over ZSETs for claim/complete.
9. **PostgresQueue** — Uses `FOR UPDATE SKIP LOCKED` for concurrent claim.
10. **S3 presign** — `S3ObjectStore` supports presigned URLs, checksums, and multipart uploads.
