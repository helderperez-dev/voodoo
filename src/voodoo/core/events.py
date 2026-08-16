"""Compatibility alias — browser events live in ``voodoo.ui.events``.

This shim replaces itself with the real module in ``sys.modules`` so that
``voodoo.core.events is voodoo.ui.events`` and the ``event_handlers`` registry
is shared. The static imports below are for type checkers only (mypy cannot
follow the runtime aliasing).
"""

import sys

from voodoo.ui import events
from voodoo.ui.events import (  # noqa: F401
    WebSocketManager,
    event,
    event_handlers,
    register_event,
    websocket_endpoint,
    ws_manager,
)

sys.modules[__name__] = events
