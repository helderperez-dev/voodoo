"""Compatibility alias for :mod:`voodoo.observability.middleware`."""

import sys

from voodoo.observability import middleware

sys.modules[__name__] = middleware
