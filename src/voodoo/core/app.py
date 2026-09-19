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
from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class ObservationHandle:
    """Public handle connecting one World property to the Runtime graph."""

    app: "App"
    entity_id: str
    property: str
    resource_id: str

    async def set(
        self,
        value: Any,
        *,
        source: str,
        **observation: Any,
    ) -> Any:
        return await self.app.observe(
            self.entity_id,
            self.property,
            value,
            source=source,
            **observation,
        )


class App:
    """Central Voodoo application."""

    def __init__(
        self,
        app_dir: str = "app",
        *,
        theme: Any = None,
        runtime: Any = None,
    ) -> None:
        self.app_dir = app_dir
        self._starlette: Starlette | None = None
        self._plugins: list[Callable[[App], Any]] = []
        if runtime is None:
            from voodoo.runtime import Runtime

            runtime = Runtime()
        self.runtime = runtime
        if theme is not None:
            if isinstance(theme, str):
                from voodoo.ui.styles.presets import activate_theme

                activate_theme(theme)
            else:
                from voodoo.ui.styles.theme import set_theme

                set_theme(theme)

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

    @property
    def world(self) -> Any:
        """World model owned by the application's canonical Runtime."""
        return self.runtime.world

    def observation(
        self,
        entity_id: str,
        property: str,
        *,
        resource_id: str | None = None,
    ) -> ObservationHandle:
        """Declare a World property that can drive adaptive reconciliation."""
        bound = self.runtime.bind_observation(
            entity_id,
            property,
            resource_id=resource_id,
        )
        return ObservationHandle(self, entity_id, property, bound)

    def observe(self, *args: Any, **kwargs: Any) -> Any:
        """Record evidence through the application's canonical Runtime."""
        return self.runtime.observe(*args, **kwargs)

    def goal(self, goal: Any, **kwargs: Any) -> "App":
        """Register a desired-state Goal on the canonical Runtime."""
        observes = kwargs.get("observes")
        if observes is not None:
            kwargs["observes"] = tuple(
                item.resource_id if isinstance(item, ObservationHandle) else item
                for item in observes
            )
        self.runtime.register_goal(goal, **kwargs)
        return self

    def capability(
        self,
        capability: Any,
        *,
        name: str | None = None,
    ) -> Any:
        """Register capability authority or decorate its compute implementation."""
        from voodoo.primitives.capability import Capability
        from voodoo.runtime.planner import ComputeParticipant

        if isinstance(capability, Capability):
            self.runtime.engine.capabilities.register(capability)
            return self

        capability_name = name or (
            capability if isinstance(capability, str) else None
        )
        if capability_name is None:
            raise TypeError("capability requires a Capability or capability name")

        def decorator(compute: Callable[..., Any]) -> Callable[..., Any]:
            if capability_name not in self.runtime.engine.capabilities.capabilities:
                self.runtime.engine.capabilities.register(Capability(name=capability_name))
            self.runtime.register_compute(
                ComputeParticipant(
                    name=compute.__name__,
                    kind="compute",
                    capabilities=[capability_name],
                    compute=compute,
                )
            )
            return compute

        return decorator

    def use(self, plugin: Callable[["App"], Any]) -> "App":
        """Register a plugin callable invoked once the app is built."""
        self._plugins.append(plugin)
        return self

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
    """Build a fully wired Starlette application."""
    from voodoo.config import get_config

    config = get_config()

    try:
        cwd = os.getcwd()
    except FileNotFoundError:
        cwd = "."

    from voodoo.ui.styles.presets import activate_theme

    activate_theme(config.theme.preset, project_root=cwd, mode=config.theme.mode)

    from voodoo.mesh import mesh

    routes: list[BaseRoute] = [
        WebSocketRoute("/_voodoo_ws", websocket_endpoint),
        WebSocketRoute("/voodoo/mesh/ws", mesh._handle_websocket),
    ]

    public_dir = os.path.join(cwd, "public")
    if os.path.isdir(public_dir):
        routes.append(
            Mount("/public", app=StaticFiles(directory=public_dir), name="public")
        )

    storage_dir = os.path.join(cwd, config.storage_dir)
    if os.path.isdir(storage_dir):
        routes.append(
            Mount("/storage", app=StaticFiles(directory=storage_dir), name="storage")
        )

    routes.extend(page_registry.routes)

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

    _scan_page_convention(app_dir, routes)
    _scan_pages_directory(app_dir, routes)

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

    from voodoo.routing.api import api as voodoo_api

    routes.extend(voodoo_api.routes)

    edge_gateway: list = []
    if config.edge.enabled and config.edge.http_enabled:
        from voodoo.edge import DeviceGateway, InMemoryDeviceStore

        # Routes are assembled before the lifespan opens application.vstore.
        # No request can run before lifespan startup, so the temporary in-memory
        # store is replaced by VoodooStoreDeviceStore as soon as RuntimeStore is active.
        edge_store = InMemoryDeviceStore()
        from voodoo.runtime.engine import engine as _runtime_engine

        gateway = DeviceGateway(edge_store, _runtime_engine)
        edge_gateway.append(gateway)
        from voodoo.edge.http import build_edge_routes as _build_edge_routes

        routes.extend(_build_edge_routes(gateway))

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
    async def lifespan(app: Starlette) -> AsyncIterator[None]:  # noqa: C901  # noqa: C901
        from voodoo.runtime.store import StoreConfig, activate_runtime_store

        application_store = activate_runtime_store(
            StoreConfig.from_mapping(config.store.model_dump())
        )
        app.state.runtime_store = application_store

        from voodoo.data.store_backend import bind_runtime_store

        bind_runtime_store(application_store)

        from voodoo.runtime.engine import engine as runtime_engine

        provider = config.database.provider.lower()
        if provider == "voodoo":
            from voodoo.storage.execution import VoodooStoreExecutionStore

            execution_store = VoodooStoreExecutionStore()
            runtime_engine.use_store(execution_store)
            schedule_path = None
        elif provider == "postgres":
            from voodoo.storage.execution import PostgresExecutionStore

            url = config.database.url or os.getenv("VOODOO_DATABASE_URL", "")
            execution_store = PostgresExecutionStore(url)
            runtime_engine.use_store(execution_store)
            schedule_path = ".voodoo/state/schedules.db"
        elif provider == "sqlite":
            from voodoo.storage.execution import SQLiteExecutionStore

            store_path = config.db_path.replace(":memory:", ".voodoo/state/data.db")
            execution_store = SQLiteExecutionStore(store_path)
            runtime_engine.use_store(execution_store)
            schedule_path = store_path.replace("data.db", "schedules.db")
        else:
            from voodoo.core.errors import ConfigurationError

            raise ConfigurationError(
                f"Unknown execution database provider '{config.database.provider}'. "
                "Use 'voodoo' (default), 'sqlite', or 'postgres'."
            )

        if edge_gateway:
            from voodoo.edge import VoodooStoreDeviceStore

            # DeviceGateway deliberately exposes no second lifecycle owner; Edge
            # shares the exact Store handle owned by this Runtime.
            edge_gateway[0]._store = VoodooStoreDeviceStore(application_store)

        from voodoo.runtime.scheduler import ScheduleService
        from voodoo.storage.scheduler import create_schedule_store

        schedule_store = create_schedule_store(schedule_path)
        scheduler = ScheduleService(schedule_store)
        await scheduler.start()

        worker_task = None
        from voodoo.workers.queue import _workers

        if _workers:
            worker_task = asyncio.create_task(start_workers())

        mqtt_transport = None
        if config.edge.enabled and config.edge.mqtt_enabled:
            try:
                from voodoo.edge import DeviceGateway as _DG
                from voodoo.edge import VoodooStoreDeviceStore as _VSDS
                from voodoo.edge.mqtt import EdgeMQTTTransport
                from voodoo.runtime.engine import engine as _rt_engine

                gateway = (
                    edge_gateway[0]
                    if edge_gateway
                    else _DG(_VSDS(application_store), _rt_engine)
                )
                mqtt_transport = EdgeMQTTTransport(
                    gateway,
                    broker_url=config.edge.mqtt_broker_url or "localhost",
                    port=config.edge.mqtt_port,
                    tls=config.edge.mqtt_tls,
                    username=config.edge.mqtt_username or None,
                    password=config.edge.mqtt_password or None,
                    client_id=config.edge.mqtt_client_id,
                    qos=config.edge.mqtt_qos,
                )
                await mqtt_transport.start()
            except ImportError:
                pass

        try:
            yield
        finally:
            if mqtt_transport is not None:
                await mqtt_transport.stop()
            await stop_workers()
            if worker_task:
                worker_task.cancel()
            from voodoo.data import close_db

            await close_db()
            await scheduler.stop()
            schedule_store.close()
            close_execution_store = getattr(execution_store, "close", None)
            if close_execution_store is not None:
                close_execution_store()
            runtime_engine.use_store(None)
            bind_runtime_store(None)
            application_store.stop()

    middleware = [
        Middleware(SecurityHeadersMiddleware),
        Middleware(CORSMiddleware),
        Middleware(RateLimitMiddleware),
        Middleware(CSRFMiddleware),
        Middleware(TelemetryMiddleware),
        Middleware(I18nMiddleware),
        Middleware(AuthMiddleware),
    ]

    # ``public/`` is the filesystem root for static assets, not part of their
    # public URL. Keep the explicit ``/public`` mount above for 2.x compatibility,
    # then add a root mount last so application/runtime routes always win.
    if os.path.isdir(public_dir):
        routes.append(
            Mount("/", app=StaticFiles(directory=public_dir), name="public-root")
        )

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
            return Route(route_path, _module_page_endpoint(page_module.page))
    return None


def _scan_page_convention(app_dir: str, routes: list[BaseRoute]) -> None:
    """Scan ``app_dir`` for ``page.py`` files (folder-based routing)."""
    if not os.path.exists(app_dir):
        return
    for root, _dirs, files in os.walk(app_dir):
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
    """Scan ``app_dir/pages/`` for file-per-page routing."""
    pages_dir = os.path.join(app_dir, "pages")
    if not os.path.isdir(pages_dir):
        return
    for root, _dirs, files in os.walk(pages_dir):
        for fname in files:
            if not fname.endswith(".py") or fname.startswith("_"):
                continue
            filepath = os.path.join(root, fname)
            rel_path = os.path.relpath(filepath, pages_dir)
            stem = rel_path[:-3].replace("\\", "/")
            if stem == "index":
                route_path = "/"
            else:
                parts = [p.replace("[", "{").replace("]", "}") for p in stem.split("/")]
                route_path = "/" + "/".join(parts)
            clean_name = route_path.replace("/", "_").replace("{", "").replace("}", "")
            module_name = f"pages_{clean_name}"
            route = _load_page_file(filepath, route_path, module_name)
            if route:
                routes.append(route)


app = App()
