# Human-in-the-Loop

> **Status:** Implemented. Durable approvals land in Sprint 17 (v1.19.0).

Voodoo treats humans as **compute participants**, not afterthoughts. The
runtime provides first-class primitives for requesting human input,
approval, and decisions — all integrated with the execution engine and
durability model.

## Core Primitives

### `ask_human()`

Pause an execution and request a human response:

```python
from voodoo.runtime import ask_human

result = await ask_human(
    "Should we proceed with deploying to production?",
    options=["yes", "no", "needs-review"],
)
```

The execution enters `WAITING_FOR_HUMAN` status. When the human
responds, the execution resumes with the answer.

### `Approval`

For binary approve/deny flows, use the `Approval` system:

```python
from voodoo.runtime import Approval, ApprovalStatus

# Within an execution, request approval
approval = await engine.request_approval(
    title="Deploy to production",
    description="Release v2.0.0 to production environment",
    requested_by="deploy-bot",
)

# The approval is persisted — it survives process restarts
# A human can decide via CLI, API, or UI
```

### `Task(human=True)`

Mark a task as requiring human execution:

```python
from voodoo import task


@task(human=True)
async def review_pull_request(pr_id: int):
    """This task is assigned to a human, not a worker."""
    pass
```

## Approving via CLI

```bash
# List pending approvals
voodoo approvals

# Approve or deny
voodoo approvals approve <id>
voodoo approvals deny <id>
```

## Durability

Approvals are persisted to the execution store. If the worker process
dies while waiting for a human decision:

1. The execution is saved as `WAITING_FOR_HUMAN`
2. On restart, `voodoo recover` restores it
3. The human can approve/deny via CLI on any machine
4. The execution resumes on whichever worker picks it up

> **Sprint 17 (v1.19.0)** will make `WAITING_FOR_HUMAN` executions
> fully resumable across workers — no requirement for the original
> worker process to be alive.

## Integration with Agents

Agents can request human input as part of their execution loop:

```python
from voodoo import Agent, tool
from voodoo.runtime import ask_human


@tool
async def risky_operation(action: str) -> str:
    """An operation that requires human confirmation."""
    decision = await ask_human(
        f"Confirm action: {action}",
        options=["proceed", "cancel"],
    )
    if decision == "proceed":
        return f"Executed: {action}"
    return f"Cancelled: {action}"


agent = Agent(
    model="openai:gpt-4o",
    tools=["risky_operation"],
    system_prompt="You are a cautious operations assistant.",
)
```

## See Also

- [Runtime Engine](runtime.md)
- [Agents](agents.md)
- [Tools](tools.md)
- [ROADMAP.md §50 — Human-in-the-Loop](../ROADMAP.md)
