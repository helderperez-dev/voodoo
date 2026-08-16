"""Backwards-compatible re-export of the real Agent from ``voodoo.ai.agent``.

The implementation lives in :mod:`voodoo.ai.agent`; this module preserves
the original ``from voodoo.agent import Agent`` import path.
"""

from voodoo.ai.agent import Agent, AgentEvent, AgentRun

__all__ = ["Agent", "AgentRun", "AgentEvent"]
