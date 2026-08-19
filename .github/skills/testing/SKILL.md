# Skill: Testing

> **When to use:** When writing new tests, fixing test failures, or adding contract tests for a new adapter.

---

## Purpose

Ensure all tests follow Voodoo's testing standards: proper structure, isolation, contract patterns, and the quality gate.

---

## Prerequisites

1. Read `.github/instructions/testing.instructions.md` — full testing reference.
2. Read `.github/copilot-instructions.md` — Testing Standards section.

---

## Workflow

### Step 1: Identify What to Test

| Type | Location | Pattern |
|---|---|---|
| Unit test | `tests/test_<module>.py` | Test class with fresh instances |
| Contract test | `tests/contracts/test_<category>_<provider>.py` | Subclass mixin, add provider tests |
| Integration test | `tests/test_integration.py` | End-to-end through the stack |
| API contract | `tests/test_contract_api.py` | Public exports are importable |

### Step 2: Write the Test

#### Standard unit test

```python
from __future__ import annotations

import pytest

class TestMyFeature:
    """Tests for MyFeature."""

    async def test_basic_case(self):
        # Arrange
        obj = MyFeature()

        # Act
        result = await obj.do_thing()

        # Assert
        assert result == expected

    async def test_error_case(self):
        with pytest.raises(MyError):
            await obj.do_bad_thing()
```

#### Contract test (new provider)

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

#### AI/Agent test

```python
class TestMyAgent:
    async def test_agent_basic(self):
        # Use MockProvider — never real API calls
        agent = Agent(model="mock:default", tools=[])
        run = await agent.run("Hello")
        assert run.output is not None

    async def test_agent_with_tool(self):
        provider = ToolThenTextProvider(
            tool_call={"name": "search", "args": {"q": "python"}},
            final_text="Found Python!",
        )
        agent = Agent(model="mock:default", tools=[search_tool])
        agent.provider = provider
        run = await agent.run("Search for Python")
        assert "Found Python!" in run.output
```

#### Failure-path test (durability)

```python
class TestExecutionRecovery:
    async def test_crash_during_running_recovers(self):
        # 1. Create execution, set status to running
        # 2. Simulate crash (close store without completing)
        # 3. Reopen store, call recover()
        # 4. Verify execution is recovered as 'waiting'
        ...

    async def test_completed_effects_skipped_on_resume(self):
        # 1. Create execution with 3 effects
        # 2. Complete effects 1 and 2, checkpoint
        # 3. Crash
        # 4. Recover, resume
        # 5. Verify only effect 3 is executed
        ...
```

### Step 3: Ensure Isolation

Autouse fixtures in `tests/conftest.py` handle cleanup:

| Fixture | What it cleans |
|---|---|
| `_clean_page_registry` | `@page` registry |
| `_reset_queue_state` | Queue provider + worker tasks (NOT handler registry) |
| `_close_db_after_test` | aiosqlite connections |
| `_isolated_registry` | Fresh `ToolRegistry` per test |
| `_clean_mesh_handlers` | Mesh event handlers |
| `_clean_telemetry` | Telemetry metrics |

**Rules:**
- Never disable autouse fixtures.
- Use fresh instances per test — never share mutable state.
- Use `@pytest.fixture` for test-specific setup.

### Step 4: Handle Env Vars

**Critical:** Use `os.environ.get(...)` at module level, never `os.environ[...]`.

```python
# CORRECT — runs before skip markers
@pytest.mark.skipif(
    not os.environ.get("VOODOO_TEST_REDIS_URL"),
    reason="VOODOO_TEST_REDIS_URL not set",
)
class TestRedisQueue(QueueContractTests):
    ...

# WRONG — KeyError before skip markers can run
@pytest.mark.skipif(
    not os.environ["VOODOO_TEST_REDIS_URL"],  # KeyError!
    reason="...",
)
```

### Step 5: Run Tests

```bash
# Full suite
just test

# Specific file
uv run pytest tests/test_runtime.py

# Specific test class
uv run pytest tests/test_runtime.py::TestExecutionEngine

# Verbose
uv run pytest -v tests/test_runtime.py

# With coverage
uv run pytest --cov=voodoo --cov-report=term-missing

# Contract tests (with service running)
VOODOO_TEST_REDIS_URL="redis://localhost:6379" uv run pytest tests/contracts/test_queue_redis.py -v
```

### Step 6: Fix Failures

1. Read the failure output carefully.
2. Use `--tb=short` for concise tracebacks (matches CI).
3. If the test reveals a real bug, fix the source code, not the test.
4. If the test is wrong, fix the test.
5. Re-run the full suite to check for regressions.

### Step 7: Quality Gate

```bash
just format && just lint && just test
```

All three must pass before committing.

---

## Test Naming Conventions

- **Test files:** `test_<module_name>.py`
- **Test classes:** `Test<FeatureName>` (PascalCase)
- **Test methods:** `test_<scenario>_<expected>` (snake_case)
  - `test_execute_with_valid_intent_returns_result`
  - `test_crash_during_running_recovers`
  - `test_agent_with_tool_calls_tool_then_returns_text`

---

## Common Pitfalls

1. **Using the singleton** — Tests must use fresh instances, not `engine` (the module-level singleton). Use `ExecutionEngine()` directly.
2. **Real API calls** — Always use `MockProvider` for AI tests. Never call real OpenAI/Anthropic APIs.
3. **Shared state** — Never share mutable state across tests. Use fixtures.
4. **Env var access** — `os.environ["VAR"]` at module level runs before skip markers. Use `os.environ.get(...)`.
5. **Modifying contract mixins** — Never modify `tests/contracts/` mixin classes. Add provider-specific tests on top.
6. **Forgetting `from __future__ import annotations`** — Required at the top of every test file.
7. **Disabling autouse fixtures** — They ensure isolation. Don't disable them.
8. **Not testing failure paths** — Every durability claim needs a failure-path test.
