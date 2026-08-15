import asyncio
import json
import os
import importlib.util
from typing import Dict, Any, Callable
from starlette.applications import Starlette
from starlette.routing import Route, WebSocketRoute, Mount
from starlette.responses import HTMLResponse, Response
from starlette.websockets import WebSocket, WebSocketDisconnect
from starlette.staticfiles import StaticFiles
import inspect

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
event_handlers: Dict[str, Callable] = {}

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

def render_page(component) -> str:
    from voodoo.components import Component
    from voodoo.theme import default_theme
    
    html_content = component.render() if isinstance(component, Component) else str(component)
    
    # Read client.js
    client_js_path = os.path.join(os.path.dirname(__file__), "client.js")
    with open(client_js_path, "r") as f:
        client_js = f.read()
        
    tailwind_config = default_theme.to_tailwind_config()
    css_vars = default_theme.to_css_variables()
    
    # Check for theme cookie if available via a simple hack or rely on client side script
    # Better: handle it strictly on client side using JS on load to prevent flash of wrong theme
    
    html_class = f"dark {default_theme.mode}" if default_theme.mode == "dark" else default_theme.mode

    return f"""
    <!DOCTYPE html>
    <html lang="en" class="{html_class}">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Voodoo App</title>
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

def create_app(app_dir: str = "app") -> Starlette:
    from voodoo.config import config
    try:
        cwd = os.getcwd()
    except FileNotFoundError:
        cwd = "."
    base_storage_dir = os.path.join(cwd, config.storage_dir)
    public_storage_dir = os.path.join(base_storage_dir, "public")
    os.makedirs(public_storage_dir, exist_ok=True)
    
    from voodoo.mesh import mesh
    
    routes = [
        WebSocketRoute("/_voodoo_ws", websocket_endpoint),
        WebSocketRoute("/voodoo/mesh/ws", mesh._handle_websocket),
        Mount("/storage/public", app=StaticFiles(directory=public_storage_dir), name="storage_public"),
    ]
    
    # Simple file-based router (folder-based)
    for root, dirs, files in os.walk(app_dir):
        if "page.py" in files:
            filepath = os.path.join(root, "page.py")
            rel_path = os.path.relpath(root, app_dir)
            
            # Compute the route path
            if rel_path == ".":
                route_path = "/"
            else:
                # Convert path separators and change [param] to {param} for Starlette
                route_path = "/" + rel_path.replace("\\", "/").replace("[", "{").replace("]", "}")
            
            # Create a unique module name
            module_name = f"page_{route_path.replace('/', '_').replace('{', '').replace('}', '')}"
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            
            if spec and spec.loader:
                page_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(page_module)
                
                if hasattr(page_module, "page"):
                    def make_route(mod):
                        async def handler(request):
                            sig = inspect.signature(mod.page)
                            kwargs = {}
                            
                            # Inject request if requested
                            if "request" in sig.parameters:
                                kwargs["request"] = request
                                
                            # Inject dynamic path parameters (e.g. from /users/[id]/page.py)
                            for param in request.path_params:
                                if param in sig.parameters:
                                    kwargs[param] = request.path_params[param]
                                    
                            component = mod.page(**kwargs)
                            if inspect.iscoroutine(component):
                                component = await component
                            return HTMLResponse(render_page(component))
                        return handler
                        
                    routes.append(Route(route_path, make_route(page_module)))

    # Initialize components if needed
    models_path = os.path.join(app_dir, "models.py")
    if os.path.exists(models_path):
        spec = importlib.util.spec_from_file_location("models", models_path)
        if spec and spec.loader:
            models_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(models_module)

    workers_path = os.path.join(app_dir, "workers.py")
    if os.path.exists(workers_path):
        spec = importlib.util.spec_from_file_location("workers", workers_path)
        if spec and spec.loader:
            workers_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(workers_module)

    api_path = os.path.join(app_dir, "api.py")
    if os.path.exists(api_path):
        spec = importlib.util.spec_from_file_location("api", api_path)
        if spec and spec.loader:
            api_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(api_module)
            
    # Always include internal API routes (like /status) even if no user api.py exists
    from voodoo.api import api as voodoo_api
    routes.extend(voodoo_api.routes)

    from voodoo.queue import start_workers, stop_workers
    from voodoo.data import init_db
    from voodoo.telemetry import TelemetryMiddleware
    from voodoo.i18n import I18nMiddleware
    from starlette.middleware import Middleware
    from contextlib import asynccontextmanager
    
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
        Middleware(TelemetryMiddleware),
        Middleware(I18nMiddleware)
    ]

    app = Starlette(debug=True, routes=routes, middleware=middleware, lifespan=lifespan)
    
    return app
