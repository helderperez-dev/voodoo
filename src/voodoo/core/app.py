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
from dataclasses import dataclass
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
            self._starlette = create_app(app_dir=self.app_dir, runtime=self.runtime)
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

    def goal(
        self,
        goal: Any,
        *,
        observes: tuple[Any, ...] = (),
        propose: Any = None,
        objective: str = "",
        target_entity_id: str | None = None,
        requires: tuple[str, ...] = (),
        **kwargs: Any,
    ) -> Any:
        """Register an explicit Goal or decorate a desired-state predicate."""
        from voodoo.runtime.goal import Goal

        observed_ids = tuple(
            item.resource_id if isinstance(item, ObservationHandle) else item
            for item in observes
        )
        if isinstance(goal, Goal):
            self.runtime.register_goal(
                goal,
                observes=observed_ids,
                propose=propose,
                **kwargs,
            )
            return self
        if not isinstance(goal, str):
            raise TypeError("goal requires a Goal or goal name")

        def decorator(predicate: Callable[..., bool]) -> Callable[..., bool]:
            desired = Goal(
                id=goal,
                name=goal,
                objective=objective,
                target_entity_id=target_entity_id,
                requires=list(requires),
            )

            def satisfied(item: Any, snapshot: Any) -> bool:
                return bool(predicate(snapshot))

            self.runtime.register_goal(
                desired,
                observes=observed_ids,
                satisfied=satisfied,
                propose=propose,
                **kwargs,
            )
            return predicate

        return decorator

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

        capability_name = name or (capability if isinstance(capability, str) else None)
        if capability_name is None:
            raise TypeError("capability requires a Capability or capability name")

        def decorator(compute: Callable[..., Any]) -> Callable[..., Any]:
            if capability_name not in self.runtime.engine.capabilities.capabilities:
                self.runtime.engine.capabilities.register(
                    Capability(name=capability_name)
                )
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
        print("
".join(["", *lines]), flush=True)


def _load_app_module(app_dir: str, name: str) -> None:
    path = os.path.join(app_dir, f"{name}.py")
    if not os.path.exists(path):
        return
    spec = importlib.util.spec_from_file_location(name, path)
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        sys.modules[f"app_{name}"] = module
        spec.loader.exec_module(module)


def _build_routes(
    app_dir: str, cwd: str, config: Any
) -> tuple[list[BaseRoute], list[Any]]:
    from voodoo.mesh import mesh

    routes: list[BaseRoute] = [
        WebSocketRoute("/_voodoo_ws", websocket_endpoint),
        WebSocketRoute("/voodoo/mesh/ws", mesh._handle_websocket),
    ]
    for url, directory in (
        ("/public", os.path.join(cwd, "public")),
        ("/storage", os.path.join(cwd, config.storage_dir)),
    ):
        if os.path.isdir(directory):
            routes.append(
                Mount(url, app=StaticFiles(directory=directory), name=url[1:])
            )
    routes.extend(page_registry.routes)
    seo = config.seo
    if seo.sitemap_enabled:
        def sitemap(request: Request) -> Response:
            base = seo.base_url or str(request.base_url).rstrip("/")
            return Response(
                _generate_sitemap_xml(app_dir, base), media_type="application/xml"
            )
        routes.append(Route("/sitemap.xml", sitemap, methods=["GET"]))
    if seo.robots_enabled:
        def robots(request: Request) -> Response:
            base = seo.base_url or str(request.base_url).rstrip("/")
            return Response(_generate_robots_txt(seo, base), media_type="text/plain")
        routes.append(Route("/robots.txt", robots, methods=["GET"]))
    _scan_page_convention(app_dir, routes)
    _scan_pages_directory(app_dir, routes)
    for name in ("models", "workers", "api"):
        _load_app_module(app_dir, name)
    from voodoo.routing.api import api as voodoo_api
    routes.extend(voodoo_api.routes)

    edge_gateway: list[Any] = []
    if config.edge.enabled and config.edge.http_enabled:
        from voodoo.edge import DeviceGateway, InMemoryDeviceStore
        from voodoo.edge.http import build_edge_routes
        from voodoo.runtime.engine import engine as runtime_engine
        gateway = DeviceGateway(InMemoryDeviceStore(), runtime_engine)
        edge_gateway.append(gateway)
        routes.extend(build_edge_routes(gateway))
    return routes, edge_gateway


def _configure_execution_store(
    config: Any, runtime_engine: Any
) -> tuple[Any, str | None]:
    provider = config.database.provider.lower()
    if provider == "voodoo":
        from voodoo.storage.execution import VoodooStoreExecutionStore
        store = VoodooStoreExecutionStore()
        schedule_path = None
    elif provider == "postgres":
        from voodoo.storage.execution import PostgresExecutionStore
        store = PostgresExecutionStore(
            config.database.url or os.getenv("VOODOO_DATABASE_URL", "")
        )
        schedule_path = ".voodoo/state/schedules.db"
    elif provider == "sqlite":
        from voodoo.storage.execution import SQLiteExecutionStore
        path = config.db_path.replace(":memory:", ".voodoo/state/data.db")
        store = SQLiteExecutionStore(path)
        schedule_path = path.replace("data.db", "schedules.db")
    else:
        from voodoo.core.errors import ConfigurationError
        raise ConfigurationError(
            f"Unknown execution database provider '{config.database.provider}'. "
            "Use 'voodoo' (default), 'sqlite', or 'postgres'."
        )
    runtime_engine.use_store(store)
    return store, schedule_path


async def _start_mqtt(
    config: Any, edge_gateway: list[Any], application_store: Any
) -> Any:
    if not (config.edge.enabled and config.edge.mqtt_enabled):
        return None
    try:
        from voodoo.edge import DeviceGateway, VoodooStoreDeviceStore
        from voodoo.edge.mqtt import EdgeMQTTTransport
        from voodoo.runtime.engine import engine as runtime_engine
    except ImportError:
        return None
    gateway = edge_gateway[0] if edge_gateway else DeviceGateway(
        VoodooStoreDeviceStore(application_store), runtime_engine
    )
    transport = EdgeMQTTTransport(
        gateway,
        broker_url=config.edge.mqtt_broker_url or "localhost",
        port=config.edge.mqtt_port,
        tls=config.edge.mqtt_tls,
        username=config.edge.mqtt_username or None,
        password=config.edge.mqtt_password or None,
        client_id=config.edge.mqtt_client_id,
        qos=config.edge.mqtt_qos,
    )
    await transport.start()
    return transport


def create_app(app_dir: str = "app", *, runtime: Any = None) -> Starlette:
    """Build a fully wired Starlette application."""
    from voodoo.config import get_config
    from voodoo.ui.styles.presets import activate_theme

    config = get_config()
    try:
        cwd = os.getcwd()
    except FileNotFoundError:
        cwd = "."
    activate_theme(config.theme.preset, project_root=cwd, mode=config.theme.mode)
    routes, edge_gateway = _build_routes(app_dir, cwd, config)

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
    async def lifespan(starlette: Starlette) -> AsyncIterator[None]:
        from voodoo.runtime.store import StoreConfig, activate_runtime_store
        application_store = activate_runtime_store(StoreConfig.from_mapping(config.store.model_dump()))
        starlette.state.runtime_store = application_store
        if runtime is not None:
            runtime.use_store(application_store)
        from voodoo.data.store_backend import bind_runtime_store
        bind_runtime_store(application_store)
        from voodoo.runtime.engine import engine as global_runtime_engine
        runtime_engine = runtime.engine if runtime is not None else global_runtime_engine
        execution_store, schedule_path = _configure_execution_store(config, runtime_engine)
        if edge_gateway:
            from voodoo.edge import VoodooStoreDeviceStore
            edge_gateway[0]._store = VoodooStoreDeviceStore(application_store)
        from voodoo.runtime.scheduler import ScheduleService
        from voodoo.storage.scheduler import create_schedule_store
        schedule_store = create_schedule_store(schedule_path)
        scheduler = ScheduleService(schedule_store)
        await scheduler.start()
        from voodoo.workers.queue import _workers
        worker_task = asyncio.create_task(start_workers()) if _workers else None
        mqtt_transport = await _start_mqtt(config, edge_gateway, application_store)
        if runtime is not None:
            runtime.start()
        try:
            yield
        finally:
            if runtime is not None:
                runtime.stop()
            if mqtt_transport is not None:
                await mqtt_transport.stop()
            await stop_workers()
            if worker_task:
                worker_task.cancel()
            from voodoo.data import close_db
            await close_db()
            await scheduler.stop()
            schedule_store.close()
            close_store = getattr(execution_store, "close", None)
            if close_store is not None:
                close_store()
            runtime_engine.use_store(None)
            bind_runtime_store(None)
            application_store.stop()

    middleware = [
        Middleware(TelemetryMiddleware),
        Middleware(SecurityHeadersMiddleware),
        Middleware(CORSMiddleware),
        Middleware(CSRFMiddleware),
        Middleware(RateLimitMiddleware),
        Middleware(I18nMiddleware),
        Middleware(AuthMiddleware),
    ]
    return Starlette(routes=routes, middleware=middleware, lifespan=lifespan)


def _scan_page_convention(app_dir: str, routes: list[BaseRoute]) -> None:
    """Scan app_dir for page.py files using folder-based routing."""
    if not os.path.exists(app_dir):
        return
    for root, _dirs, files in os.walk(app_dir):
        if os.path.relpath(root, app_dir) == "pages" or "page.py" not in files:
            continue
        filepath = os.path.join(root, "page.py")
        rel_path = os.path.relpath(root, app_dir)
        route_path = (
            "/"
            if rel_path == "."
            else "/" + rel_path.replace("\\", "/").replace("[", "{").replace("]", "}")
        )
        clean_name = route_path.replace("/", "_").replace("{", "").replace("}", "")
        route = _load_page_file(filepath, route_path, f"page_{clean_name}")
        if route:
            routes.append(route)


def _scan_pages_directory(app_dir: str, routes: list[BaseRoute]) -> None:
    """Scan app_dir/pages for file-per-page routing."""
    pages_dir = os.path.join(app_dir, "pages")
    if not os.path.isdir(pages_dir):
        return
    for root, _dirs, files in os.walk(pages_dir):
        for fname in files:
            if not fname.endswith(".py") or fname.startswith("_"):
                continue
            filepath = os.path.join(root, fname)
            stem = os.path.relpath(filepath, pages_dir)[:-3].replace("\\", "/")
            if stem == "index":
                route_path = "/"
            else:
                parts = [
                    part.replace("[", "{").replace("]", "}")
                    for part in stem.split("/")
                ]
                route_path = "/" + "/".join(parts)
            clean_name = route_path.replace("/", "_").replace("{", "").replace("}", "")
            route = _load_page_file(filepath, route_path, f"pages_{clean_name}")
            if route:
                routes.append(route)


app = App()
