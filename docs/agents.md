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

## API reference

- `Agent(model="mock:test", tools=None, system_prompt=None, registry=None, max_iterations=10)` — create an agent.
- `Agent.run(prompt, context=None) -> AgentRun` — execute to completion.
- `Agent.stream(prompt, context=None) -> AsyncIterator[AgentEvent]` — stream events.
- `AgentRun` — full run record with token/cost accounting.
- `AgentEvent` — streaming event (`type`, `data`).
- `VoodooModelProvider` — normalized model provider Protocol.
- `ModelDescriptor` — static model capability descriptor.
- `get_provider(model)`, `resolve_model(model)`, `describe_model(model)` — model resolution helpers.
