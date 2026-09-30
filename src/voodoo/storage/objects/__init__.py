"""Object storage capability.

Voodoo Store is the canonical local-first object backend. Local filesystem and
S3 implementations remain explicit compatibility/infrastructure adapters.
"""

from voodoo.storage.objects.interfaces import VoodooObjectStore
from voodoo.storage.objects.local import LocalObjectStore
from voodoo.storage.objects.s3 import S3ObjectStore
from voodoo.storage.objects.store import VoodooStoreObjectStore

__all__ = [
    "VoodooObjectStore",
    "VoodooStoreObjectStore",
    "LocalObjectStore",
    "S3ObjectStore",
]
