# Agents

## What it is

The `Agent` is a provider-driven execution loop: prompt → LLM → tool calls → final answer. Agents sit next to `Button` and `Card` as first-class application primitives.

## Minimal example

```python
from voodoo import Agent

agent = Agent(model="mock:test")
run = await agent.run("What is 2 + 2?")

print(run.output)  # "Mock response to: What is 2 + 2?"
print(run.status)  # "completed"
print(run.tokens_in)  # token count
print(run.cost)  # 0.0 (mock provider)
```

## Common usage

### With a real provider

```python
agent = Agent(model="openai:gpt-4o")
run = await agent.run("Summarize this article")
```

### With tools

```python
from voodoo import Agent, tool


@tool
async def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"Sunny in {city}"


agent = Agent(
    model="openai:gpt-4o",
    tools=["get_weather"],
)
run = await agent.run("What's the weather in Tokyo?")
print(run.tool_calls)  # list of tool call records
```

### With a system prompt

```python
agent = Agent(
    model="openai:gpt-4o",
    system_prompt="You are a helpful customer support agent.",
)
```

### Streaming

```python
async for event in agent.stream("Tell me a story"):
    if event.type == "text":
        print(event.data["text"], end="")
    elif event.type == "completed":
        print(f"\nTokens: {event.data['tokens_out']}")
```

## Advanced

### Agent lifecycle states

`created → configured → running → tool_call ⇄ thinking → completed | error → failed`

### AgentRun record

```python
run = await agent.run("prompt")
run.run_id  # unique run ID
run.model  # provider:model string
run.tokens_in  # input token count
run.tokens_out  # output token count
run.cost  # cost in USD
run.tool_calls  # list of {name, arguments, result, latency_ms}
run.timings  # {total_ms, iterations}
run.trace_id  # correlation ID (from telemetry)
```

### Provider resolution

Model strings follow the `provider:model` pattern:

- `openai:gpt-4o`
- `anthropic:claude-3-opus`
- `gemini:gemini-1.5-pro`
- `ollama:llama3`
- `mock:test` (deterministic, no network)

### Routing aliases

Instead of a hard-coded model, reference a capability alias resolved from
configuration + model descriptors:

- `best`, `fast`, `cheap`, `vision`, `reasoning`

```python
from voodoo.ai import get_provider, resolve_model

resolve_model("best")  # ("openai", "gpt-4o")
provider = get_provider("best")  # OpenAIProvider(model="gpt-4o")
```

Aliases resolve through the `models.aliases` block in `voodoo.yaml` first,
then built-in defaults:

```yaml
models:
  default: "openai:gpt-4o"
  aliases:
    best: "anthropic:claude-3-opus"
    cheap: "openai:gpt-4o-mini"
```

### Config-driven providers (`[ai]` block) — zero-code endpoints

Any OpenAI-compatible endpoint (DeepSeek, OpenRouter, Together, …) is
configured entirely in `voodoo.toml`/`voodoo.yaml` — no provider class, no
SDK wiring, no code:

```toml
[ai]
provider = "openai"                                # the OpenAI-compatible client
model = "deepseek-v4-flash"
base_url = "${DEEPSEEK_BASE_URL:-https://api.deepseek.com/v1}"
api_key = "${DEEPSEEK_API_KEY}"
aliases = { agent = "openai:deepseek-v4-flash" }
```

With that block, `Agent()` (no `model` argument) resolves everything from
config: `default_model()` prefers `ai.model` + `ai.provider`; `get_provider()`
applies `ai.base_url`/`ai.api_key` as fallback kwargs. Env vars
`VOODOO_AI_PROVIDER` / `_MODEL` / `_BASE_URL` / `_API_KEY` are the fallbacks
when the file has no `[ai]` block. `ai.aliases` merge into routing.

### Multi-turn conversations

`Agent.run()` / `Agent.stream()` accept a `history` of prior turns
(`Message` dicts) prepended before the new prompt:

```python
history = [
    {"role": "user", "content": "My name is Ana."},
    {"role": "assistant", "content": "Hello Ana!"},
]
run = await agent.run("What is my name?", history=history)
```

### Native tool calling

Providers surface structured tool-call requests via
`ProviderResponse.tool_calls` (`ToolCall(name, arguments, id)`), and the
agent builds native follow-up messages (assistant `tool_calls` + `tool` role
echoing `tool_call_id`), so OpenAI/Anthropic-style APIs map tool results
correctly. The legacy `[TOOL: name]` text marker remains only as the
mock-provider fallback.

### The `VoodooModelProvider` interface

Every model provider conforms to a normalized interface (spec gap #7):

```python
from voodoo.ai.providers import VoodooModelProvider

# generate() -> ProviderResponse        (alias of complete)
# stream()  -> AsyncIterator[ProviderEvent]
# embed(texts) -> EmbeddingResponse     (embedding-capable providers only)
# count_tokens(messages) -> int         (optional; word-count default)
# describe() -> ModelDescriptor         (capability matrix)
```

`describe()` returns a `ModelDescriptor` — provider, model, modalities,
context window, tool use, structured output, streaming, reasoning, vision,
audio, embeddings, and pricing metadata:

```python
from voodoo.ai import describe_model

desc = describe_model("mock:test")
desc.provider  # "mock"
desc.streaming  # True
desc.embeddings  # True
desc.qualified_name  # "mock:test"
```

### `voodoo generate`

```bash
voodoo generate agent "A lead-scoring agent"
```

Resolves the model through the provider abstraction (no direct SDK use). Set
`VOODOO_MODELS_DEFAULT` to pick a different model, or `OPENAI_API_KEY` /
`OPENROUTER_API_KEY` to authenticate.

### Agent memory (Sprint 16)

Every `Agent` has a `memory` property — a `MemoryStore` instance for durable,
queryable recall. Memories are distinct from context: context is what you pass
into a single run; memory is what the agent persists across runs.

```python
from voodoo import Agent, MemoryLayer

agent = Agent(model="mock:test")

# Agent auto-writes episodic memory after every run/stream
run = await agent.run("What is 2 + 2?")

# Read the agent's episodic memories
entries = await agent.memory.list_entries(
    entity_id=f"agent:{agent.agent_id}",
    layer=MemoryLayer.EPISODIC,
)
print(entries[0].content)  # "Prompt: What is 2 + 2? → Mock response..."
```

**Automatic episodic memory:** After every `run()` or `stream()`, the agent
writes an `EPISODIC` memory entry summarizing the prompt, response, tool calls,
and execution metadata. This happens without any manual wiring.

**Custom memory store:** Inject a `SQLiteMemoryStore` for durable persistence:

```python
from voodoo import Agent, SQLiteMemoryStore

agent = Agent(
    model="openai:gpt-4o",
    memory=SQLiteMemoryStore("agent_memory.db"),
)
```

**Search:** Find relevant memories with full-text search:

```python
results = await agent.memory.search(
    "pricing discussion", entity_id=f"agent:{agent.agent_id}"
)
```

### Agent registry (Sprint 17)

Agents are **durable entities** — their identity, configuration, tools,
capabilities, and run history survive process restarts. The `AgentRegistry`
Protocol provides `InMemoryAgentRegistry` (tests) and `SQLiteAgentRegistry`
(production, WAL mode).

**Auto-registration:** An agent with `agent_id` and `agent_registry` is
automatically registered on its first `run()` or `stream()`:

```python
from voodoo import Agent, SQLiteAgentRegistry

registry = SQLiteAgentRegistry("agents.db")
agent = Agent(
    model="openai:gpt-4o",
    agent_id="lead-scorer",
    name="Lead Scorer",
    tools=["get_lead", "update_lead"],
    capabilities=["scoring.read"],
    agent_registry=registry,
)

# First run auto-registers the agent + records run history
run = await agent.run("Score lead #42")

# Inspect the persisted entity
entity = await registry.get("lead-scorer")
print(entity.name)  # "Lead Scorer"
print(entity.state)  # "active"
print(entity.capabilities)  # ["scoring.read"]

# Review run history
runs = await registry.get_runs("lead-scorer")
print(runs[0].prompt)  # "Score lead #42"
print(runs[0].status)  # "completed"
```

**Run history:** Every `run()` and `stream()` persists an `AgentRunRecord`
linking the agent to its execution, tokens, cost, tool calls, and trace ID:

```python
for run in await registry.get_runs("lead-scorer"):
    print(f"{run.run_id}: {run.status} ({run.tokens_in + run.tokens_out} tokens)")
```

**Multi-agent collaboration:** Multiple agents share a registry and produce
distinct, queryable histories:

```python
registry = SQLiteAgentRegistry("agents.db")

scorer = Agent(model="openai:gpt-4o", agent_id="scorer", agent_registry=registry)
emailer = Agent(model="openai:gpt-4o", agent_id="emailer", agent_registry=registry)

await scorer.run("Score all new leads")
await emailer.run("Send follow-up emails to hot leads")

# Each agent has its own run history
print(await registry.count_agents())  # 2
print(await registry.count_runs("scorer"))  # 1
print(await registry.count_runs("emailer"))  # 1
```

**CLI inspection:**

```bash
voodoo agents list              # list all registered agents
voodoo agents list --state active  # filter by state
voodoo agents list --json       # JSON output
voodoo agents show <agent-id>   # inspect agent details + recent runs
voodoo agents show <agent-id> --limit 20  # more run history
```

## API reference

- `Agent(model, tools=None, system_prompt=None, registry=None, max_iterations=10, agent_id=None, name=None, agent_registry=None, memory=None)` — create an agent.
- `Agent.memory` — the agent's `MemoryStore` (lazy, defaults to `InMemoryMemoryStore`).
- `Agent.run(prompt, context=None) -> AgentRun` — execute to completion.
- `Agent.stream(prompt, context=None) -> AsyncIterator[AgentEvent]` — stream events.
- `AgentRun` — full run record with token/cost accounting.
- `AgentEvent` — streaming event (`type`, `data`).
- `AgentEntity` — durable agent identity (id, name, model, tools, capabilities, state).
- `AgentRunRecord` — run history record linking an agent to an execution.
- `AgentRegistry` — Protocol for agent persistence (`register`, `get`, `list_agents`, `update`, `delete`, `record_run`, `get_runs`).
- `InMemoryAgentRegistry` — in-memory registry for tests.
- `SQLiteAgentRegistry(path)` — durable SQLite registry (WAL mode).
- `VoodooModelProvider` — normalized model provider Protocol.
- `ModelDescriptor` — static model capability descriptor.
- `get_provider(model)`, `resolve_model(model)`, `describe_model(model)` — model resolution helpers.
