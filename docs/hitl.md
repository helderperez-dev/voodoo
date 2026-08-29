# Human-in-the-Loop

> **Status:** Fully durable (Sprint 18, v2.1.0). Waiting approvals survive
> process death and resume on any worker via registered participants.

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
# List approvals (pending and decided)
voodoo approvals list

# Only pending
voodoo approvals list --pending

# Inspect one in detail
voodoo approvals show <execution-id>

# Approve or deny — resumes the execution
voodoo approvals approve <execution-id> --by ops --note "ship it"
voodoo approvals deny <execution-id> --by admin --reason "too risky"

# Import the app first so participants re-register and the
# approved execution actually re-runs
voodoo approvals approve <execution-id> --app main:app
```

## Durability

Approvals are persisted to the execution store (`approvals` table). If the
worker process dies while waiting for a human decision:

1. The execution is saved as `WAITING_FOR_HUMAN` with a journal event
   `approval.requested`
2. On restart, `voodoo recover` restores it and rehydrates the approval
3. The human can approve/deny via CLI on any machine
4. The execution resumes **on any worker** through its registered
   participant — the original process does not need to be alive

### Durable participants (Sprint 18)

What makes a resume possible after a restart: the approval persists a
**participant name**, and the process that decides registers that name with
the engine:

```python
from voodoo import Intent
from voodoo.runtime import engine


async def deploy_compute(ctx):
    if ctx.metadata.get("approval") != "approved":
        raise ApprovalRequired("Deploy to production?")
    return "deployed"


# Register the participant — its name is the durable handle.
engine.register_participant("deploy_wf", deploy_compute)
await engine.execute(Intent(name="deploy"), deploy_compute)
# → execution waits; approval persisted with participant="deploy_wf"
```

After a crash, on any machine:

```bash
voodoo approvals list --pending
voodoo approvals approve <execution-id> --by ops --app main:app
# → imports main.py (re-registers "deploy_wf"), resumes, completes
```

Decisions are journaled: `approval.requested` on wait,
`approval.granted` / `approval.denied` on decide.

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
