"""Voodoo core runtime: application object, factory, rendering, events,
routing primitives and the error hierarchy.
"""

from voodoo.core.app import App, create_app
from voodoo.core.errors import (
    AgentError,
    AuthError,
    ComponentError,
    ConfigurationError,
    DataError,
    EventError,
    MCPError,
    MeshError,
    RoutingError,
    StateError,
    ToolError,
    VoodooError,
)
from voodoo.core.events import (
    WebSocketManager,
    event_handlers,
    register_event,
    websocket_endpoint,
    ws_manager,
)
from voodoo.core.render import render_page
from voodoo.core.routing import PageRegistry, call_page, page, page_registry

__all__ = [
    "App",
    "create_app",
    "WebSocketManager",
    "event_handlers",
    "register_event",
    "websocket_endpoint",
    "ws_manager",
    "render_page",
    "PageRegistry",
    "call_page",
    "page",
    "page_registry",
    "VoodooError",
    "ConfigurationError",
    "RoutingError",
    "ComponentError",
    "StateError",
    "EventError",
    "MeshError",
    "MCPError",
    "DataError",
    "AuthError",
    "AgentError",
    "ToolError",
]
