# Installation

## What it is

Voodoo is a programmable runtime for adaptive applications and operational systems. It installs as a single package with optional extras for AI providers and MCP integration.

## Quick install

```bash
pip install voodoo-framework
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv tool install voodoo-framework
```

## Optional extras

Voodoo keeps the core install lean. AI provider SDKs are lazy — install only what you need:

```bash
pip install "voodoo-framework[ai]"      # OpenAI, Anthropic, Gemini, Ollama SDKs
pip install "voodoo-framework[mcp]"     # MCP-specific dependencies
pip install "voodoo-framework[dev]"     # pytest, ruff, mypy, pre-commit
pip install "voodoo-framework[ai,dev]" # combine extras
```

## Verify the install

```bash
voodoo version
```

## Scaffold a new project

```bash
voodoo new my_app
cd my_app
voodoo dev
```

The app starts on `http://localhost:8000` with hot-reloading enabled.

`voodoo new` is the canonical scaffold and creates the supported Store-first
application shape. Durable tasks, schedules, events, objects, and agents are
added through the same Runtime as the application grows. The hidden
`voodoo create` command remains a compatibility alias for the deprecation
window and emits a warning.

```
my_app/
├── main.py              # App entry point — full runtime demo
├── voodoo.toml          # Runtime configuration
├── pyproject.toml       # Python project metadata
├── app/                 # Folder-based routes (add page.py files here)
└── .voodoo/
    └── application.vstore  # Local durable Store state
```

> **Tip:** Keep the generated project minimal and add capabilities as they are
> needed; this keeps the first deployment surface understandable.

No `main.py`, no `.env`, no placeholder directories, no infrastructure configuration. Capabilities like database, storage, workers, and AI activate lazily when used.

## AI development context (optional)

```bash
voodoo ai init              # auto-detect IDE
voodoo ai init --ide cursor # specific IDE
voodoo ai init --ide all    # all supported IDEs
```

Generates `.voodoo/ai/` context docs and IDE-specific rule files. Removing `.voodoo/ai` never breaks the application.

## Python version

Voodoo requires Python 3.12 or later.

## Development setup

For contributing to Voodoo itself:

```bash
git clone <repo-url>
cd voodoo
pip install -e ".[dev]"
pre-commit install
pytest
```

## Configuration

Voodoo reads configuration from `voodoo.toml` (preferred), `voodoo.yaml` (compatibility), and environment variables.

**Precedence:** `voodoo.toml` > `voodoo.yaml` > environment variables > defaults

Minimal `voodoo.toml`:

```toml
[app]
name = "my_app"
```

Environment variables:

| Variable | Default | Description |
|---|---|---|
| `VOODOO_ENV` | `development` | Environment name |
| `VOODOO_DEBUG` | `true` (dev) | Debug mode |
| `VOODOO_SECRET_KEY` | dev secret | JWT signing secret |
| `VOODOO_JWT_ISSUER` | unset | Optional exact JWT issuer claim |
| `VOODOO_JWT_AUDIENCE` | unset | Optional exact JWT audience claim |
| `VOODOO_JWT_CLOCK_SKEW` | `0` | Accepted clock drift in seconds, bounded to 300 |
| `VOODOO_JWT_PREVIOUS_SECRETS` | unset | Comma-separated old signing secrets during rotation |
| `VOODOO_JWT_REVOCATION_MAX` | `10000` | Maximum process-local revoked-token entries |
| `VOODOO_DB_PATH` | `.voodoo/state/data.db` | SQLite database path |
| `DATABASE_URL` | — | Database URL (overrides path) |
| `VOODOO_HOST` | `0.0.0.0` | Server host |
| `VOODOO_PORT` | `8000` | Server port |

Infrastructure configuration (database provider, storage provider, etc.) is optional — Voodoo provides intelligent defaults.
