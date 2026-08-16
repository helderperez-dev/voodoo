# Installation

## What it is

Voodoo is an AI-native application framework for Python. It installs as a single package with optional extras for AI providers and MCP integration.

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

You should see the installed version printed. If the command is not found, ensure `pip`'s bin directory is on your `PATH`.

## Scaffold a new project

```bash
voodoo new my_app
cd my_app
voodoo dev
```

The app starts on `http://localhost:8000` with hot-reloading enabled.

## Clean-env validation

Voodoo is designed to work from a clean environment with zero manual steps:

```bash
# In a fresh virtualenv
uv tool install voodoo-framework
voodoo new my_app
cd my_app
voodoo dev
```

No `npm`, no bundler, no configuration files required. The framework ships with everything needed to run.

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

Voodoo reads configuration from environment variables and an optional `voodoo.yaml` file:

| Variable | Default | Description |
|---|---|---|
| `VOODOO_ENV` | `development` | Environment name |
| `VOODOO_SECRET_KEY` | dev secret | JWT signing secret |
| `VOODOO_DB_PATH` | `.data/voodoo.db` | SQLite database path |
| `VOODOO_HOST` | `0.0.0.0` | Server host |
| `VOODOO_PORT` | `8000` | Server port |

See `voodoo.yaml` for full configuration options.
