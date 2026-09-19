"""Compatibility alias for :mod:`voodoo.integrations.ai.gemini`."""

import sys

from voodoo.integrations.ai import gemini

sys.modules[__name__] = gemini
