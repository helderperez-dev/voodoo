"""Voodoo — programmable runtime for adaptive applications and operational systems.

The package root is intentionally small. It exposes only the common application
vocabulary. Catalogs and advanced primitives live in the namespace that owns
their semantics: voodoo.ui, voodoo.runtime, voodoo.world, voodoo.edge,
voodoo.protocol, voodoo.observability and voodoo.integrations.
"""

from .ai.agent import Agent
from .ai.tools import tool
from .core import App, page, state
from .data import Model
from .runtime.scheduling.tasks import task

__version__ = "3.0.0"

__all__ = [
    "Agent",
    "App",
    "Model",
    "page",
    "state",
    "task",
    "tool",
]
