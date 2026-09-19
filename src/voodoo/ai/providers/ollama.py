"""Compatibility alias for :mod:`voodoo.integrations.ai.ollama`."""

import sys

from voodoo.integrations.ai import ollama

sys.modules[__name__] = ollama
