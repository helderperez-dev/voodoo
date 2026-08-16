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

## API reference

- `Agent(model="mock:test", tools=None, system_prompt=None, registry=None, max_iterations=10)` — create an agent.
- `Agent.run(prompt, context=None) -> AgentRun` — execute to completion.
- `Agent.stream(prompt, context=None) -> AsyncIterator[AgentEvent]` — stream events.
- `AgentRun` — full run record with token/cost accounting.
- `AgentEvent` — streaming event (`type`, `data`).
