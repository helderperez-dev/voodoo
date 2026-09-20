"""Compatibility alias for :mod:`voodoo.ui.events`."""

import sys

from voodoo.ui import events

WebSocketManager = events.WebSocketManager
event = events.event
event_handlers = events.event_handlers
register_event = events.register_event
websocket_endpoint = events.websocket_endpoint
ws_manager = events.ws_manager

__all__ = [
    "WebSocketManager",
    "event",
    "event_handlers",
    "register_event",
    "websocket_endpoint",
    "ws_manager",
]

sys.modules[__name__] = events
