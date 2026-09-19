"""Compatibility facade for durable Runtime worker scheduling."""

import sys

from voodoo.runtime.scheduling import workers as _workers

sys.modules[__name__] = _workers
