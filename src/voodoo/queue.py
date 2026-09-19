"""Compatibility alias for :mod:`voodoo.workers.queue`."""

import sys

from voodoo.workers import queue

__all__ = getattr(queue, "__all__", ())

sys.modules[__name__] = queue
