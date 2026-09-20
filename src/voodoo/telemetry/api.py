"""Compatibility alias for :mod:`voodoo.observability.api`."""

import sys

from voodoo.observability import api

sys.modules[__name__] = api
