"""Compatibility alias — the JSON API namespace lives in ``voodoo.routing.api``.

This shim replaces itself with the real module in ``sys.modules`` so that
``voodoo.api is voodoo.routing.api``. The static imports below are for type
checkers only (mypy cannot follow the runtime aliasing).
"""

import sys

from voodoo.routing import api
from voodoo.routing.api import API  # noqa: F401

sys.modules[__name__] = api
