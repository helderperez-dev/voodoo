"""Compatibility alias for :mod:`voodoo.integrations.mcp`."""

import sys

from voodoo.integrations import mcp

sys.modules[__name__] = mcp
