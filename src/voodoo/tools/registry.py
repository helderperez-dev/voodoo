"""Compatibility alias — the tool registry lives in ``voodoo.ai.tools.registry``.

This shim replaces itself with the real module in ``sys.modules`` so that
``voodoo.tools.registry is voodoo.ai.tools.registry`` and the
``default_registry`` singleton (including test monkeypatching) is shared.
The static imports below are for type checkers only (mypy cannot follow the
runtime aliasing).
"""

import sys

from voodoo.ai.tools import registry
from voodoo.ai.tools.registry import (  # noqa: F401
    ToolRegistry,
    ToolSpec,
    build_spec,
    default_registry,
)

sys.modules[__name__] = registry
