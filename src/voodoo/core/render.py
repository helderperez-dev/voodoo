"""Compatibility shim — rendering lives in ``voodoo.ui.rendering`` and
sitemap/robots generation in ``voodoo.core.sitemap``."""

from voodoo.core.sitemap import _generate_robots_txt, _generate_sitemap_xml
from voodoo.ui.rendering import render_page

__all__ = ["render_page", "_generate_sitemap_xml", "_generate_robots_txt"]
