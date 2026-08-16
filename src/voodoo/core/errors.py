"""Voodoo error hierarchy.

Every framework error derives from `VoodooError` so applications can catch the
whole framework surface with one exception type. Subsystems may extend these
(e.g. `voodoo.auth.AuthError`) without introducing new roots.
"""


class VoodooError(Exception):
    """Base class for all Voodoo framework errors."""


class ConfigurationError(VoodooError):
    """Invalid or missing configuration (env vars, provider keys, options)."""


class RoutingError(VoodooError):
    """Route registration or path resolution failure."""


class ComponentError(VoodooError):
    """Component construction or rendering failure."""


class StateError(VoodooError):
    """Reactive state misuse or propagation failure."""


class EventError(VoodooError):
    """Browser/UI event handling failure."""


class MeshError(VoodooError):
    """Mesh event or remote-call failure."""


class MCPError(VoodooError):
    """MCP protocol or tool-exposure failure."""


class DataError(VoodooError):
    """Database or model operation failure."""


class AuthError(VoodooError):
    """Authentication or authorization failure."""

    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class AgentError(VoodooError):
    """Agent execution failure."""


class ToolError(VoodooError):
    """Tool registration or execution failure."""
