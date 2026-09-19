"""Compatibility alias for :mod:`voodoo.integrations.ai.anthropic`."""

import sys

from voodoo.integrations.ai import anthropic

sys.modules[__name__] = anthropic
