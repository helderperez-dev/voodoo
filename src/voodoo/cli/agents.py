"""voodoo agents — list and inspect registered agents.

Reads from the agent registry (SQLite by default). Falls back to
in-memory state when no durable store is available.
"""

from __future__ import annotations

import typer

from voodoo.cli import terminal

agents_app = typer.Typer(
    name="agents",
    help="List and inspect registered agents.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


def _get_registry():
    """Return an AgentRegistry — SQLite by default."""
    from voodoo.agents.registry import SQLiteAgentRegistry
    from voodoo.config import config

    db_path = config.db_path.replace(":memory:", ".voodoo/state/data.db").replace(
        "data.db", "agents.db"
    )
    try:
        return SQLiteAgentRegistry(db_path)
    except Exception:
        return None


@agents_app.command("list")
def list_agents(
    state_filter: str = typer.Option(None, "--state", help="Filter by state"),
    limit: int = typer.Option(20, "--limit", help="Maximum rows"),
    json_mode: bool = typer.Option(False, "--json", help="Machine-readable JSON"),
):
    """List registered agents."""
    import asyncio

    registry = _get_registry()
    if registry is None:
        if json_mode or terminal.is_json_mode():
            terminal.json_output({"error": "cannot open agent registry"})
            return
        terminal.wordmark()
        terminal.blank()
        terminal.muted("cannot open agent registry")
        return

    async def _list():
        agents = await registry.list_agents(state=state_filter, limit=limit)
        if json_mode or terminal.is_json_mode():
            terminal.json_output([a.to_dict() for a in agents])
            return
        terminal.wordmark()
        terminal.blank()
        if not agents:
            terminal.muted("no agents registered")
            return
        for a in agents:
            terminal.info(f"  {a.agent_id}")
            terminal.muted(f"    name: {a.name}")
            terminal.muted(f"    model: {a.model}")
            terminal.muted(f"    state: {a.state}")
            terminal.muted(f"    capabilities: {', '.join(a.capabilities) or 'none'}")
            terminal.muted(f"    tools: {', '.join(a.tools) or 'none'}")
            terminal.blank()

    asyncio.run(_list())
    registry.close()


@agents_app.command("show")
def show_agent(
    agent_id: str = typer.Argument(help="Agent ID to inspect"),
    limit: int = typer.Option(10, "--limit", help="Maximum run history"),
    json_mode: bool = typer.Option(False, "--json", help="Machine-readable JSON"),
):
    """Show agent details and recent run history."""
    import asyncio

    registry = _get_registry()
    if registry is None:
        if json_mode or terminal.is_json_mode():
            terminal.json_output({"error": "cannot open agent registry"})
            return
        terminal.wordmark()
        terminal.blank()
        terminal.muted("cannot open agent registry")
        return

    async def _show():
        entity = await registry.get(agent_id)
        if entity is None:
            if json_mode or terminal.is_json_mode():
                terminal.json_output({"error": f"agent '{agent_id}' not found"})
                return
            terminal.wordmark()
            terminal.blank()
            terminal.error(f"agent '{agent_id}' not found")
            return

        runs = await registry.get_runs(agent_id, limit=limit)
        run_count = await registry.count_runs(agent_id)

        if json_mode or terminal.is_json_mode():
            terminal.json_output(
                {
                    "agent": entity.to_dict(),
                    "total_runs": run_count,
                    "recent_runs": [r.to_dict() for r in runs],
                }
            )
            return

        terminal.wordmark()
        terminal.blank()
        terminal.info(f"Agent: {entity.name or entity.agent_id}")
        terminal.muted(f"  ID:          {entity.agent_id}")
        terminal.muted(f"  Model:       {entity.model}")
        terminal.muted(f"  State:       {entity.state}")
        terminal.muted(f"  Description: {entity.description or 'none'}")
        terminal.muted(f"  Capabilities: {', '.join(entity.capabilities) or 'none'}")
        terminal.muted(f"  Tools:       {', '.join(entity.tools) or 'none'}")
        terminal.muted(f"  Created:     {entity.created_at}")
        terminal.muted(f"  Updated:     {entity.updated_at}")
        terminal.blank()
        terminal.info(f"Run history ({run_count} total, showing {len(runs)}):")
        if not runs:
            terminal.muted("  no runs recorded")
        for r in runs:
            terminal.muted(
                f"  {r.run_id[:8]}  {r.status:10s}  "
                f"in={r.tokens_in} out={r.tokens_out} "
                f"cost=${r.cost:.4f}  tools={len(r.tool_calls)}"
            )

    asyncio.run(_show())
    registry.close()
