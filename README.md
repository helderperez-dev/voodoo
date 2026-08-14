# Voodoo Framework 🪄

**The Modern, Full-Stack Async Python Web Framework.**

Voodoo is an ultra-minimalist, high-performance web framework designed for the AI era. Built on top of Starlette and Uvicorn, it offers a seamless, reactive developer experience by combining a React-like component system in pure Python with robust backend features like background queues, real-time websockets, LLM agents, and built-in SQLite persistence.

## ✨ Features

- **Component-Driven UI**: Build modern, reactive UIs using pure Python components (`Div`, `Card`, `Button`, `Text`) with TailwindCSS integration out of the box. No writing raw HTML/JS required.
- **Real-Time WebSockets**: Live updates pushed seamlessly to the client with minimal configuration.
- **Data Persistence**: Built-in async SQLite (`aiosqlite`) ORM using Pydantic models with Row-Level Security (RLS) policies.
- **Background Workers**: Native task queues for heavy processing, ideal for AI/LLM workloads.
- **AI Native**: Built-in support for LLM Agents and the Model Context Protocol (MCP).
- **Observability**: Integrated Telemetry and APM tracing module tracking latencies, metrics, and AI token usage.
- **Zero Config**: `pyproject.toml` based, zero-configuration setup, hot-reloading, and out-of-the-box smart documentation.

## 🚀 Getting Started

### Prerequisites

- Python 3.12+
- `pip`

### Installation

Clone the repository and install the framework in editable mode with development dependencies:

```bash
git clone https://github.com/your-org/voodoo-framework.git
cd voodoo-framework
pip install -e .[dev]
```

### Running the App

Start the development server using the CLI:

```bash
voodoo dev
```

The application will start on `http://localhost:8000`. 
Check out the built-in Smart Documentation at `http://localhost:8000/docs` to see all available components and APIs.

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
