"""Compatibility alias for :mod:`voodoo.integrations.mcp.client`."""

import sys

from voodoo.integrations.mcp import client

sys.modules[__name__] = client
