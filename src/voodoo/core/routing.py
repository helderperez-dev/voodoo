"""Compatibility alias for :mod:`voodoo.routing.pages`."""

import sys

from voodoo.routing import pages

PageRegistry = pages.PageRegistry
call_page = pages.call_page
page = pages.page
page_registry = pages.page_registry

__all__ = ["PageRegistry", "call_page", "page", "page_registry"]

sys.modules[__name__] = pages
