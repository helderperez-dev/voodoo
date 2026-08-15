# Voodoo Framework 🪄

**The Modern, Full-Stack Async Python Web Framework.**

Voodoo is an ultra-minimalist, high-performance web framework designed for the AI era. Built on top of Starlette and Uvicorn, it offers a seamless, reactive developer experience by combining a React-like component system in pure Python with robust backend features like background queues, real-time websockets, LLM agents, and built-in SQLite persistence.

## ✨ Features

- **Component-Driven UI**: Build modern, reactive UIs using pure Python components (`Div`, `Card`, `Button`, `Text`) with TailwindCSS integration out of the box. No writing raw HTML/JS required.
- **Native Authentication & Security**: Complete identity system with PBKDF2 password hashing, HS256 JWT tokens, API keys, session cookies, RBAC route guards (`@login_required`, `@requires_role`), CSRF protection, rate limiting, and security headers.
- **Native SEO Engine**: Built-in support for dynamic `sitemap.xml`, `robots.txt`, OpenGraph tags, Twitter Cards, and JSON-LD structured data.
- **Semantic HTML**: Fully accessible HTML5 hierarchy (`Article`, `Nav`, `Section`, `Header`, `Main`) enforcing best-practices out of the box.
- **Voodoo Mesh**: Real-time events network (`voodoo.mesh`) bridging WebSocket broadcasting, local event handling, and automatic MCP tooling for AI IDEs.
- **Data Persistence**: Built-in async SQLite (`aiosqlite`) ORM using Pydantic models with Row-Level Security (RLS) policies.
- **Background Workers**: Native task queues for heavy processing, ideal for AI/LLM workloads.
- **AI Native**: Built-in support for LLM Agents, Model Context Protocol (MCP), and multi-IDE configuration sync (Trae, Cursor, Windsurf, Copilot).
- **Observability**: Integrated Telemetry and APM tracing module tracking latencies, metrics, and AI token usage.
- **Modern CLI**: Developer toolkit featuring `voodoo new`, `voodoo dev`, `voodoo routes`, `voodoo doctor`, `voodoo auth`, `voodoo generate`, and `voodoo version`.

## 🚀 Getting Started

Voodoo is designed to be installed globally on your machine so you can scaffold new projects anywhere in seconds. We provide multiple effortless installation methods.

### 🍎 Method 1: Homebrew (macOS / Linux) - *Recommended*

The cleanest and most native way to install Voodoo globally:

```bash
brew install helderperez-dev/voodoo/voodoo
```

### ⚡ Method 2: uv (Cross-Platform)

If you use [uv](https://github.com/astral-sh/uv), Astral's blazingly fast Python tool installer:

```bash
uv tool install voodoo-framework
```

### 🪄 Method 3: The Magic Install Script

For a quick, zero-dependency installation that isolates the environment automatically:

```bash
curl -fsSL https://raw.githubusercontent.com/helderperez-dev/voodoo/main/install.sh | bash
```

### 🐍 Method 4: pipx / pip

```bash
pipx install voodoo-framework
```

---

## 🏗 Scaffolding a New Project

Once Voodoo is installed globally, generating a new application is as simple as:

```bash
# Create a standard minimal project
voodoo new my_app

# Create a project using the SaaS template
voodoo new my_saas_app --variant saas
```

Navigate into the newly created directory and start the server:

```bash
cd my_app
voodoo dev
```

The application will start on `http://localhost:8000` with hot-reloading enabled.

## 📖 Smart Documentation

Voodoo ships with its own interactive documentation built using the framework itself. When you run the application, navigate to `/docs` in your browser to view:

- Component Library References
- API Integration Guides
- Framework Telemetry Status
- Live Examples

## 🛠 Project Structure

```
voodoo-framework/
├── app/               # Your application code
│   ├── pages/         # File-based routing (index.py, docs.py)
│   ├── layout.py      # Main layout component
│   ├── models.py      # Pydantic data models
│   └── workers.py     # Background task handlers
├── voodoo/            # Framework core source
├── tests/             # Pytest async test suite
└── pyproject.toml     # Project metadata and dependencies
```

## 🧪 Testing

Run the test suite using `pytest`:

```bash
pytest
```

## 📜 License

MIT License. See `LICENSE` for more information.
