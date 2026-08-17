import os
import subprocess
import time
import urllib.request
from pathlib import Path
from textwrap import dedent

from rich.progress import Progress

AI_DOCS_BASE_URL = (
    "https://raw.githubusercontent.com/helderperez-dev/voodoo/main/docs/ai"
)
AI_TRAE_SKILL_URL = "https://raw.githubusercontent.com/helderperez-dev/voodoo/main/.trae/skills/voodoo-builder/SKILL.md"


def _write_text_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _fetch_text(url: str, timeout: int = 3) -> str | None:
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = response.read()
            if isinstance(data, bytes):
                return data.decode("utf-8")
            if isinstance(data, str):
                return data
    except Exception:
        pass
    return None


def _build_workspace_rules() -> str:
    return (
        dedent(
            """
        # Voodoo AI Workspace

        This project uses the Voodoo Framework.

        Start by reading these local files in order:
        1. `.voodoo/ai/README.md`
        2. `.voodoo/ai/RULES.md`
        3. `.voodoo/ai/ARCHITECTURE.md`
        4. `.voodoo/ai/ROUTING.md`
        5. `.voodoo/ai/COMPONENTS.md`
        6. `.voodoo/ai/STATE.md`
        7. `.voodoo/ai/DATABASE.md`
        8. `.voodoo/ai/SKILLS.md`
        9. `.voodoo/ai/MESH.md`
        10. `.voodoo/ai/SEO.md`

        Core rules:
        - Use `voodoo.components` instead of raw HTML templates.
        - Prefer `async def` for handlers, I/O, and database work.
        - Use Voodoo's `A` component plus `voodoo.navigate()` for internal links.
        - Keep app code in `app/` and data in `.voodoo/state/`.
        - Use `aiosqlite` with `.voodoo/state/data.db` by default.
        - Preserve the large-cookie websocket settings in `voodoo dev`.

        If Trae skills are available, use `.trae/skills/voodoo-builder/SKILL.md`.
        """
        ).strip()
        + "\n"
    )


def _build_cursor_rules() -> str:
    return (
        "---\n"
        "description: Voodoo framework guidance for Cursor.\n"
        "globs:\n"
        '  - "**/*.py"\n'
        '  - "**/*.md"\n'
        "alwaysApply: true\n"
        "---\n\n" + _build_workspace_rules()
    )


def _fallback_ai_assets() -> dict[str, str]:
    return {
        ".voodoo/ai/README.md": dedent(
            """
            # Voodoo AI Kit

            This folder gives AI IDEs high-context guidance for building serious Voodoo applications.

            Read these files in order:
            1. `RULES.md`
            2. `ARCHITECTURE.md`
            3. `ROUTING.md`
            4. `COMPONENTS.md`
            5. `STATE.md`
            6. `DATABASE.md`
            7. `SKILLS.md`
            8. `MESH.md`
            9. `SEO.md`

            Recommended behavior:
            - Treat Voodoo as a Python-first UI framework.
            - Prefer simple, composable route files and reusable components.
            - Respect Voodoo navigation, websocket, and data conventions.
            """
        ).strip()
        + "\n",
        ".voodoo/ai/RULES.md": dedent(
            """
            # Voodoo Rules

            - Build UI with `voodoo.components`.
            - Prefer `async def` for handlers and I/O.
            - Use Tailwind via `className`.
            - Use `A(..., href=..., onClick="voodoo.navigate('...')")` for internal links.
            - Keep route files inside `app/`.
            - Keep persistent data inside `.voodoo/state/`.
            - Use `aiosqlite` and `.voodoo/state/data.db` by default.
            - Preserve `WEBSOCKETS_MAX_LINE_LENGTH="8388608"` and `http="h11"` when working with websocket-heavy apps.
            """
        ).strip()
        + "\n",
        ".voodoo/ai/ARCHITECTURE.md": dedent(
            """
            # Voodoo Architecture

            Voodoo is a Starlette-based framework with Python-defined UI and file-based routing.

            Main conventions:
            - `app/` contains routes and app-facing code.
            - `voodoo dev` boots the app (`main.py` is optional).
            - `voodoo.components` is the primary UI surface.
            - Internal framework API routes remain mounted automatically.
            """
        ).strip()
        + "\n",
        ".voodoo/ai/ROUTING.md": dedent(
            """
            # Voodoo Routing

            - `app/page.py` maps to `/`
            - Nested `page.py` files map to nested routes
            - Dynamic segments use bracket folders such as `app/users/[id]/page.py`
            - Return `(SEO, Component)` or `(Component, SEO)` tuples to inject head metadata

            Internal links must use Voodoo navigation:

            ```python
            from voodoo.components import A

            A("Dashboard", href="/dashboard", onClick="voodoo.navigate('/dashboard')")
            ```
            """
        ).strip()
        + "\n",
        ".voodoo/ai/COMPONENTS.md": dedent(
            """
            # Voodoo Components

            Import UI primitives from `voodoo.components`.

            Common components:
            - `Div`, `Text`, `Heading`, `Button`, `A`, `Input`, `Form`
            - Semantic HTML: `Nav`, `Header`, `Footer`, `Main`, `Section`, `Article`, `Aside`, `Figure`, `FigCaption`, `Time`, `Address`, `Img`, `Paragraph`

            Use `className` for styling and favor small reusable Python functions for custom components.
            """
        ).strip()
        + "\n",
        ".voodoo/ai/STATE.md": dedent(
            """
            # Voodoo State

            Voodoo does not use React-style client state hooks.

            Preferred patterns:
            - Form posts for mutations
            - Async route handlers for derived UI
            - Database-backed state for persistence
            - WebSockets only when real-time behavior is truly needed
            """
        ).strip()
        + "\n",
        ".voodoo/ai/DATABASE.md": dedent(
            """
            # Voodoo Database

            Default stack:
            - `aiosqlite`
            - database path: `.voodoo/state/data.db`

            Example:

            ```python
            import aiosqlite

            async with aiosqlite.connect(".voodoo/state/data.db") as db:
                await db.execute("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, name TEXT)")
                await db.commit()
            ```
            """
        ).strip()
        + "\n",
        ".voodoo/ai/SKILLS.md": dedent(
            """
            # Voodoo AI Skills

            ## Scaffold a Route
            - Create the correct `app/.../page.py` file
            - Export `page(request, ...)`
            - Return `voodoo.components`

            ## Create a Component
            - Build a reusable Python function
            - Accept meaningful arguments
            - Style through `className`

            ## Add Data
            - Use `aiosqlite`
            - Store the database in `.voodoo/state/data.db`
            - Keep queries async

            ## Debug Navigation
            - Check file-based route placement
            - Check `A` + `voodoo.navigate()`

            ## Debug Cookies / WebSockets
            - Check `WEBSOCKETS_MAX_LINE_LENGTH`
            - Check `http="h11"`
            """
        ).strip()
        + "\n",
        ".voodoo/ai/MESH.md": dedent(
            """
            # Voodoo Mesh

            The Voodoo Mesh (`voodoo.mesh`) enables real-time WebSocket events and automatic MCP tool registration.

            - Use `@mesh.expose()` to expose functions to RPC and MCP tools.
            - Use `@mesh.on(event)` to listen for local and remote broadcast events.
            - Use `await mesh.broadcast(event, payload)` to push data to all connected clients.
            """
        ).strip()
        + "\n",
        ".voodoo/ai/SEO.md": dedent(
            """
            # Voodoo SEO & GEO

            Voodoo supports native SEO metadata and Generative Engine Optimization (GEO).

            - Return `(SEO(...), Component)` from route handlers.
            - Configure defaults in `voodoo.yaml`.
            - Dynamic `sitemap.xml` and `robots.txt` are served automatically.
            - Supports JSON-LD structured data and OpenGraph / Twitter cards.
            """
        ).strip()
        + "\n",
        ".trae/skills/voodoo-builder/SKILL.md": dedent(
            """
            ---
            name: "voodoo-builder"
            description: "Builds and refactors Voodoo apps. Invoke when creating routes, components, data flows, or debugging Voodoo-specific behavior."
            ---

            # Voodoo Builder

            Use this skill when working on Voodoo Framework applications.

            Read these local files before making major changes:
            1. `.voodoo/ai/README.md`
            2. `.voodoo/ai/RULES.md`
            3. `.voodoo/ai/ARCHITECTURE.md`
            4. `.voodoo/ai/ROUTING.md`
            5. `.voodoo/ai/COMPONENTS.md`
            6. `.voodoo/ai/STATE.md`
            7. `.voodoo/ai/DATABASE.md`
            8. `.voodoo/ai/SKILLS.md`
            9. `.voodoo/ai/MESH.md`
            10. `.voodoo/ai/SEO.md`

            Follow these Voodoo rules:
            - Build UI with `voodoo.components`
            - Prefer `async def`
            - Use `A` plus `voodoo.navigate()` for internal links
            - Keep data in `.voodoo/state/`
            - Use `aiosqlite` by default
            - Preserve websocket large-cookie configuration
            """
        ).lstrip(),
    }


def _detect_ide() -> str | None:  # noqa: C901
    """
    Attempt to auto-detect the active AI IDE/Editor from environment variables,
    workspace config directories, or running parent processes.
    """
    env_keys = " ".join(os.environ.keys()).lower()
    term_program = os.getenv("TERM_PROGRAM", "").lower()

    # 1. Environment variables (highest priority for current session)
    if (
        any(
            k in env_keys
            for k in ["trae_pid", "trae_resources_path", "__trae_app_dir__"]
        )
        or "trae" in term_program
    ):
        return "trae"

    if (
        any(k in env_keys for k in ["cursor_trace", "cursor_port", "cursor_session_id"])
        or "cursor" in term_program
    ):
        return "cursor"

    if (
        any(k in env_keys for k in ["windsurf_port", "windsurf_initial_cwd"])
        or "windsurf" in term_program
    ):
        return "windsurf"

    if (
        any(k in env_keys for k in ["vscode_pid", "vscode_injection"])
        or "vscode" in term_program
    ):
        return "vscode"

    # 2. Check directory markers in current workspace
    curr = Path.cwd()
    for directory in [curr, *curr.parents[:3]]:
        if (directory / ".trae").exists():
            return "trae"
        if (directory / ".cursor").exists():
            return "cursor"
        if (directory / ".windsurfrules").exists():
            return "windsurf"
        if (directory / ".vscode").exists():
            return "vscode"

    # 3. Process inspection for specific IDEs
    try:
        curr_pid = os.getppid()
        for _ in range(4):
            if curr_pid <= 1:
                break
            res = subprocess.run(
                ["ps", "-p", str(curr_pid), "-o", "comm="],
                capture_output=True,
                text=True,
                timeout=1,
            )
            comm = res.stdout.strip().lower()
            if "trae" in comm:
                return "trae"
            if "cursor" in comm:
                return "cursor"
            if "windsurf" in comm:
                return "windsurf"
            if "code" in comm or "vscode" in comm:
                return "vscode"
            ppid_res = subprocess.run(
                ["ps", "-p", str(curr_pid), "-o", "ppid="],
                capture_output=True,
                text=True,
                timeout=1,
            )
            ppid_str = ppid_res.stdout.strip()
            if not ppid_str.isdigit():
                break
            curr_pid = int(ppid_str)
    except Exception:
        pass

    return None


def _sync_ai_assets(project_dir: Path, progress: Progress, ide: str = "none") -> None:  # noqa: C901
    _task = progress.add_task(
        description=f"Setting up AI assets ({ide})...", total=None
    )
    time.sleep(0.2)

    fallback_assets = _fallback_ai_assets()
    remote_assets = {
        ".voodoo/ai/README.md": f"{AI_DOCS_BASE_URL}/README.md",
        ".voodoo/ai/RULES.md": f"{AI_DOCS_BASE_URL}/RULES.md",
        ".voodoo/ai/ARCHITECTURE.md": f"{AI_DOCS_BASE_URL}/ARCHITECTURE.md",
        ".voodoo/ai/ROUTING.md": f"{AI_DOCS_BASE_URL}/ROUTING.md",
        ".voodoo/ai/COMPONENTS.md": f"{AI_DOCS_BASE_URL}/COMPONENTS.md",
        ".voodoo/ai/STATE.md": f"{AI_DOCS_BASE_URL}/STATE.md",
        ".voodoo/ai/DATABASE.md": f"{AI_DOCS_BASE_URL}/DATABASE.md",
        ".voodoo/ai/SKILLS.md": f"{AI_DOCS_BASE_URL}/SKILLS.md",
        ".voodoo/ai/MESH.md": f"{AI_DOCS_BASE_URL}/MESH.md",
        ".voodoo/ai/SEO.md": f"{AI_DOCS_BASE_URL}/SEO.md",
        ".voodoo/ai/AUTH.md": f"{AI_DOCS_BASE_URL}/AUTH.md",
        ".voodoo/ai/SECURITY.md": f"{AI_DOCS_BASE_URL}/SECURITY.md",
    }

    if ide in ("trae", "all"):
        remote_assets[".trae/skills/voodoo-builder/SKILL.md"] = AI_TRAE_SKILL_URL

    for relative_path, url in remote_assets.items():
        target = project_dir / relative_path
        if target.exists():
            continue
        content = _fetch_text(url, timeout=3) or fallback_assets.get(relative_path, "")
        if content:
            _write_text_file(target, content)

    ide_rules: dict[str, str] = {}
    if ide in ("trae", "all"):
        ide_rules[".trae/rules"] = _build_workspace_rules()
    if ide in ("windsurf", "all"):
        ide_rules[".windsurfrules"] = _build_workspace_rules()
    if ide in ("cursor", "all"):
        ide_rules[".cursor/rules/voodoo.mdc"] = _build_cursor_rules()
    if ide in ("vscode", "all"):
        ide_rules[".github/copilot-instructions.md"] = _build_workspace_rules()

    for relative_path, content in ide_rules.items():
        target = project_dir / relative_path
        if target.exists():
            continue
        _write_text_file(target, content)
