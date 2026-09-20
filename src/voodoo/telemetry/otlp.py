"""Compatibility alias for :mod:`voodoo.integrations.otel`."""

import sys

from voodoo.integrations import otel

sys.modules[__name__] = otel
