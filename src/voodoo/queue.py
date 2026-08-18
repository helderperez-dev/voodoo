"""Compatibility alias — the durable queue lives in ``voodoo.workers.queue``.

This shim replaces itself with the real module in ``sys.modules`` so that
``voodoo.queue is voodoo.workers.queue`` and mutable globals (``_workers``,
``_worker_tasks``) are always current.
"""

import sys

from voodoo.workers import queue  # noqa: F401

sys.modules[__name__] = queue
