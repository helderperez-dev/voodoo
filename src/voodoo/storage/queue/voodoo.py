"""Compatibility alias for the canonical Voodoo Store queue adapter."""

from voodoo.storage.queue.store import VoodooStoreQueue, _native_id, _public_id

__all__ = ["VoodooStoreQueue", "_native_id", "_public_id"]
