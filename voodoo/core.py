import asyncio
import importlib.util
import inspect
import json
import os
import sys
from collections.abc import Callable
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from starlette.routing import BaseRoute, Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket, WebSocketDisconnect


class WebSocketManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_patch(self, element_id: str, html: str):
        message = json.dumps({"type": "patch", "id": element_id, "html": html})
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

    async def broadcast_append(self, element_id: str, html: str):
        message = json.dumps({"type": "append", "id": element_id, "html": html})
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass


ws_manager = WebSocketManager()
event_handlers: dict[str, Callable] = {}


def register_event(name: str, handler: Callable):
    event_handlers[name] = handler


async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            print(f"WS Received: {data}")
            msg = json.loads(data)
            if msg.get("type") == "event":
                handler = event_handlers.get(msg["event"])
                if handler:
                    if inspect.iscoroutinefunction(handler):
                        await handler(msg["id"], msg["value"])
                    else:
                        handler(msg["id"], msg["value"])
    except WebSocketDisconnect as e:
        # 1000 = Normal Closure, 1001 = Going Away (e.g. page reload)
        if getattr(e, "code", None) not in (1000, 1001):
            print(f"WS Disconnected with code: {getattr(e, 'code', 'unknown')}")
    except Exception as e:
        err_str = str(e)
        if "1000" not in err_str and "1001" not in err_str:
            print(f"WS Error: {err_str}")
    finally:
        ws_manager.disconnect(websocket)


# In-memory cache for client.js to prevent disk I/O on every request
_client_js_cache: str | None = None


def _get_client_js() -> str:
    global _client_js_cache
    if _client_js_cache is None:
        client_js_path = os.path.join(os.path.dirname(__file__), "client.js")
        try:
            with open(client_js_path, encoding="utf-8") as f:
                _client_js_cache = f.read()
        except Exception:
            _client_js_cache = ""
    return _client_js_cache


def render_page(component, seo=None) -> str:
    """
    Renders a full HTML page with the given component tree and optional SEO metadata.

    Args:
        component: A Component instance, a string, or a tuple of (SEO, Component) / (Component, SEO).
        seo: An optional SEO instance with page-level metadata.
    """
    from voodoo.components import Component
    from voodoo.config import config
    from voodoo.seo import SEO
    from voodoo.theme import default_theme

    # Handle tuple if passed directly as component
    if isinstance(component, tuple) and len(component) == 2:
        first, second = component
        if isinstance(first, SEO):
            seo = first
            component = second
        elif isinstance(second, SEO):
            seo = second
            component = first

    # Use provided SEO or create defaults
    if seo is None:
        seo = SEO()

    seo_config = config.seo

    html_content = (
        component.render() if isinstance(component, Component) else str(component)
    )

    client_js = _get_client_js()
    tailwind_config = default_theme.to_tailwind_config()
    css_vars = default_theme.to_css_variables()

    html_class = (
        f"dark {default_theme.mode}"
        if default_theme.mode == "dark"
        else default_theme.mode
    )

    # --- SEO: Build <head> content ---
    page_lang = seo.lang or seo_config.default_lang or "en"
    page_title = seo.title

    # Meta tags (description, robots, canonical, OG, Twitter, GEO author/dates, hreflang)
    meta_tags = seo.render_meta_tags(
        site_name=seo_config.site_name,
        base_url=seo_config.base_url,
        default_og_image=seo_config.default_og_image,
    )

    # Structured data (JSON-LD)
    structured_data = seo.render_structured_data(
        site_name=seo_config.site_name,
        base_url=seo_config.base_url,
    )

    # Generator meta tag
    generator_tag = (
        '<meta name="generator" content="Voodoo Framework">'
        if seo_config.generator_meta
        else ""
    )

    return f"""
    <!DOCTYPE html>
    <html lang="{page_lang}" class="{html_class}">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{page_title}</title>
        {meta_tags}
        {generator_tag}
        {structured_data}
        <script src="https://cdn.tailwindcss.com"></script>
        <script>
            tailwind.config = {tailwind_config};

            // Prevent flash of incorrect theme
            if (document.cookie.includes('voodoo_theme=light')) {{
                document.documentElement.classList.remove('dark');
                document.documentElement.classList.add('light');
            }} else if (document.cookie.includes('voodoo_theme=dark')) {{
                document.documentElement.classList.remove('light');
                document.documentElement.classList.add('dark');
            }}
        </script>
        <style>
            {css_vars}
            body {{
                background-color: var(--color-background);
                color: var(--color-text);
                font-family: var(--font-sans);
            }}
            ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
            ::-webkit-scrollbar-track {{ background: transparent; }}
            ::-webkit-scrollbar-thumb {{ background: var(--color-surface); border-radius: 4px; border: 1px solid var(--color-border); }}
            ::-webkit-scrollbar-thumb:hover {{ background: var(--color-text-muted); }}
        </style>
    </head>
    <body class="bg-[var(--color-background)] text-[var(--color-text)] min-h-screen antialiased selection:bg-[var(--color-secondary)] selection:text-white">
        <div id="root">
            {html_content}
        </div>
        <script>
            {client_js}
        </script>
    </body>
    </html>
    """


def _generate_sitemap_xml(app_dir: str, base_url: str = "") -> str:  # noqa: C901
    """Auto-generates deterministic sitemap.xml from file-based routes."""
    from datetime import datetime

    discovered_routes = []

    if os.path.exists(app_dir):
        for root, _dirs, files in os.walk(app_dir):
            if "page.py" in files:
                filepath = os.path.join(root, "page.py")
                rel_path = os.path.relpath(root, app_dir)

                # Compute the route path
                if rel_path == ".":
                    route_path = "/"
                else:
                    route_path = "/" + rel_path.replace("\\", "/")

                # Skip dynamic routes (contain [param]) from static sitemap
                if "[" in route_path or "{" in route_path:
                    continue

                # Check for SITEMAP_EXCLUDE flag in the module without executing it
                try:
                    import ast

                    with open(filepath, encoding="utf-8") as f:
                        tree = ast.parse(f.read(), filename=filepath)

                    exclude = False
                    for node in tree.body:
                        if isinstance(node, ast.Assign):
                            for target in node.targets:
                                if (
                                    isinstance(target, ast.Name)
                                    and target.id == "SITEMAP_EXCLUDE"
                                ):
                                    if (
                                        isinstance(node.value, ast.Constant)
                                        and node.value.value is True
                                    ):
                                        exclude = True
                    if exclude:
                        continue
                except Exception:
                    pass

                # Get last modified time of the file
                try:
                    mtime = os.path.getmtime(filepath)
                    lastmod = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
                except Exception:
                    lastmod = datetime.now().strftime("%Y-%m-%d")

                # Priority: homepage gets 1.0, others get 0.8
                priority = "1.0" if route_path == "/" else "0.8"
                discovered_routes.append((route_path, lastmod, priority))

    # Sort deterministically: root "/" first, then alphabetical
    discovered_routes.sort(key=lambda r: "" if r[0] == "/" else r[0])

    urls = []
    for route_path, lastmod, priority in discovered_routes:
        if base_url:
            loc = (
                f"{base_url.rstrip('/')}{route_path}"
                if route_path != "/"
                else f"{base_url.rstrip('/')}/"
            )
        else:
            loc = route_path

        urls.append(f"""    <url>
        <loc>{loc}</loc>
        <lastmod>{lastmod}</lastmod>
        <changefreq>weekly</changefreq>
        <priority>{priority}</priority>
    </url>""")

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>"""


def _generate_robots_txt(seo_config, base_url: str = "") -> str:
    """Auto-generates robots.txt with sensible defaults."""
    lines = ["User-agent: *"]

    # Disallowed paths
    for path in seo_config.robots_disallow:
        if path:
            lines.append(f"Disallow: {path}")

    lines.append("")  # blank line

    # AI crawler policy
    if not seo_config.allow_ai_crawlers:
        ai_crawlers = [
            "GPTBot",
            "Claude-Web",
            "PerplexityBot",
            "ChatGPT-User",
            "anthropic-ai",
            "Bytespider",
        ]
        for crawler in ai_crawlers:
            lines.append(f"User-agent: {crawler}")
            lines.append("Disallow: /")
            lines.append("")

    # Sitemap
    if seo_config.sitemap_enabled:
        effective_base = seo_config.base_url or base_url
        sitemap_url = (
            f"{effective_base.rstrip('/')}/sitemap.xml"
            if effective_base
            else "/sitemap.xml"
        )
        lines.append(f"Sitemap: {sitemap_url}")

    return "\n".join(lines)


def create_app(app_dir: str = "app") -> Starlette:  # noqa: C901
    from voodoo.config import config

    try:
        cwd = os.getcwd()
    except FileNotFoundError:
        cwd = "."
    base_storage_dir = os.path.join(cwd, config.storage_dir)
    public_storage_dir = os.path.join(base_storage_dir, "public")
    os.makedirs(public_storage_dir, exist_ok=True)

    from voodoo.mesh import mesh

    routes: list[BaseRoute] = [
        WebSocketRoute("/_voodoo_ws", websocket_endpoint),
        WebSocketRoute("/voodoo/mesh/ws", mesh._handle_websocket),
        Mount(
            "/storage/public",
            app=StaticFiles(directory=public_storage_dir),
            name="storage_public",
        ),
    ]

    # --- SEO: Auto-generate sitemap.xml and robots.txt ---
    seo_config = config.seo

    if seo_config.sitemap_enabled:

        def sitemap_handler(request: Request):
            effective_base = seo_config.base_url or str(request.base_url).rstrip("/")
            xml = _generate_sitemap_xml(app_dir, effective_base)
            return Response(content=xml, media_type="application/xml")

        routes.append(Route("/sitemap.xml", sitemap_handler, methods=["GET"]))

    if seo_config.robots_enabled:

        def robots_handler(request: Request):
            effective_base = seo_config.base_url or str(request.base_url).rstrip("/")
            txt = _generate_robots_txt(seo_config, effective_base)
            return Response(content=txt, media_type="text/plain")

        routes.append(Route("/robots.txt", robots_handler, methods=["GET"]))

    # Simple file-based router (folder-based)
    if os.path.exists(app_dir):
        for root, _dirs, files in os.walk(app_dir):
            if "page.py" in files:
                filepath = os.path.join(root, "page.py")
                rel_path = os.path.relpath(root, app_dir)

                # Compute the route path
                if rel_path == ".":
                    route_path = "/"
                else:
                    # Convert path separators and change [param] to {param} for Starlette
                    route_path = "/" + rel_path.replace("\\", "/").replace(
                        "[", "{"
                    ).replace("]", "}")

                # Create a unique module name
                clean_name = (
                    route_path.replace("/", "_").replace("{", "").replace("}", "")
                )
                module_name = f"page_{clean_name}"
                spec = importlib.util.spec_from_file_location(module_name, filepath)

                if spec and spec.loader:
                    page_module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = page_module
                    spec.loader.exec_module(page_module)

                    if hasattr(page_module, "page"):

                        def make_route(mod):  # noqa: C901
                            async def handler(request: Request):  # noqa: C901
                                from voodoo.seo import SEO

                                sig = inspect.signature(mod.page)
                                kwargs: dict[str, Any] = {}

                                # Inject request if requested
                                if "request" in sig.parameters:
                                    kwargs["request"] = request

                                # Inject user if requested
                                if "user" in sig.parameters:
                                    from voodoo.auth import get_current_user

                                    kwargs["user"] = get_current_user(request)

                                # Inject dynamic path parameters with type coercion if annotated
                                for param, val in request.path_params.items():
                                    if param in sig.parameters:
                                        param_type = sig.parameters[param].annotation
                                        if (
                                            param_type is not inspect._empty
                                            and callable(param_type)
                                        ):
                                            try:
                                                val = param_type(val)
                                            except (ValueError, TypeError):
                                                pass
                                        kwargs[param] = val

                                result = mod.page(**kwargs)
                                if inspect.iscoroutine(result):
                                    result = await result

                                # If the page function returns a direct Starlette Response (e.g. RedirectResponse, HTMLResponse), return it
                                if isinstance(result, Response):
                                    return result

                                # Detect (SEO, Component) or (Component, SEO) tuple vs plain Component
                                seo = None
                                component = result
                                if isinstance(result, tuple) and len(result) == 2:
                                    first, second = result
                                    if isinstance(first, SEO):
                                        seo = first
                                        component = second
                                    elif isinstance(second, SEO):
                                        seo = second
                                        component = first

                                return HTMLResponse(render_page(component, seo=seo))

                            return handler

                        routes.append(Route(route_path, make_route(page_module)))

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
    from voodoo.api import api as voodoo_api

    routes.extend(voodoo_api.routes)

    from contextlib import asynccontextmanager

    from starlette.middleware import Middleware

    from voodoo.auth import AuthMiddleware
    from voodoo.data import init_db
    from voodoo.i18n import I18nMiddleware
    from voodoo.queue import start_workers, stop_workers
    from voodoo.security import (
        CORSMiddleware,
        CSRFMiddleware,
        RateLimitMiddleware,
        SecurityHeadersMiddleware,
    )
    from voodoo.telemetry import TelemetryMiddleware

    @asynccontextmanager
    async def lifespan(app: Starlette):
        # Startup
        await init_db()
        worker_task = asyncio.create_task(start_workers())
        yield
        # Shutdown
        await stop_workers()
        worker_task.cancel()

    middleware = [
        Middleware(SecurityHeadersMiddleware),
        Middleware(CORSMiddleware),
        Middleware(RateLimitMiddleware),
        Middleware(CSRFMiddleware),
        Middleware(TelemetryMiddleware),
        Middleware(I18nMiddleware),
        Middleware(AuthMiddleware),
    ]

    app = Starlette(debug=True, routes=routes, middleware=middleware, lifespan=lifespan)

    return app
