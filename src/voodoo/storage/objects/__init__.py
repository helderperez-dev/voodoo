"""Object storage capability (Sprint 6).

``LocalObjectStore`` is the default embedded backend under
``.voodoo/objects/``. ``VoodooObjectStore`` is the protocol every backend
implements.
"""

from voodoo.storage.objects.interfaces import VoodooObjectStore
from voodoo.storage.objects.local import LocalObjectStore
from voodoo.storage.objects.s3 import S3ObjectStore\nfrom voodoo.storage.objects.store import VoodooStoreObjectStore

__all__ = [\n    "VoodooObjectStore",\n    "VoodooStoreObjectStore",\n    "LocalObjectStore",\n    "S3ObjectStore",\n]
