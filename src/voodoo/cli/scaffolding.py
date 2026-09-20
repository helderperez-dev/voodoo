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
            - Voodoo CSS is the default style adapter: components emit semantic
              `vd-*` classes driven by theme tokens. Prefer semantic props
              (`variant`, `size`, `tone`, `level`) over utility classes. Opt into
              Tailwind only with `set_style_adapter(TailwindAdapter())`.
            - Use `A(..., href=..., onClick="voodoo.navigate('...')")` for internal links.
            - Use folder-based routing: `app/<segment>/page.py` defines a `page(request)`
              function. `app/pages/` (file-per-page) is supported for backward compat.
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

            Folder-based routing (the scaffold default): each directory under `app/`
            containing a `page.py` maps to a route.

            - `app/page.py` -> `/`
            - `app/about/page.py` -> `/about`
            - `app/dashboard/settings/page.py` -> `/dashboard/settings`
            - Dynamic segments use bracket folders such as `app/users/[id]/page.py` -> `/users/{id}`

            Each `page.py` defines a `page(request, ...)` function. Path parameters
            are injected by name and coerced to their annotation.

            Return `(SEO, Component)` or `(Component, SEO)` tuples to inject head metadata.

            `app/pages/` (one file per page) is supported for backward compatibility.

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

            Import UI primitives from `voodoo.components` (or the `voodoo` top level).

            Common components:
            - `Div`, `Text`, `Heading`, `Button`, `A`, `Input`, `Form`
            - Layout: `Page`, `Container`, `Stack`, `Flex`, `Grid`, `Box`
            - Semantic HTML: `Nav`, `Header`, `Footer`, `Main`, `Section`, `Article`, `Aside`, `Figure`, `FigCaption`, `Time`, `Address`, `Img`, `Paragraph`

            Voodoo CSS (the default adapter) generates semantic `vd-*` classes from
            each component's style key and props, all driven by `--vd-*` theme tokens.
            Prefer semantic props over utility classes:

            ```python
            from voodoo import Button, Heading, Stack, Text, Card

            Stack(
                Heading("Hello, Voodoo!", level=1, size="xl"),
                Text("Build your UI in Python.", tone="muted"),
                Button("Get Started", variant="primary"),
                Card(Heading("Folder-based routing", level=3), Text("app/page.py → /")),
            )
            ```

            Use `className` only for one-off overrides. Swap to Tailwind with
            `set_style_adapter(TailwindAdapter())`. Build reusable components as
            small Python functions.
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


def _ide_from_environment() -> str | None:
    env_keys = " ".join(os.environ.keys()).lower()
    term_program = os.getenv("TERM_PROGRAM", "").lower()
    signatures = {
        "trae": ("trae_pid", "trae_resources_path", "__trae_app_dir__"),
        "cursor": ("cursor_trace", "cursor_port", "cursor_session_id"),
        "windsurf": ("windsurf_port", "windsurf_initial_cwd"),
        "vscode": ("vscode_pid", "vscode_injection"),
    }
    return next(
        (
            ide
            for ide, keys in signatures.items()
            if ide in term_program or any(key in env_keys for key in keys)
        ),
        None,
    )


def _ide_from_workspace() -> str | None:
    markers = (
        (".trae", "trae"),
        (".cursor", "cursor"),
        (".windsurfrules", "windsurf"),
        (".vscode", "vscode"),
    )
    directories = [Path.cwd(), *Path.cwd().parents[:3]]
    return next(
        (
            ide
            for directory in directories
            for marker, ide in markers
            if (directory / marker).exists()
        ),
        None,
    )


def _ide_from_processes() -> str | None:
    markers = (\n        ("trae", "trae"),\n        ("cursor", "cursor"),\n        ("windsurf", "windsurf"),\n        ("vscode", "vscode"),\n        ("code", "vscode"),\n    )
    try:
        curr_pid = os.getppid()
        for _ in range(4):
            if curr_pid <= 1:
                return None
            res = subprocess.run(
                ["ps", "-p", str(curr_pid), "-o", "comm="],
                capture_output=True,
                text=True,
                timeout=1,
            )
            comm = res.stdout.strip().lower()
            match = next((ide for marker, ide in markers if marker in comm), None)
            if match:
                return match
            ppid_res = subprocess.run(
                ["ps", "-p", str(curr_pid), "-o", "ppid="],
                capture_output=True,
                text=True,
                timeout=1,
            )
            ppid = ppid_res.stdout.strip()
            if not ppid.isdigit():
                return None
            curr_pid = int(ppid)
    except Exception:
        return None
    return None


def _detect_ide() -> str | None:
    """Auto-detect the active AI IDE/editor."""
    return _ide_from_environment() or _ide_from_workspace() or _ide_from_processes()


def _remote_ai_assets(ide: str) -> dict[str, str]:
    names = [
        "README",
        "RULES",
        "ARCHITECTURE",
        "ROUTING",
        "COMPONENTS",
        "STATE",
        "DATABASE",
        "SKILLS",
        "MESH",
        "SEO",
        "AUTH",
        "SECURITY",
    ]
    assets = {
        f".voodoo/ai/{name}.md": f"{AI_DOCS_BASE_URL}/{name}.md" for name in names
    }
    if ide in ("trae", "all"):
        assets[".trae/skills/voodoo-builder/SKILL.md"] = AI_TRAE_SKILL_URL
    return assets


def _ide_rule_assets(ide: str) -> dict[str, str]:
    builders = {
        "trae": (".trae/rules", _build_workspace_rules),
        "windsurf": (".windsurfrules", _build_workspace_rules),
        "cursor": (".cursor/rules/voodoo.mdc", _build_cursor_rules),
        "vscode": (".github/copilot-instructions.md", _build_workspace_rules),
    }
    selected = (
        builders if ide == "all" else {ide: builders[ide]} if ide in builders else {}
    )
    return {path: builder() for path, builder in selected.values()}


def _write_missing_assets(project_dir: Path, assets: dict[str, str]) -> None:
    for relative_path, content in assets.items():
        target = project_dir / relative_path
        if not target.exists() and content:
            _write_text_file(target, content)


def _sync_ai_assets(project_dir: Path, progress: Progress, ide: str = "none") -> None:
    progress.add_task(description=f"Setting up AI assets ({ide})...", total=None)
    time.sleep(0.2)
    fallback_assets = _fallback_ai_assets()
    fetched = {
        path: _fetch_text(url, timeout=3) or fallback_assets.get(path, "")
        for path, url in _remote_ai_assets(ide).items()
    }
    _write_missing_assets(project_dir, fetched)
    _write_missing_assets(project_dir, _ide_rule_assets(ide))
