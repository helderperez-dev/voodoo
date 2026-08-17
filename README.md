<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/voodoo-logo-white.png">
  <img alt="Voodoo" src="docs/assets/voodoo-logo-black.png" width="200" align="right">
</picture>

# Voodoo

**The AI-native application framework for Python.**

Build reactive UIs, APIs, agents, background workers, realtime systems, MCP tools, and data-driven applications in one Python runtime. Built for the future of adaptive applications.

> Voodoo favors composition over configuration, Python over DSLs, adapters over
> lock-in, events over tightly coupled systems, and explicit capabilities over
> unrestricted AI autonomy.

## Quick start

```bash
pip install voodoo-framework
voodoo new my_app
cd my_app
voodoo dev
```

Open `http://localhost:8000` — that's it. No npm, no bundler, no config files.

The scaffold produces only `app/page.py`, `voodoo.toml`, and `pyproject.toml` — nothing else. No `main.py`, no `.env`, no placeholder directories.

Want AI development context in your editor? Run `voodoo ai init` (opt-in, supports `--ide trae|cursor|windsurf|vscode|all`).

## The AI SaaS app

Here's a complete example exercising the full chain — UI → agent → tool → MCP → mesh → worker → database:

```python
from voodoo import (
    App,
    page,
    state,
    event,
    Agent,
    tool,
    Container,
    Heading,
    Text,
    Button,
    Card,
    Div,
    Table,
)

app = App()

# --- Data model ---
from voodoo import Model


class Lead(Model):
    name: str
    email: str
    status: str = "new"


# --- Tool (one definition, four consumers) ---
@tool
async def create_lead(name: str, email: str) -> str:
    """Create a new lead in the database."""
    lead = await Lead.create(name=name, email=email)
    return f"Created lead #{lead.id}: {name}"


# --- Agent with tool calling ---
agent = Agent(
    model="openai:gpt-4o",
    tools=["create_lead"],
    system_prompt="You are a sales assistant. Use tools to create leads.",
)

# --- Realtime mesh event ---
from voodoo.mesh import mesh


@mesh.on("lead.created")
async def notify_slack(payload):
    # Triggered when a lead is created
    print(f"New lead notification: {payload}")


# --- Reactive UI ---
leads = state([])


@page("/")
def dashboard():
    return Container(
        Heading("AI SaaS Dashboard", level=1),
        Card(
            Text("Ask the AI to create leads"),
            Button("Create Lead", onclick="vd.event('create_lead', 'btn')"),
        ),
        Div(
            Table(*leads.get()),
            id="leads-table",
        ),
    )


@event
async def create_lead(element_id, value):
    run = await agent.run("Create a lead for Ada Lovelace, ada@x.io")
    # Agent calls create_lead tool → DB insert → mesh event fires
    all_leads = await Lead.all()
    leads.set(all_leads)


if __name__ == "__main__":
    app.run()
```

## What makes Voodoo different

| Differentiator | What it means |
|---|---|
| **AI-native by design** | Agents, tools, and MCP are first-class primitives — not add-ons bolted on later |
| **Agents as application primitives** | `Agent()` sits next to `Button()` and `Card()` in your code |
| **Voodoo Mesh** | Unified event layer connecting UI, workers, agents, and applications |
| **One tool, many consumers** | A single `@tool` definition serves Python calls, agents, MCP, and mesh |
| **Observability everywhere** | Correlation IDs and telemetry built into every subsystem |
| **Zero-config runtime** | `voodoo new` → `voodoo dev` → working app. No build step. Add `voodoo.toml` when you need configuration |

## Architectural Primitives

Voodoo is built on eight fundamental computational primitives:

    State · Capability · Intent · Effect · Time · Compute · Resource · Constraint

```python
from voodoo.primitives import State, Capability, Intent, Effect
```

See [docs/primitives.md](docs/primitives.md) for the full model.

## Features

- **Reactive UI** — Component system in pure Python with WebSocket-driven DOM patches
- **Agents** — Provider-driven execution loop with tool calling (OpenAI, Anthropic, Gemini, Ollama)
- **Tools** — `@tool` decorator with auto-generated JSON schemas from type hints
- **MCP** — Built-in Model Context Protocol server; every tool is automatically exposed
- **Voodoo Mesh** — Realtime event bus with local + remote boundaries
- **Workers** — `@task` decorator with retries, timeout, and telemetry spans
- **Data** — Async SQLite ORM with RLS policies and lifecycle hooks
- **Auth** — JWT tokens, API keys, session cookies, RBAC route guards
- **Security** — CORS, CSRF, rate limiting, security headers — all on by default
- **Telemetry** — Correlation IDs, request tracking, agent token/cost accounting

## Installation

### Homebrew (macOS/Linux)

```bash
brew tap helderperez-dev/voodoo
brew install voodoo
```

### uv

```bash
uv tool install voodoo-framework
```

### Magic install script

```bash
curl -fsSL https://raw.githubusercontent.com/helderperez-dev/voodoo/main/install.sh | bash
```

### pip / pipx

```bash
# Core (lean — no AI SDKs)
pip install voodoo-framework

# With AI providers
pip install "voodoo-framework[ai]"

# With dev tools
pip install "voodoo-framework[dev]"

# Isolated environment
pipx install voodoo-framework
```

### Verify

```bash
voodoo version
```

## Uninstall

### Homebrew

```bash
brew uninstall voodoo
brew untap helderperez-dev/voodoo
```

### uv

```bash
uv tool uninstall voodoo-framework
```

### Magic install script

```bash
rm -rf ~/.voodoo/venv
rm -f ~/.local/bin/voodoo
```

### pip / pipx

```bash
pip uninstall voodoo-framework
# or
pipx uninstall voodoo-framework
```

## Documentation

- [Installation](docs/installation.md)
- [Hello World](docs/hello_world.md)
- [Components](docs/components.md)
- [Routing](docs/routing.md)
- [Reactive State](docs/state.md)
- [Events](docs/events.md)
- [Data & Models](docs/data.md)
- [Auth](docs/auth.md)
- [Agents](docs/agents.md)
- [Tools](docs/tools.md)
- [MCP](docs/mcp.md)
- [Mesh](docs/mesh.md)
- [Workers](docs/workers.md)
- [Telemetry](docs/telemetry.md)
- [Deployment](docs/deployment.md)
- [Architecture](docs/architecture.md)
- [Architectural Primitives](docs/primitives.md)

## Examples

- [`examples/hello_world/`](examples/hello_world/) — Minimal app
- [`examples/dashboard/`](examples/dashboard/) — Data dashboard
- [`examples/realtime/`](examples/realtime/) — Realtime counter
- [`examples/ai_agent/`](examples/ai_agent/) — Simple AI agent
- [`examples/ai_saas/`](examples/ai_saas/) — Full AI SaaS demo

## Testing

```bash
pytest
```

## License

MIT
