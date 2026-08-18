"""Voodoo style adapters.

The native Voodoo CSS adapter is the default; Tailwind is opt-in::

    from voodoo import TailwindAdapter, set_style_adapter
    set_style_adapter(TailwindAdapter())
"""

from voodoo.adapters.capabilities import (
    AdapterCapabilities,
    CapabilityError,
    DatabaseCapabilities,
    EventBusCapabilities,
    ObjectStoreCapabilities,
    QueueCapabilities,
    capability_matrix,
    negotiate,
    require,
)
from voodoo.adapters.registry import ProviderRegistry, registry
from voodoo.adapters.tailwind import TailwindAdapter
from voodoo.adapters.voodoo_css import VoodooCSSAdapter, generate_component_css

__all__ = [
    "TailwindAdapter",
    "VoodooCSSAdapter",
    "generate_component_css",
    "AdapterCapabilities",
    "CapabilityError",
    "DatabaseCapabilities",
    "EventBusCapabilities",
    "ObjectStoreCapabilities",
    "QueueCapabilities",
    "capability_matrix",
    "negotiate",
    "require",
    "ProviderRegistry",
    "registry",
]
