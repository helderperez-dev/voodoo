"""Compatibility alias — page routing lives in ``voodoo.routing.pages``.

This shim replaces itself with the real module in ``sys.modules`` so that
``voodoo.core.routing is voodoo.routing.pages``. The static imports below are
for type checkers only (mypy cannot follow the runtime aliasing).
"""

import sys

from voodoo.routing import pages
from voodoo.routing.pages import (  # noqa: F401
    PageRegistry,
    call_page,
    page,
    page_registry,
)

sys.modules[__name__] = pages
