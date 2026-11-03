"""Shared helpers for tests that inspect rendered pages."""

from __future__ import annotations

import re

from voodoo.ui.assets import ASSET_PREFIX, read_asset

_LINK = re.compile(rf'(?:href|src)="{re.escape(ASSET_PREFIX)}([^"]+)"')


def linked_asset_names(html: str) -> list[str]:
    """Return the content-addressed asset file names a page references."""
    return _LINK.findall(html)


def page_css(html: str) -> str:
    """Return the concatenated stylesheet(s) a rendered page links to."""
    parts = []
    for name in linked_asset_names(html):
        asset = read_asset(name)
        if asset is not None and name.endswith(".css"):
            parts.append(asset.body.decode("utf-8"))
    return "\n".join(parts)


def page_js(html: str) -> str:
    """Return the client runtime script(s) a rendered page links to."""
    parts = []
    for name in linked_asset_names(html):
        asset = read_asset(name)
        if asset is not None and name.endswith(".js"):
            parts.append(asset.body.decode("utf-8"))
    return "\n".join(parts)


def page_with_assets(html: str) -> str:
    """Return the page plus everything it links (for substring assertions)."""
    return "\n".join((html, page_css(html), page_js(html)))
