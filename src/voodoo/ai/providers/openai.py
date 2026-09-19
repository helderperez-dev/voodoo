"""Compatibility alias for :mod:`voodoo.integrations.ai.openai`."""

import sys

from voodoo.integrations.ai import openai

sys.modules[__name__] = openai
