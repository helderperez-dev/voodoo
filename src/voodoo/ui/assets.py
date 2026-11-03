"""Content-addressed static assets for the Voodoo UI.

The framework stylesheet and client runtime used to be inlined into every HTML
response. That made each page ~150 KB heavier, prevented browser caching and
required ``unsafe-inline`` styles, which production CSP forbids.

Assets are now published once under a URL derived from the SHA-256 of their
bytes::

    /_voodoo/assets/<digest>.css
    /_voodoo/assets/<digest>.js

Because the name changes whenever the content changes (a theme switch, a
framework upgrade), responses can be cached as ``immutable`` for a year and the
browser never serves a stale stylesheet.
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock

from starlette.requests import Request
from starlette.responses import Response

__all__ = [
    "ASSET_PREFIX",
    "Asset",
    "asset_route_handler",
    "publish_asset",
    "read_asset",
    "reset_assets",
]

ASSET_PREFIX = "/_voodoo/assets/"
#: One year; safe because the URL is derived from the content.
_CACHE_CONTROL = "public, max-age=31536000, immutable"
#: Distinct themes or framework builds kept resident. Old digests that fall out
#: simply stop being servable; pages always reference the newest digest.
_MAX_ASSETS = 32
_CONTENT_TYPES = {
    "css": "text/css; charset=utf-8",
    "js": "text/javascript; charset=utf-8",
}
_DIGEST_LENGTH = 16


@dataclass(frozen=True)
class Asset:
    """An immutable published asset."""

    name: str
    body: bytes
    content_type: str

    @property
    def url(self) -> str:
        return f"{ASSET_PREFIX}{self.name}"

    @property
    def etag(self) -> str:
        return f'"{self.name.rsplit(".", 1)[0]}"'


_lock = Lock()
_assets: OrderedDict[str, Asset] = OrderedDict()


def publish_asset(content: str, kind: str) -> Asset:
    """Publish ``content`` and return its content-addressed :class:`Asset`.

    Publishing identical content again returns the existing asset, so rendering
    a page on every request costs a hash, not a copy.
    """
    if kind not in _CONTENT_TYPES:
        raise ValueError(f"unsupported asset kind: {kind!r}")
    body = content.encode("utf-8")
    digest = hashlib.sha256(body).hexdigest()[:_DIGEST_LENGTH]
    name = f"{digest}.{kind}"
    with _lock:
        existing = _assets.get(name)
        if existing is not None:
            _assets.move_to_end(name)
            return existing
        asset = Asset(name=name, body=body, content_type=_CONTENT_TYPES[kind])
        _assets[name] = asset
        while len(_assets) > _MAX_ASSETS:
            _assets.popitem(last=False)
        return asset


def read_asset(name: str) -> Asset | None:
    """Return a published asset by file name, or ``None``."""
    with _lock:
        return _assets.get(name)


def reset_assets() -> None:
    """Forget every published asset (test isolation)."""
    with _lock:
        _assets.clear()


async def asset_route_handler(request: Request) -> Response:
    """Serve a published asset with immutable caching and conditional GET."""
    asset = read_asset(request.path_params["name"])
    if asset is None:
        return Response("Not found", status_code=404, media_type="text/plain")
    headers = {
        "Cache-Control": _CACHE_CONTROL,
        "ETag": asset.etag,
        "X-Content-Type-Options": "nosniff",
    }
    if request.headers.get("if-none-match") == asset.etag:
        return Response(status_code=304, headers=headers)
    return Response(asset.body, media_type=asset.content_type, headers=headers)
