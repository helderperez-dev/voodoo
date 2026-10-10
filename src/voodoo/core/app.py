"""The Voodoo application object (:class:`App`) and the underlying factory.

``App`` is the central runtime facade: it wraps the existing ``create_app``
machinery, exposes a dev-server entry point with a clean startup banner, and
stays a plain ASGI callable so it works with uvicorn, TestClient, and any
Starlette-compatible tooling.
"""

import asyncio
import importlib.util
import logging
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
from starlette.responses import JSONResponse, Response
from starlette.routing import BaseRoute, Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles

from voodoo.core.sitemap import _generate_robots_txt, _generate_sitemap_xml
from voodoo.routing.pages import call_page, page_registry
from voodoo.security.redaction import redact_string
from voodoo.ui.events import websocket_endpoint

logger = logging.getLogger(__name__)

# Readiness is fail-closed for provider/connection failures, but an invariant
# violation must remain visible to the caller and test runner.
_READINESS_STORE_ERRORS = (
    AttributeError,
    ConnectionError,
    ImportError,
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


def _local_ip() -> str | None:
    """Best-effort LAN IP discovery (no packet is actually sent)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return str(s.getsockname()[0])
    except OSError as error:
        logger.debug("LAN IP discovery unavailable error=%s", redact_string(str(error)))
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
        from voodoo.runtime.agency import Goal

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
        print("\\n".join(["", *lines]), flush=True)


def _load_app_module(app_dir: str, name: str) -> None:
    path = os.path.join(app_dir, f"{name}.py")
    if not os.path.exists(path):
        return
    spec = importlib.util.spec_from_file_location(name, path)
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        sys.modules[f"app_{name}"] = module
        spec.loader.exec_module(module)


def _build_probe_routes() -> list[BaseRoute]:
    """Return deployment probes kept independent from application routing."""

    async def healthz(request: Request) -> JSONResponse:
        """Liveness probe: process routing is available."""
        from voodoo import __version__

        return JSONResponse({"status": "ok", "version": __version__})

    async def readyz(request: Request) -> JSONResponse:
        """Readiness probe backed by the Runtime-owned Store health contract."""
        lifecycle_phase = getattr(request.app.state, "lifecycle_phase", "unknown")
        if lifecycle_phase in {"starting", "stopping", "stopped"}:
            return JSONResponse(
                {
                    "status": "not_ready",
                    "mode": "shutting_down"
                    if lifecycle_phase in {"stopping", "stopped"}
                    else "starting",
                    "lifecycle_phase": lifecycle_phase,
                },
                status_code=503,
            )
        runtime_store = getattr(request.app.state, "runtime_store", None)
        try:
            health = runtime_store.health() if runtime_store is not None else None
        except _READINESS_STORE_ERRORS as error:
            logger.warning(
                "readiness Store health probe failed error=%s",
                redact_string(str(error)),
            )
            return JSONResponse(
                {
                    "status": "not_ready",
                    "mode": "store_unavailable",
                    "store": {"opened": False, "verified": False},
                },
                status_code=503,
            )
        from voodoo.status import _redact_store_details

        safe_store_details = _redact_store_details(
            health.details if health is not None else {}
        )
        if not isinstance(safe_store_details, dict):
            safe_store_details = {}
        from voodoo.data.base import migration_health

        migration = migration_health()
        migration_required = migration["status"] == "migration_required"
        capacity_pressure = bool(
            health is not None and not safe_store_details.get("within_limit", True)
        )
        recovery_mode = bool(
            health is not None
            and (
                safe_store_details.get("has_torn_tail") is True
                or (safe_store_details.get("pending_transactions") or 0) > 0
            )
        )
        ready = bool(
            health is not None
            and health.opened
            and health.verified
            and safe_store_details.get("within_limit", True)
            and not migration_required
        )
        if migration_required:
            mode = "migration_required"
        elif capacity_pressure:
            mode = "capacity_pressure"
        elif recovery_mode:
            mode = "recovery"
        elif ready:
            mode = "ready"
        else:
            mode = "not_ready"
        payload = {
            "status": "ready" if ready else "not_ready",
            "mode": mode,
            "migration": migration,
            "capacity_pressure": capacity_pressure,
            "recovery_mode": recovery_mode,
            "store": safe_store_details if health is not None else {"opened": False},
        }
        return JSONResponse(payload, status_code=200 if ready else 503)

    return [
        Route("/healthz", healthz, methods=["GET"]),
        Route("/readyz", readyz, methods=["GET"]),
    ]


def _build_routes(
    app_dir: str, cwd: str, config: Any
) -> tuple[list[BaseRoute], list[Any]]:
    from voodoo.mesh import mesh

    routes: list[BaseRoute] = [
        WebSocketRoute("/_voodoo_ws", websocket_endpoint),
        WebSocketRoute("/voodoo/mesh/ws", mesh._handle_websocket),
    ]

    routes.extend(_build_probe_routes())
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
        from voodoo.runtime.execution.engine import engine as runtime_engine

        gateway = DeviceGateway(InMemoryDeviceStore(), runtime_engine)
        edge_gateway.append(gateway)
        routes.extend(build_edge_routes(gateway))
    public_dir = os.path.join(cwd, "public")
    if os.path.isdir(public_dir):
        routes.append(
            Mount("/", app=StaticFiles(directory=public_dir), name="public-root")
        )
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
        from voodoo.runtime.execution.engine import engine as runtime_engine
    except ImportError:
        return None
    gateway = (
        edge_gateway[0]
        if edge_gateway
        else DeviceGateway(VoodooStoreDeviceStore(application_store), runtime_engine)
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


async def _cleanup_lifecycle_resources(
    *,
    runtime: Any,
    runtime_started: bool,
    mqtt_transport: Any,
    stop_workers: Callable[[], Any],
    worker_task: asyncio.Task[Any] | None,
    scheduler: Any,
    schedule_store: Any,
    execution_store: Any,
    runtime_engine: Any,
    store_bound: bool,
    application_store: Any,
) -> None:
    """Release every lifespan resource in a deterministic, failure-safe order."""
    if runtime is not None and runtime_started:
        runtime.stop()
    if mqtt_transport is not None:
        await mqtt_transport.stop()
    await stop_workers()
    if worker_task:
        worker_task.cancel()
        # Drain the task so cancellation cannot leak a pending task or replace
        # the original lifecycle failure with a warning.
        await asyncio.gather(worker_task, return_exceptions=True)

    from voodoo.data import close_db

    await close_db()
    if scheduler is not None:
        await scheduler.stop()
    if schedule_store is not None:
        schedule_store.close()
    close_store = getattr(execution_store, "close", None)
    if close_store is not None:
        close_store()
    runtime_engine.use_store(None)
    if store_bound:
        from voodoo.data.store_backend import bind_runtime_store

        bind_runtime_store(None)
    if application_store is not None:
        application_store.stop()
    from voodoo.ui.events import ws_manager

    ws_manager.reset()


def create_app(app_dir: str = "app", *, runtime: Any = None) -> Starlette:
    """Build a fully wired Starlette application."""
    from voodoo.config import get_config, validate_production_config
    from voodoo.ui.styles.presets import activate_theme

    config = get_config()
    validate_production_config(config)
    try:
        cwd = os.getcwd()
    except FileNotFoundError:
        cwd = "."
    activate_theme(config.theme.preset, project_root=cwd, mode=config.theme.mode)
    routes, edge_gateway = _build_routes(app_dir, cwd, config)

    from voodoo.auth import AuthMiddleware
    from voodoo.i18n import I18nMiddleware
    from voodoo.observability import TelemetryMiddleware
    from voodoo.runtime.scheduling.workers import start_workers, stop_workers
    from voodoo.security import (
        CORSMiddleware,
        CSRFMiddleware,
        RateLimitMiddleware,
        SecurityHeadersMiddleware,
    )

    @asynccontextmanager
    async def lifespan(starlette: Starlette) -> AsyncIterator[None]:
        from voodoo.data.store_backend import bind_runtime_store
        from voodoo.runtime.execution.engine import engine as global_runtime_engine
        from voodoo.runtime.store import StoreConfig, activate_runtime_store

        starlette.state.lifecycle_phase = "starting"
        application_store = None
        runtime_engine = runtime.engine if runtime is not None else global_runtime_engine
        execution_store = None
        schedule_store = None
        scheduler = None
        worker_task = None
        mqtt_transport = None
        runtime_started = False
        store_bound = False
        try:
            application_store = activate_runtime_store(
                StoreConfig.from_mapping(config.store.model_dump())
            )
            starlette.state.runtime_store = application_store
            if runtime is not None:
                runtime.use_store(application_store)
            bind_runtime_store(application_store)
            store_bound = True
            execution_store, schedule_path = _configure_execution_store(
                config, runtime_engine
            )
            if edge_gateway:
                from voodoo.edge import VoodooStoreDeviceStore

                edge_gateway[0]._store = VoodooStoreDeviceStore(application_store)
            from voodoo.runtime.scheduling import ScheduleService
            from voodoo.storage.scheduler import create_schedule_store

            schedule_store = create_schedule_store(schedule_path)
            scheduler = ScheduleService(schedule_store)
            await scheduler.start()
            from voodoo.runtime.scheduling.workers import _workers

            worker_task = asyncio.create_task(start_workers()) if _workers else None
            mqtt_transport = await _start_mqtt(config, edge_gateway, application_store)
            if runtime is not None:
                runtime.start()
                runtime_started = True
            starlette.state.lifecycle_phase = "ready"
            yield
        finally:
            starlette.state.lifecycle_phase = "stopping"
            await _cleanup_lifecycle_resources(
                runtime=runtime,
                runtime_started=runtime_started,
                mqtt_transport=mqtt_transport,
                stop_workers=stop_workers,
                worker_task=worker_task,
                scheduler=scheduler,
                schedule_store=schedule_store,
                execution_store=execution_store,
                runtime_engine=runtime_engine,
                store_bound=store_bound,
                application_store=application_store,
            )
            starlette.state.lifecycle_phase = "stopped"

    middleware = [
        Middleware(TelemetryMiddleware),
        Middleware(SecurityHeadersMiddleware, config_override=config),
        Middleware(CORSMiddleware, config_override=config),
        Middleware(I18nMiddleware),
        Middleware(AuthMiddleware, config_override=config),
        Middleware(RateLimitMiddleware, config_override=config),
        Middleware(CSRFMiddleware, config_override=config),
    ]
    starlette = Starlette(routes=routes, middleware=middleware, lifespan=lifespan)
    starlette.state.voodoo_config = config
    return starlette


def _module_page_endpoint(page_func: Callable[..., Any]) -> Callable:
    """Wrap a file-based page function into a Starlette endpoint."""

    async def handler(request: Request) -> Response:
        return await call_page(page_func, request)

    return handler


def _load_page_file(filepath: str, route_path: str, module_name: str) -> Route | None:
    """Import a single page module and return its Starlette Route."""
    spec = importlib.util.spec_from_file_location(module_name, filepath)
    if spec and spec.loader:
        page_module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = page_module
        spec.loader.exec_module(page_module)
        if hasattr(page_module, "page"):
            return Route(route_path, _module_page_endpoint(page_module.page))
    return None


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
                    part.replace("[", "{").replace("]", "}") for part in stem.split("/")
                ]
                route_path = "/" + "/".join(parts)
            clean_name = route_path.replace("/", "_").replace("{", "").replace("}", "")
            route = _load_page_file(filepath, route_path, f"pages_{clean_name}")
            if route:
                routes.append(route)


app = App()
