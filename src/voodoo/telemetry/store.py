"""Compatibility alias for :mod:`voodoo.observability.store`."""

import sys

from voodoo.observability import store

sys.modules[__name__] = store
