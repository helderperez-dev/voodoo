"""Voodoo core runtime: application object, factory, error hierarchy.

Reactive state/events and page routing are re-exported here for backwards
compatibility; their implementations live in ``voodoo.ui`` and
``voodoo.routing`` respectively.
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
from voodoo.routing.pages import PageRegistry, call_page, page, page_registry
from voodoo.ui.events import (
    WebSocketManager,
    event,
    event_handlers,
    register_event,
    websocket_endpoint,
    ws_manager,
)
from voodoo.ui.rendering import render_page
from voodoo.ui.state import State, StateRenderer, state, state_renderer

__all__ = [
    "App",
    "create_app",
    "WebSocketManager",
    "event",
    "event_handlers",
    "register_event",
    "websocket_endpoint",
    "ws_manager",
    "render_page",
    "PageRegistry",
    "call_page",
    "page",
    "page_registry",
    "State",
    "StateRenderer",
    "state",
    "state_renderer",
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
