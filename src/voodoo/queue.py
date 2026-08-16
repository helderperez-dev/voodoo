"""Compatibility alias — the single-process queue lives in
``voodoo.workers.queue``.

This shim replaces itself with the real module in ``sys.modules`` so that
``voodoo.queue is voodoo.workers.queue`` and mutable globals (``_queues``,
``_workers``) are always current. The static imports below are for type
checkers only (mypy cannot follow the runtime aliasing).
"""

import sys

from voodoo.workers import queue
from voodoo.workers.queue import (  # noqa: F401
    _queues,
    _worker_tasks,
    _workers,
    enqueue,
    start_workers,
    stop_workers,
)

sys.modules[__name__] = queue
