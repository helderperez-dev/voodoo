"""Browser event transport: WebSocket manager and event registration.

Internal today; the public surface (`event` decorator, state sync) lands in the
UI sprints and will build on this machinery.
"""

import inspect
import json
from collections.abc import Callable

from starlette.websockets import WebSocket, WebSocketDisconnect


class WebSocketManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_patch(self, element_id: str, html: str) -> None:
        message = json.dumps({"type": "patch", "id": element_id, "html": html})
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

    async def broadcast_append(self, element_id: str, html: str) -> None:
        message = json.dumps({"type": "append", "id": element_id, "html": html})
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass


ws_manager = WebSocketManager()
event_handlers: dict[str, Callable] = {}


def register_event(name: str, handler: Callable) -> None:
    event_handlers[name] = handler


def event(func: Callable) -> Callable:
    """Decorator: auto-register an async event handler by its function name.

    The handler signature is ``async def handler(element_id: str, value: Any)
    -> None``. The decorator is transparent — it returns the original function
    unchanged while registering it in the global ``event_handlers`` registry so
    the WebSocket transport can dispatch browser events to it::

        @event
        async def increment(element_id, value):
            count.set(count.get() + 1)
    """
    register_event(func.__name__, func)
    return func


async def websocket_endpoint(websocket: WebSocket) -> None:
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
