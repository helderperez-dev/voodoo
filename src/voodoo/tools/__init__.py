"""Compatibility shim — tools live in ``voodoo.ai.tools``.

Kept as a package (not a flat module) because tests and downstream code
import the ``voodoo.tools.registry`` submodule directly.
"""

from voodoo.ai.tools import ToolRegistry, ToolSpec, build_spec, default_registry, tool

__all__ = ["tool", "ToolSpec", "ToolRegistry", "default_registry", "build_spec"]
