# Skill: Add Provider

> **When to use:** When adding a new database, queue, cache, event bus, or object store adapter. Also for new LLM providers.

---

## Purpose

Guide the structured addition of a new infrastructure or LLM provider, ensuring it follows the Protocol-based adapter system, passes contract tests, and is properly registered.

---

## Prerequisites

1. Read `.github/instructions/providers.instructions.md` — full provider system reference.
2. Read `.github/instructions/testing.instructions.md` — contract test patterns.
3. Read `.github/copilot-instructions.md` — Provider/Adapter System section.

---

## Adding an Infrastructure Provider

### Step 1: Implement the Protocol

Choose the relevant Protocol and implement it:

| Protocol | Location | Methods |
|---|---|---|
| `VoodooDatabase` | `storage/database/base.py` | `execute`, `fetchone`, `fetchall`, `transaction` |
| `VoodooQueue` | `storage/queue/base.py` | `enqueue`, `claim`, `complete`, `retry`, `release` |
| `VoodooEventBus` | `storage/events/base.py` | `publish`, `subscribe`, `replay` |
| `VoodooObjectStore` | `storage/objects/base.py` | `upload`, `download`, `delete`, `presign` |
| `VoodooCache` | `storage/cache/base.py` | `get`, `set`, `delete`, `exists`, `expire` |

Create the implementation in `src/voodoo/storage/<category>/<provider>.py`:

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from voodoo.storage.database.base import VoodooDatabase, DatabaseCapabilities

__all__ = ["MyProviderDatabase", "MyProviderDatabaseCapabilities"]


class MyProviderDatabaseCapabilities(DatabaseCapabilities):
    """Boolean capability flags for MyProvider."""

    supports_transactions: bool = True
    supports_migrations: bool = True
    # ... provider-specific flags


class MyProviderDatabase(VoodooDatabase):
    """MyProvider database adapter."""

    def __init__(self, config: dict[str, Any]) -> None:
        # Lazy import the SDK
        import myprovider_sdk
        self._client = myprovider_sdk.connect(**config)

    async def execute(self, query: str, params: list | None = None) -> None:
        ...

    async def fetchone(self, query: str, params: list | None = None) -> dict | None:
        ...

    # ... implement all Protocol methods
```

### Step 2: Create Capabilities Dataclass

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class MyProviderDatabaseCapabilities(DatabaseCapabilities):
    supports_transactions: bool = True
    supports_migrations: bool = True
    supports_returning: bool = False
    # ... boolean flags only, never enums
```

### Step 3: Register the Factory

In `src/voodoo/adapters/registry.py` → `_register_defaults()`:

```python
def _register_defaults() -> None:
    # ... existing registrations
    registry.register_database(
        "myprovider",
        lambda cfg: __import__(
            "voodoo.storage.database.myprovider",
            fromlist=["MyProviderDatabase"],
        ).MyProviderDatabase(cfg),
    )
```

Use lazy `importlib.import_module()` — never import the SDK at module level.

### Step 4: Add Provider-Specific Contract Tests

Create `tests/contracts/test_database_myprovider.py`:

```python
from __future__ import annotations

import os
import pytest

myprovider_sdk = pytest.importorskip("myprovider_sdk")

from .test_database import DatabaseContractTests

@pytest.mark.skipif(
    not os.environ.get("VOODOO_TEST_MYSQL_URL"),
    reason="VOODOO_TEST_MYSQL_URL not set",
)
class TestMyProviderDatabase(DatabaseContractTests):
    @pytest.fixture
    def db(self):
        from voodoo.storage.database.myprovider import MyProviderDatabase
        cfg = {"url": os.environ.get("VOODOO_TEST_MYSQL_URL")}
        db = MyProviderDatabase(cfg)
        yield db
        # cleanup
```

**Critical:** The mixin (`DatabaseContractTests`) must pass unchanged. Add provider-specific tests as additional methods on the subclass.

### Step 5: Gate with importorskip + env vars

```python
# At module level — runs before skip markers
myprovider_sdk = pytest.importorskip("myprovider_sdk")

@pytest.mark.skipif(
    not os.environ.get("VOODOO_TEST_MYSQL_URL"),
    reason="VOODOO_TEST_MYSQL_URL not set",
)
class TestMyProviderDatabase(DatabaseContractTests):
    ...
```

**Gotcha:** Use `os.environ.get(...)` not `os.environ[...]` at module level.

### Step 6: Add Optional Extra

In `pyproject.toml`:

```toml
[project.optional-dependencies]
mysql = ["mysql-connector-python>=8.0"]
```

### Step 7: Update CLI Capability Matrix

In `src/voodoo/cli/doctor.py`, add the new provider to the capability matrix output:

```python
# In the doctor command
providers = {
    "database": ["sqlite", "postgres", "myprovider"],
    # ...
}
```

### Step 8: Quality Gate

```bash
just format && just lint && just test
```

Run contract tests with the service running:

```bash
# Start the service
docker run --name voodoo-mysql ...

# Run contract tests
VOODOO_TEST_MYSQL_URL="mysql://..." uv run pytest tests/contracts/test_database_myprovider.py -v
```

---

## Adding an LLM Provider

### Step 1: Subclass LLMProvider

In `src/voodoo/ai/providers/myprovider.py`:

```python
from __future__ import annotations

from voodoo.ai.providers.base import LLMProvider, ProviderResponse, ProviderEvent

__all__ = ["MyProviderProvider"]


class MyProviderProvider(LLMProvider):
    """MyProvider LLM provider."""

    name = "myprovider"

    def __init__(self, model: str, **kwargs: Any) -> None:
        self.model = model
        self._client = None

    def _ensure_client(self) -> None:
        if self._client is None:
            try:
                import myprovider_sdk
            except ImportError:
                raise ConfigurationError(
                    "myprovider_sdk not installed. "
                    "Install with: uv pip install voodoo-framework[ai]"
                )
            self._client = myprovider_sdk.Client()

    async def complete(self, messages, **kwargs) -> ProviderResponse:
        self._ensure_client()
        # ... call SDK, return ProviderResponse

    async def stream(self, messages, **kwargs):
        self._ensure_client()
        # ... yield ProviderEvent
```

### Step 2: Register in _PROVIDER_CLASSES

In `src/voodoo/ai/providers/__init__.py`:

```python
_PROVIDER_CLASSES = {
    "openai": "voodoo.ai.providers.openai.OpenAIProvider",
    "anthropic": "voodoo.ai.providers.anthropic.AnthropicProvider",
    "gemini": "voodoo.ai.providers.gemini.GeminiProvider",
    "ollama": "voodoo.ai.providers.ollama.OllamaProvider",
    "mock": "voodoo.ai.providers.mock.MockProvider",
    "myprovider": "voodoo.ai.providers.myprovider.MyProviderProvider",  # NEW
}
```

### Step 3: Add Optional Extra

In `pyproject.toml`:

```toml
[project.optional-dependencies]
ai = ["openai", "anthropic", "myprovider-sdk"]
```

### Step 4: Test with MockProvider Patterns

```python
async def test_myprovider_agent():
    # Use MockProvider — never make real API calls in tests
    agent = Agent(model="mock:default", tools=[])
    run = await agent.run("Hello")
    assert run.output is not None
```

### Step 5: Quality Gate

```bash
just format && just lint && just test
```

---

## Checklist

### Infrastructure Provider
- [ ] Protocol implemented (all methods).
- [ ] Capabilities dataclass (boolean flags, frozen).
- [ ] Factory registered in `adapters/registry.py`.
- [ ] Contract tests pass (mixin unchanged).
- [ ] Provider-specific tests added.
- [ ] Gated with `importorskip` + env vars.
- [ ] Optional extra in `pyproject.toml`.
- [ ] CLI doctor capability matrix updated.
- [ ] Quality gate passes.

### LLM Provider
- [ ] Subclassed `LLMProvider` ABC.
- [ ] `complete()` and `stream()` implemented.
- [ ] Registered in `_PROVIDER_CLASSES`.
- [ ] Lazy SDK import (function level).
- [ ] Optional extra in `pyproject.toml`.
- [ ] Tested with MockProvider patterns.
- [ ] Quality gate passes.
