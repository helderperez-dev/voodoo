"""Agent — provider-driven execution loop with tool calling.

The Agent turns a prompt into a final answer by iterating:

    prompt → provider → tool calls (via registry) → final

``run()`` returns a full :class:`AgentRun` record with token/cost accounting;
``stream()`` yields normalized :class:`AgentEvent` objects so the UI can react
to agent activity in real time. Lifecycle states (created → configured →
running → tool_call ⇄ thinking → completed | error → retry/failed) are
captured for telemetry and surfaced through mesh events (S7-2).

The ``context`` parameter is an explicit, opaque dict passed to every tool
call; it is neither memory nor a database — keep the concepts separate.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from voodoo.ai.providers import LLMProvider, Message, default_model, get_provider
from voodoo.tools.registry import ToolRegistry, default_registry

__all__ = ["Agent", "AgentRun", "AgentEvent"]

# Lazy import for memory — avoids circular deps and keeps memory optional.
_memory_store_cls = None


def _get_memory_store_class() -> Any:
    """Resolve the default memory store class (lazy)."""
    global _memory_store_cls
    if _memory_store_cls is None:
        from voodoo.memory.interfaces import InMemoryMemoryStore

        _memory_store_cls = InMemoryMemoryStore
    return _memory_store_cls


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class AgentState(StrEnum):
    created = "created"
    configured = "configured"
    running = "running"
    tool_call = "tool_call"
    thinking = "thinking"
    completed = "completed"
    error = "error"
    retry = "retry"
    failed = "failed"


# ---------------------------------------------------------------------------
# Records & events
# ---------------------------------------------------------------------------


@dataclass
class AgentRun:
    """Full run record with token/cost accounting."""

    run_id: str
    model: str
    provider: str
    prompt: str
    output: str
    timings: dict[str, float] = field(default_factory=dict)
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0.0
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    status: str = "completed"
    error: str | None = None
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    trace_id: str | None = None


@dataclass
class AgentEvent:
    """Normalized streaming event.

    ``type`` is one of: ``text``, ``tool_started``, ``tool_finished``,
    ``thinking``, ``error``, ``completed``.
    """

    type: str
    data: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class Agent:
    """Agent with provider-driven execution and tool calling.

    Parameters
    ----------
    model:
        ``"provider:model"`` string resolved via :func:`get_provider`. When
        omitted, the configured default (the ``ai`` block or
        ``models.default`` in ``voodoo.toml``/``voodoo.yaml``) is used.
    tools:
        List of :class:`ToolSpec` objects or tool names registered in the
        chosen registry. ``None`` means "no tools available".
    system_prompt:
        Optional system message prepended to the message list.
    registry:
        Tool registry used for tool lookup; defaults to the global registry.
    max_iterations:
        Maximum tool-call iterations before forcing a final answer.
    memory:
        Memory store for durable entity state. When ``None``, an
        :class:`~voodoo.memory.interfaces.InMemoryMemoryStore` is created
        lazily on first access. Context is NOT memory — context is an
        opaque dict passed to tool calls; memory is a queryable, durable
        record of what the entity knows.
    agent_id:
        Stable identity for this agent. When provided with an
        ``agent_registry``, the agent is auto-registered and run history
        is persisted. Auto-generated UUID if not provided.
    name:
        Human-readable display name for registry entry.
    agent_registry:
        :class:`~voodoo.agents.registry.AgentRegistry` for durable
        identity and run history. When ``None``, run history is not
        persisted (memory episodic entries still write).
    """

    def __init__(
        self,
        model: str | None = None,
        tools: list[Any] | None = None,
        system_prompt: str | None = None,
        registry: ToolRegistry | None = None,
        max_iterations: int = 10,
        capabilities: list[str] | None = None,
        memory: Any | None = None,
        agent_id: str | None = None,
        name: str = "",
        agent_registry: Any | None = None,
        **provider_kwargs: Any,
    ) -> None:
        self.model = model or default_model()
        self.system_prompt = system_prompt
        self.registry = registry or default_registry
        self.max_iterations = max_iterations
        # Capability names granted to this agent. Tools that declare
        # ``permissions`` require a matching grant (or an active runtime
        # execution context holding the capability) before they execute.
        self.capabilities: list[str] = list(capabilities) if capabilities else []
        self.state: AgentState = AgentState.created
        self.provider: LLMProvider = get_provider(self.model, **provider_kwargs)
        self._memory: Any | None = memory

        # Agent identity (Sprint 17).
        self.agent_id: str = agent_id or str(uuid.uuid4())
        self.name: str = name
        self._agent_registry: Any | None = agent_registry
        self._registered: bool = False

        # Resolve tool specs/names into a list of names for tool calling.
        self._tool_names: list[str] = []
        if tools:
            for t in tools:
                if isinstance(t, str):
                    self._tool_names.append(t)
                elif hasattr(t, "name"):
                    self._tool_names.append(t.name)
                elif hasattr(t, "__tool_spec__"):
                    self._tool_names.append(t.__tool_spec__.name)

        self.state = AgentState.configured

    # -- agent registry (Sprint 17) ----------------------------------------

    async def _ensure_registered(self) -> None:
        """Auto-register this agent in the agent registry (lazy)."""
        if self._agent_registry is None or self._registered:
            return
        from voodoo.agents.models import AgentEntity

        existing = await self._agent_registry.get(self.agent_id)
        if existing is None:
            entity = AgentEntity(
                agent_id=self.agent_id,
                name=self.name or self.agent_id,
                model=self.model,
                system_prompt=self.system_prompt,
                capabilities=list(self.capabilities),
                tools=list(self._tool_names),
            )
            await self._agent_registry.register(entity)
        self._registered = True

    async def _record_run(self, run_record: AgentRun) -> None:
        """Persist a run record to the agent registry."""
        if self._agent_registry is None:
            return
        from voodoo.agents.models import AgentRunRecord

        await self._ensure_registered()
        record = AgentRunRecord(
            run_id=run_record.run_id,
            agent_id=self.agent_id,
            execution_id=run_record.trace_id,
            prompt=run_record.prompt,
            output=run_record.output,
            status=run_record.status,
            tokens_in=run_record.tokens_in,
            tokens_out=run_record.tokens_out,
            cost=run_record.cost,
            tool_calls=run_record.tool_calls,
            started_at=run_record.started_at,
            completed_at=run_record.completed_at,
            trace_id=run_record.trace_id,
        )
        await self._agent_registry.record_run(record)

    # -- memory ------------------------------------------------------------

    @property
    def memory(self) -> Any:
        """The memory store for this agent.

        Lazily creates an :class:`~voodoo.memory.interfaces.InMemoryMemoryStore`
        if no store was provided at construction time. This is NOT context —
        context is an opaque dict passed to tool calls; memory is a queryable,
        durable record of what the entity knows.
        """
        if self._memory is None:
            from voodoo.memory.interfaces import InMemoryMemoryStore

            self._memory = InMemoryMemoryStore()
        return self._memory

    @memory.setter
    def memory(self, store: Any) -> None:
        self._memory = store

    async def _write_episodic_memory(self, run_record: AgentRun) -> None:
        """Write episodic memory entries derived from a completed run.

        Each run produces a summary memory entry capturing the prompt, output,
        tool calls, and token accounting. This is Layer 1 (episodic) — the
        execution-derived record of what happened.
        """
        from voodoo.memory.interfaces import MemoryEntry, MemoryLayer

        tool_summary = ""
        if run_record.tool_calls:
            names = [tc["name"] for tc in run_record.tool_calls]
            tool_summary = f" Tools used: {', '.join(names)}."

        content = (
            f"Run {run_record.run_id}: {run_record.prompt[:200]} "
            f"→ {run_record.output[:200]}.{tool_summary}"
        )

        entry = MemoryEntry(
            entity_id="agent",
            layer=MemoryLayer.EPISODIC,
            content=content,
            metadata={
                "run_id": run_record.run_id,
                "model": run_record.model,
                "provider": run_record.provider,
                "tokens_in": run_record.tokens_in,
                "tokens_out": run_record.tokens_out,
                "cost": run_record.cost,
                "status": run_record.status,
                "tool_count": len(run_record.tool_calls),
            },
            tags=["agent-run", run_record.provider],
            source_execution_id=run_record.run_id,
            importance=0.6,
        )
        try:
            self.memory.write(entry)
        except Exception:  # noqa: BLE001 — memory writes never break the run
            pass

    # -- helpers -----------------------------------------------------------

    def _build_messages(
        self,
        prompt: str,
        context: dict | None = None,
        history: list[Message] | None = None,
    ) -> list[Message]:
        messages: list[Message] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        if context:
            messages.append(
                {
                    "role": "system",
                    "content": f"Context: {context}",
                }
            )
        # Prior turns (multi-turn conversation) precede the new user message.
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})
        return messages

    def _tools_for_provider(self) -> list[dict[str, Any]] | None:
        if not self._tool_names:
            return None
        specs = []
        for name in self._tool_names:
            spec = self.registry.get(name)
            if spec:
                specs.append(
                    {
                        "name": spec.name,
                        "description": spec.description,
                        "input_schema": spec.input_schema,
                    }
                )
        return specs or None

    async def _execute_tool_call(self, name: str, arguments: dict[str, Any]) -> Any:
        """Invoke a registered tool through the runtime authorization path.

        Flow: Agent → Intent → capability check → Tool → Effect → Mesh.
        Tools that declare ``permissions`` require a matching capability,
        granted either to this agent or held by the active runtime
        :class:`~voodoo.runtime.context.ExecutionContext`. Unauthorized
        tool calls are denied before any side effect executes.
        """
        from voodoo.primitives.effect import Effect
        from voodoo.runtime.context import current_context

        spec = self.registry.get(name)
        required = list(spec.permissions) if spec else []

        ctx = current_context()
        held = (
            {c.name for c in ctx.capabilities if c.valid}
            if ctx
            else set(self.capabilities)
        )
        missing = [p for p in required if p not in held]
        if missing:
            effect = Effect(
                name=f"tool.{name}",
                capability_name=required[0] if required else None,
            )
            effect.mark_failed(f"capability denied: {', '.join(missing)}")
            if ctx is not None:
                ctx.add_effect(effect)
            await self._broadcast(
                "tool.called",
                {"tool": name, "arguments": arguments, "denied": missing},
            )
            return {
                "error": f"CapabilityDenied: tool '{name}' requires "
                f"{', '.join(missing)}"
            }

        effect = Effect(
            name=f"tool.{name}", capability_name=required[0] if required else None
        )
        await self._broadcast("tool.called", {"tool": name, "arguments": arguments})
        try:
            result = await self.registry.call(name, **arguments)
        except Exception as e:  # noqa: BLE001 — capture for telemetry
            effect.mark_failed(str(e))
            if ctx is not None:
                ctx.add_effect(effect)
            await self._broadcast(
                "tool.completed", {"tool": name, "status": "failed", "error": str(e)}
            )
            return {"error": str(e)}
        effect.mark_succeeded(result={"ok": True})
        if ctx is not None:
            ctx.add_effect(effect)
        await self._broadcast("tool.completed", {"tool": name, "status": "succeeded"})
        return result

    # -- run ---------------------------------------------------------------

    async def run(
        self,
        prompt: str,
        context: dict | None = None,
        history: list[Message] | None = None,
    ) -> AgentRun:
        """Execute prompt → provider → tool calls → final; return AgentRun.

        ``history`` prepends prior conversation turns (a list of ``Message``
        dicts) before the new user prompt, enabling multi-turn chat.
        """
        run_id = str(uuid.uuid4())
        from voodoo.telemetry import telemetry_store

        trace_id = (
            telemetry_store.trace_id_var.get()
            if hasattr(telemetry_store, "trace_id_var")
            else None
        )
        started = time.time()
        self.state = AgentState.running

        messages = self._build_messages(prompt, context, history)
        tool_calls: list[dict[str, Any]] = []
        tokens_in = 0
        tokens_out = 0
        cost = 0.0
        output = ""
        error: str | None = None
        iterations = 0

        await self._broadcast("agent.started", {"run_id": run_id, "model": self.model})

        try:
            while iterations <= self.max_iterations:
                self.state = AgentState.running
                await self._broadcast(
                    "model.called",
                    {
                        "run_id": run_id,
                        "provider": self.provider.name,
                        "model": self.model,
                    },
                )
                # Only send tools when the model advertises tool_use support.
                # Some OpenAI-compatible endpoints (e.g. LiteLLM proxies for
                # non-tool models) reject requests with unsupported params.
                try:
                    desc = self.provider.describe()
                    tools_arg = self._tools_for_provider() if desc.tool_use else None
                except Exception:  # noqa: BLE001 — best-effort capability check
                    tools_arg = self._tools_for_provider()
                response = await self.provider.complete(messages, tools=tools_arg)
                await self._broadcast(
                    "model.completed",
                    {
                        "run_id": run_id,
                        "provider": self.provider.name,
                        "model": self.model,
                        "tokens_in": response.tokens_in,
                        "tokens_out": response.tokens_out,
                        "cost": response.cost,
                    },
                )
                tokens_in += response.tokens_in
                tokens_out += response.tokens_out
                cost += response.cost

                # Check if the response requests a tool call.
                tool_request = self._extract_tool_request(response)
                if tool_request and iterations < self.max_iterations:
                    self.state = AgentState.tool_call
                    tool_name = tool_request["name"]
                    tool_args = tool_request.get("arguments", {})

                    await self._broadcast(
                        "agent.tool.started",
                        {"run_id": run_id, "tool": tool_name, "arguments": tool_args},
                    )

                    tool_start = time.time()
                    tool_result = await self._execute_tool_call(tool_name, tool_args)
                    tool_latency = (time.time() - tool_start) * 1000

                    tool_calls.append(
                        {
                            "name": tool_name,
                            "arguments": tool_args,
                            "result": tool_result,
                            "latency_ms": tool_latency,
                        }
                    )
                    telemetry_store.record_tool_call(
                        tool_name,
                        tool_latency,
                        isinstance(tool_result, dict) and "error" in tool_result,
                    )

                    await self._broadcast(
                        "agent.tool.completed",
                        {
                            "run_id": run_id,
                            "tool": tool_name,
                            "latency_ms": tool_latency,
                        },
                    )

                    self.state = AgentState.thinking
                    messages.extend(
                        self._tool_follow_up_messages(
                            tool_request=tool_request,
                            tool_result=tool_result,
                            text=response.content,
                        )
                    )
                    iterations += 1
                    continue
                else:
                    # Final answer
                    output = response.content
                    break

        except Exception as e:  # noqa: BLE001
            self.state = AgentState.error
            error = str(e)
            await self._broadcast("agent.failed", {"run_id": run_id, "error": error})
            self.state = AgentState.failed
        else:
            self.state = AgentState.completed

        completed_at = time.time()
        run_record = AgentRun(
            run_id=run_id,
            model=self.model,
            provider=self.provider.name,
            prompt=prompt,
            output=output,
            timings={
                "total_ms": (completed_at - started) * 1000,
                "iterations": iterations,
            },
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost,
            tool_calls=tool_calls,
            status=self.state.value,
            error=error,
            started_at=started,
            completed_at=completed_at,
            trace_id=trace_id,
        )

        telemetry_store.record_agent_run(run_record)
        await self._write_episodic_memory(run_record)
        await self._record_run(run_record)
        await self._broadcast(
            "agent.completed",
            {
                "run_id": run_id,
                "status": run_record.status,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "cost": cost,
            },
        )
        return run_record

    # -- stream ------------------------------------------------------------

    async def stream(  # noqa: C901
        self,
        prompt: str,
        context: dict | None = None,
        history: list[Message] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Yield normalized events: text, tool_started, tool_finished, thinking, error, completed."""
        run_id = str(uuid.uuid4())
        from voodoo.telemetry import telemetry_store

        trace_id = (
            telemetry_store.trace_id_var.get()
            if hasattr(telemetry_store, "trace_id_var")
            else None
        )
        started = time.time()
        self.state = AgentState.running

        messages = self._build_messages(prompt, context, history)
        tool_calls: list[dict[str, Any]] = []
        tokens_in = 0
        tokens_out = 0
        cost = 0.0
        output = ""
        error: str | None = None
        iterations = 0

        await self._broadcast("agent.started", {"run_id": run_id, "model": self.model})

        try:
            while iterations <= self.max_iterations:
                self.state = AgentState.running
                accumulated_text = ""
                structured_tool_request: dict[str, Any] | None = None
                await self._broadcast(
                    "model.called",
                    {
                        "run_id": run_id,
                        "provider": self.provider.name,
                        "model": self.model,
                    },
                )
                try:
                    desc = self.provider.describe()
                    tools_arg = self._tools_for_provider() if desc.tool_use else None
                except Exception:  # noqa: BLE001 — best-effort capability check
                    tools_arg = self._tools_for_provider()
                async for event in self.provider.stream(messages, tools=tools_arg):
                    if event.type == "text":
                        accumulated_text += event.data.get("text", "")
                        yield AgentEvent(type="text", data=event.data)
                    elif event.type == "tool_call":
                        structured_tool_request = {
                            "name": event.data.get("name", ""),
                            "arguments": event.data.get("arguments", {}),
                            "id": event.data.get("id"),
                        }
                    elif event.type == "done":
                        tokens_in += event.data.get("tokens_in", 0)
                        tokens_out += event.data.get("tokens_out", 0)
                        cost += event.data.get("cost", 0.0)
                    elif event.type == "error":
                        raise Exception(event.data.get("error", "Provider error"))
                await self._broadcast(
                    "model.completed",
                    {
                        "run_id": run_id,
                        "provider": self.provider.name,
                        "model": self.model,
                        "tokens_in": tokens_in,
                        "tokens_out": tokens_out,
                        "cost": cost,
                    },
                )

                # Native providers emit ``tool_call`` events; mock and legacy
                # providers encode requests as a ``[TOOL: ...]`` text marker.
                tool_request = (
                    structured_tool_request
                    or self._extract_tool_request_from_stream(accumulated_text)
                )

                if tool_request and iterations < self.max_iterations:
                    self.state = AgentState.tool_call
                    tool_name = tool_request["name"]
                    tool_args = tool_request.get("arguments", {})

                    yield AgentEvent(
                        type="tool_started",
                        data={"tool": tool_name, "arguments": tool_args},
                    )
                    await self._broadcast(
                        "agent.tool.started",
                        {"run_id": run_id, "tool": tool_name, "arguments": tool_args},
                    )

                    tool_start = time.time()
                    tool_result = await self._execute_tool_call(tool_name, tool_args)
                    tool_latency = (time.time() - tool_start) * 1000

                    tool_calls.append(
                        {
                            "name": tool_name,
                            "arguments": tool_args,
                            "result": tool_result,
                            "latency_ms": tool_latency,
                        }
                    )
                    telemetry_store.record_tool_call(
                        tool_name,
                        tool_latency,
                        isinstance(tool_result, dict) and "error" in tool_result,
                    )

                    yield AgentEvent(
                        type="tool_finished",
                        data={
                            "tool": tool_name,
                            "result": tool_result,
                            "latency_ms": tool_latency,
                        },
                    )
                    await self._broadcast(
                        "agent.tool.completed",
                        {
                            "run_id": run_id,
                            "tool": tool_name,
                            "latency_ms": tool_latency,
                        },
                    )

                    self.state = AgentState.thinking
                    yield AgentEvent(type="thinking", data={"tool": tool_name})

                    messages.extend(
                        self._tool_follow_up_messages(
                            tool_request=tool_request,
                            tool_result=tool_result,
                            text=accumulated_text,
                        )
                    )
                    iterations += 1
                    continue
                else:
                    output = accumulated_text
                    break

        except Exception as e:  # noqa: BLE001
            self.state = AgentState.error
            error = str(e)
            yield AgentEvent(type="error", data={"error": error})
            await self._broadcast("agent.failed", {"run_id": run_id, "error": error})
            self.state = AgentState.failed
        else:
            self.state = AgentState.completed

        completed_at = time.time()
        run_record = AgentRun(
            run_id=run_id,
            model=self.model,
            provider=self.provider.name,
            prompt=prompt,
            output=output,
            timings={
                "total_ms": (completed_at - started) * 1000,
                "iterations": iterations,
            },
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost,
            tool_calls=tool_calls,
            status=self.state.value,
            error=error,
            started_at=started,
            completed_at=completed_at,
            trace_id=trace_id,
        )

        telemetry_store.record_agent_run(run_record)
        await self._write_episodic_memory(run_record)
        await self._record_run(run_record)
        await self._broadcast(
            "agent.completed",
            {
                "run_id": run_id,
                "status": run_record.status,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "cost": cost,
            },
        )
        yield AgentEvent(
            type="completed",
            data={
                "run_id": run_id,
                "output": output,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "cost": cost,
                "status": run_record.status,
            },
        )

    # -- tool request extraction ------------------------------------------

    def _extract_tool_request(self, response: Any) -> dict[str, Any] | None:
        """Extract a tool-call request from a provider response.

        Prefers the native ``tool_calls`` field (ROADMAP §47); falls back to
        the legacy ``[TOOL: ...]`` text-marker convention for providers that
        return plain text (mock and older custom providers).
        """
        structured = getattr(response, "tool_calls", None)
        if structured:
            first = structured[0]
            if isinstance(first, dict):
                return {
                    "name": first.get("name", ""),
                    "arguments": first.get("arguments", {}),
                    "id": first.get("id"),
                }
            return {
                "name": getattr(first, "name", ""),
                "arguments": getattr(first, "arguments", {}),
                "id": getattr(first, "id", None),
            }
        content = getattr(response, "content", "")
        return self._parse_tool_marker(content)

    def _extract_tool_request_from_stream(self, content: str) -> dict[str, Any] | None:
        return self._parse_tool_marker(content)

    def _tool_follow_up_messages(
        self,
        tool_request: dict[str, Any],
        tool_result: Any,
        text: str = "",
    ) -> list[Message]:
        """Build the assistant/tool messages to append after a tool call.

        Native tool calls (carrying an ``id``) are echoed back in the
        provider's own format so the result maps to the originating call; the
        legacy marker convention appends a plain assistant message followed by
        a ``tool`` role message.
        """
        tool_name = tool_request["name"]
        tool_args = tool_request.get("arguments", {})
        tc_id = tool_request.get("id")
        if tc_id is not None:
            assistant_msg: Message = {
                "role": "assistant",
                "content": text,
                "tool_calls": [
                    {
                        "id": tc_id,
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": json.dumps(tool_args),
                        },
                    }
                ],
            }
            tool_msg: Message = {
                "role": "tool",
                "tool_call_id": tc_id,
                "content": str(tool_result),
            }
            return [assistant_msg, tool_msg]
        return [
            {"role": "assistant", "content": text},
            {"role": "tool", "content": str(tool_result), "name": tool_name},
        ]

    @staticmethod
    def _parse_tool_marker(content: str) -> dict[str, Any] | None:
        marker = "[TOOL:"
        if marker not in content:
            return None
        try:
            start = content.index(marker) + len(marker)
            end = content.index("]", start)
            tool_name = content[start:end].strip()
            args: dict[str, Any] = {}
            # Look for args: after the tool marker
            args_marker = "args:"
            if args_marker in content[end:]:
                args_start = content.index(args_marker, end) + len(args_marker)
                # Try to parse JSON until end of content or next marker
                remaining = content[args_start:].strip()
                # Find end of JSON (try to parse incrementally)
                try:
                    args = json.loads(remaining)
                except json.JSONDecodeError:
                    # Try to find a JSON object
                    brace_start = remaining.find("{")
                    if brace_start >= 0:
                        brace_end = remaining.rfind("}")
                        if brace_end > brace_start:
                            args = json.loads(remaining[brace_start : brace_end + 1])
            return {"name": tool_name, "arguments": args}
        except (ValueError, json.JSONDecodeError):
            return None

    # -- mesh broadcasting -------------------------------------------------

    async def _broadcast(self, event: str, payload: dict[str, Any]) -> None:
        """Publish a namespaced mesh event (best-effort, never breaks the run)."""
        try:
            from voodoo.mesh import mesh

            await mesh.broadcast(event, payload)
        except Exception:  # noqa: BLE001 — mesh is optional in tests
            pass
