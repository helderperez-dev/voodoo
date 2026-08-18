"""The Voodoo application object (:class:`App`) and the underlying factory.

``App`` is the central runtime facade: it wraps the existing ``create_app``
machinery, exposes a dev-server entry point with a clean startup banner, and
stays a plain ASGI callable so it works with uvicorn, TestClient, and any
Starlette-compatible tooling.
"""

import asyncio
import importlib.util
import os
import socket
import sys
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import BaseRoute, Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles

from voodoo.core.sitemap import _generate_robots_txt, _generate_sitemap_xml
from voodoo.routing.pages import call_page, page_registry
from voodoo.ui.events import websocket_endpoint


def _local_ip() -> str | None:
    """Best-effort LAN IP discovery (no packet is actually sent)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return str(s.getsockname()[0])
    except Exception:
        return None


class App:
    """Central Voodoo application.

    Wraps the :func:`create_app` machinery behind one object with sane defaults
    for every subsystem. The Starlette application is built lazily (on first
    request or ``run()``) so ``@page`` registrations in the same module still
    apply::

        app = App()

        @page("/")
        def home():
            return Text("Hello")

        app.run()
    """

    def __init__(
        self,
        app_dir: str = "app",
        *,
        theme: Any = None,
    ) -> None:
        self.app_dir = app_dir
        self._starlette: Starlette | None = None
        self._plugins: list[Callable[[App], Any]] = []
        if theme is not None:
            from voodoo.ui.styles.theme import set_theme

            set_theme(theme)

    # -- ASGI ----------------------------------------------------------------

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        await self.starlette(scope, receive, send)

    @property
    def starlette(self) -> Starlette:
        """The underlying Starlette application (built on first access)."""
        if self._starlette is None:
            self._starlette = create_app(app_dir=self.app_dir)
            for plugin in self._plugins:
                plugin(self)
        return self._starlette

    @property
    def routes(self) -> list[BaseRoute]:
        """All registered routes (consumed by ``voodoo routes``)."""
        return list(self.starlette.routes)

    # -- Extension point -----------------------------------------------------

    def use(self, plugin: Callable[["App"], Any]) -> "App":
        """Register a plugin callable invoked once the app is built."""
        self._plugins.append(plugin)
        return self

    # -- Dev server ----------------------------------------------------------

    def run(
        self,
        host: str | None = None,
        port: int | None = None,
        *,
        reload: bool = False,
        **uvicorn_kwargs: Any,
    ) -> None:
        """Start the development server with the Voodoo startup banner."""

        import uvicorn

        from voodoo import __version__
        from voodoo.config import config
        from voodoo.core.errors import ConfigurationError

        host = host or config.host
        port = port if port is not None else config.port

        if reload:
            # uvicorn reload requires an import string, not an app object.
            raise ConfigurationError(
                "app.run(reload=True) requires an import string. Use "
                "`voodoo dev` or uvicorn.run('main:app', reload=True)."
            )

        self._print_banner(host, port, __version__)
        uvicorn.run(self, host=host, port=port, **uvicorn_kwargs)

    def _print_banner(self, host: str, port: int, version: str) -> None:
        display_host = "localhost" if host in ("0.0.0.0", "::", "") else host
        local_url = f"http://{display_host}:{port}"
        lines = [f"  Voodoo v{version}", ""]
        lines.append(f"  ➜  Local:   {local_url}")
        lines.append(f"  ➜  Docs:    {local_url}/docs")
        ip = _local_ip()
        if ip and host in ("0.0.0.0", "::", ""):
            lines.append(f"  ➜  Network: http://{ip}:{port}")
        print("\n".join(["", *lines]), flush=True)


def create_app(app_dir: str = "app") -> Starlette:  # noqa: C901
    """Build a fully wired Starlette application.

    ``App`` wraps this factory; ``create_app`` itself remains available as a
    compatibility alias for existing code.
    """
    from voodoo.config import config

    try:
        cwd = os.getcwd()
    except FileNotFoundError:
        cwd = "."
    from voodoo.mesh import mesh

    routes: list[BaseRoute] = [
        WebSocketRoute("/_voodoo_ws", websocket_endpoint),
        WebSocketRoute("/voodoo/mesh/ws", mesh._handle_websocket),
    ]

    # Mount public/ static assets only if the directory exists
    public_dir = os.path.join(cwd, "public")
    if os.path.isdir(public_dir):
        routes.append(
            Mount("/public", app=StaticFiles(directory=public_dir), name="public")
        )

    # Mount storage/ for local file serving only if the directory exists
    storage_dir = os.path.join(cwd, config.storage_dir)
    if os.path.isdir(storage_dir):
        routes.append(
            Mount("/storage", app=StaticFiles(directory=storage_dir), name="storage")
        )

    # --- Decorator-registered pages (@page) take precedence over convention ---
    routes.extend(page_registry.routes)

    # --- SEO: Auto-generate sitemap.xml and robots.txt ---
    seo_config = config.seo

    if seo_config.sitemap_enabled:

        def sitemap_handler(request: Request) -> Response:
            effective_base = seo_config.base_url or str(request.base_url).rstrip("/")
            xml = _generate_sitemap_xml(app_dir, effective_base)
            return Response(content=xml, media_type="application/xml")

        routes.append(Route("/sitemap.xml", sitemap_handler, methods=["GET"]))

    if seo_config.robots_enabled:

        def robots_handler(request: Request) -> Response:
            effective_base = seo_config.base_url or str(request.base_url).rstrip("/")
            txt = _generate_robots_txt(seo_config, effective_base)
            return Response(content=txt, media_type="text/plain")

        routes.append(Route("/robots.txt", robots_handler, methods=["GET"]))

    # File-based routing: app/page.py convention + app/pages/ file-per-page
    _scan_page_convention(app_dir, routes)
    _scan_pages_directory(app_dir, routes)

    # Initialize components if needed
    models_path = os.path.join(app_dir, "models.py")
    if os.path.exists(models_path):
        spec = importlib.util.spec_from_file_location("models", models_path)
        if spec and spec.loader:
            models_module = importlib.util.module_from_spec(spec)
            sys.modules["app_models"] = models_module
            spec.loader.exec_module(models_module)

    workers_path = os.path.join(app_dir, "workers.py")
    if os.path.exists(workers_path):
        spec = importlib.util.spec_from_file_location("workers", workers_path)
        if spec and spec.loader:
            workers_module = importlib.util.module_from_spec(spec)
            sys.modules["app_workers"] = workers_module
            spec.loader.exec_module(workers_module)

    api_path = os.path.join(app_dir, "api.py")
    if os.path.exists(api_path):
        spec = importlib.util.spec_from_file_location("api", api_path)
        if spec and spec.loader:
            api_module = importlib.util.module_from_spec(spec)
            sys.modules["app_api"] = api_module
            spec.loader.exec_module(api_module)

    # Always include internal API routes (like /status) even if no user api.py exists
    from voodoo.routing.api import api as voodoo_api

    routes.extend(voodoo_api.routes)

    from voodoo.auth import AuthMiddleware
    from voodoo.i18n import I18nMiddleware
    from voodoo.security import (
        CORSMiddleware,
        CSRFMiddleware,
        RateLimitMiddleware,
        SecurityHeadersMiddleware,
    )
    from voodoo.telemetry import TelemetryMiddleware
    from voodoo.workers.queue import start_workers, stop_workers

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        # Startup — wire the durable execution store (Sprint 3).
        from voodoo.core.errors import ConfigurationError
        from voodoo.runtime.engine import engine as runtime_engine
        from voodoo.storage.execution import SQLiteExecutionStore

        if config.database.provider == "postgres":
            # Sprint 10 ships the PostgreSQL database capability. The
            # execution/schedule stores are still SQLite-bound until
            # Sprint 11 wires them to the VoodooDatabase protocol — fail
            # fast with an actionable message rather than writing mixed
            # state (SQLite stores + PG adapter).
            raise ConfigurationError(
                "database.provider=postgres is not usable by the app "
                "lifespan yet: the execution/schedule stores wire to the "
                "VoodooDatabase protocol in Sprint 11. Use "
                "database.provider=sqlite for now."
            )

        store_path = config.db_path.replace(":memory:", ".voodoo/state/data.db")
        store = SQLiteExecutionStore(store_path)
        runtime_engine.use_store(store)

        # Scheduler (Sprint 5)
        from voodoo.runtime.scheduler import ScheduleService
        from voodoo.storage.scheduler import SQLiteScheduleStore

        schedule_store = SQLiteScheduleStore(
            store_path.replace("data.db", "schedules.db")
        )
        scheduler = ScheduleService(schedule_store)
        await scheduler.start()

        # DB and workers are lazily initialized
        worker_task = None
        from voodoo.workers.queue import _workers

        if _workers:
            worker_task = asyncio.create_task(start_workers())
        yield
        # Shutdown
        await stop_workers()
        if worker_task:
            worker_task.cancel()
        # Close the database connection if one was lazily opened
        # (no-op when the app never touched the data layer)
        from voodoo.data import close_db

        await close_db()
        await scheduler.stop()
        schedule_store.close()

    middleware = [
        Middleware(SecurityHeadersMiddleware),
        Middleware(CORSMiddleware),
        Middleware(RateLimitMiddleware),
        Middleware(CSRFMiddleware),
        Middleware(TelemetryMiddleware),
        Middleware(I18nMiddleware),
        Middleware(AuthMiddleware),
    ]

    app = Starlette(
        debug=config.debug,
        routes=routes,
        middleware=middleware,
        lifespan=lifespan,
    )

    return app


def _module_page_endpoint(page_func: Callable[..., Any]) -> Callable:
    """Wrap a file-based ``page()`` function into a Starlette endpoint."""

    async def handler(request: Request) -> Response:
        return await call_page(page_func, request)

    return handler


def _load_page_file(filepath: str, route_path: str, module_name: str) -> Route | None:
    """Import a single page module and return its Starlette Route (or None)."""
    spec = importlib.util.spec_from_file_location(module_name, filepath)
    if spec and spec.loader:
        page_module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = page_module
        spec.loader.exec_module(page_module)

        if hasattr(page_module, "page"):
            page_func = page_module.page
            return Route(route_path, _module_page_endpoint(page_func))
    return None


def _scan_page_convention(app_dir: str, routes: list[BaseRoute]) -> None:
    """Scan ``app_dir`` for ``page.py`` files (folder-based routing)."""
    if not os.path.exists(app_dir):
        return
    for root, _dirs, files in os.walk(app_dir):
        # Skip the pages/ subdirectory — handled by _scan_pages_directory
        if os.path.relpath(root, app_dir) == "pages":
            continue
        if "page.py" in files:
            filepath = os.path.join(root, "page.py")
            rel_path = os.path.relpath(root, app_dir)

            if rel_path == ".":
                route_path = "/"
            else:
                route_path = "/" + rel_path.replace("\\", "/").replace(
                    "[", "{"
                ).replace("]", "}")

            clean_name = route_path.replace("/", "_").replace("{", "").replace("}", "")
            module_name = f"page_{clean_name}"
            route = _load_page_file(filepath, route_path, module_name)
            if route:
                routes.append(route)


def _scan_pages_directory(app_dir: str, routes: list[BaseRoute]) -> None:
    """Scan ``app_dir/pages/`` for file-per-page routing.

    ``pages/index.py`` → ``/``, ``pages/about.py`` → ``/about``,
    ``pages/users/[id].py`` → ``/users/{id}``.
    """
    pages_dir = os.path.join(app_dir, "pages")
    if not os.path.isdir(pages_dir):
        return
    for root, _dirs, files in os.walk(pages_dir):
        for fname in files:
            if not fname.endswith(".py") or fname.startswith("_"):
                continue
            filepath = os.path.join(root, fname)
            rel_path = os.path.relpath(filepath, pages_dir)

            # Remove .py extension and normalize separators
            stem = rel_path[:-3]  # without .py
            stem = stem.replace("\\", "/")

            # index.py → /
            if stem == "index":
                route_path = "/"
            else:
                # about.py → /about, users/[id].py → /users/{id}
                parts = stem.split("/")
                parts = [p.replace("[", "{").replace("]", "}") for p in parts]
                route_path = "/" + "/".join(parts)

            clean_name = route_path.replace("/", "_").replace("{", "").replace("}", "")
            module_name = f"pages_{clean_name}"
            route = _load_page_file(filepath, route_path, module_name)
            if route:
                routes.append(route)


# Module-level ASGI app for `voodoo dev` when no main.py exists.
# The underlying Starlette app is built lazily on first request.
app = App()
