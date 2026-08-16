"""Compatibility alias — reactive state lives in ``voodoo.ui.state``.

This shim replaces itself with the real module in ``sys.modules`` so that
``voodoo.core.state is voodoo.ui.state`` and the ``state_renderer`` singleton
is shared. The static imports below are for type checkers only (mypy cannot
follow the runtime aliasing).
"""

import sys

from voodoo.ui import state
from voodoo.ui.state import (  # noqa: F401
    State,
    StateRenderer,
    state_renderer,
)

sys.modules[__name__] = state
