"""Compatibility alias for :mod:`voodoo.routing.api`."""

import sys

from voodoo.routing import api

API = api.API
__all__ = ["API"]

sys.modules[__name__] = api
