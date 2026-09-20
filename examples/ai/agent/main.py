"""Simple AI Agent — an agent that uses the mock provider (no network needed).

Run: python main.py  or  voodoo dev
"""

from voodoo import (
    Agent,
    App,
    Button,
    Card,
    Container,
    Heading,
    Text,
    event,
    page,
    state,
    tool,
)

app = App()


# A tool the agent can call
@tool
async def get_time() -> str:
    """Get the current time."""
    from datetime import datetime

    return datetime.now().strftime("%H:%M:%S")


# Agent with the mock provider (no network, deterministic)
agent = Agent(
    model="mock:test",
    tools=["get_time"],
)

result = state("Click to run the agent")


@page("/")
def home():
    return Container(
        Heading("AI Agent Demo", level=1),
        Card(
            Text(f"Result: {result.get()}", id="result-text"),
            Button("Run Agent", onclick="vd.event('run_agent', 'result-text')"),
        ),
    )


@event
async def run_agent(element_id, value):
    run = await agent.run("What time is it?")
    result.set(run.output)


if __name__ == "__main__":
    app.run()
