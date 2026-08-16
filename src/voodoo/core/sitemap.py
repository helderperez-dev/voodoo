"""SEO route artifacts: sitemap.xml and robots.txt generation.

Deterministic, filesystem-derived — consumed by the application factory
(``voodoo.core.app``). Kept in ``core`` because it is a routing/SEO concern,
not a rendering one.
"""

from __future__ import annotations

import ast
import os
from datetime import datetime
from typing import Any


def _generate_sitemap_xml(app_dir: str, base_url: str = "") -> str:  # noqa: C901
    """Auto-generates deterministic sitemap.xml from file-based routes."""

    discovered_routes = []

    if os.path.exists(app_dir):
        for root, _dirs, files in os.walk(app_dir):
            if "page.py" in files:
                filepath = os.path.join(root, "page.py")
                rel_path = os.path.relpath(root, app_dir)

                # Compute the route path
                if rel_path == ".":
                    route_path = "/"
                else:
                    route_path = "/" + rel_path.replace("\\", "/")

                # Skip dynamic routes (contain [param]) from static sitemap
                if "[" in route_path or "{" in route_path:
                    continue

                # Check for SITEMAP_EXCLUDE flag in the module without executing it
                try:
                    with open(filepath, encoding="utf-8") as f:
                        tree = ast.parse(f.read(), filename=filepath)

                    exclude = False
                    for node in tree.body:
                        if isinstance(node, ast.Assign):
                            for target in node.targets:
                                if (
                                    isinstance(target, ast.Name)
                                    and target.id == "SITEMAP_EXCLUDE"
                                ):
                                    if (
                                        isinstance(node.value, ast.Constant)
                                        and node.value.value is True
                                    ):
                                        exclude = True
                    if exclude:
                        continue
                except Exception:
                    pass

                # Get last modified time of the file
                try:
                    mtime = os.path.getmtime(filepath)
                    lastmod = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
                except Exception:
                    lastmod = datetime.now().strftime("%Y-%m-%d")

                # Priority: homepage gets 1.0, others get 0.8
                priority = "1.0" if route_path == "/" else "0.8"
                discovered_routes.append((route_path, lastmod, priority))

    # Sort deterministically: root "/" first, then alphabetical
    discovered_routes.sort(key=lambda r: "" if r[0] == "/" else r[0])

    urls = []
    for route_path, lastmod, priority in discovered_routes:
        if base_url:
            loc = (
                f"{base_url.rstrip('/')}{route_path}"
                if route_path != "/"
                else f"{base_url.rstrip('/')}/"
            )
        else:
            loc = route_path

        urls.append(f"""    <url>
        <loc>{loc}</loc>
        <lastmod>{lastmod}</lastmod>
        <changefreq>weekly</changefreq>
        <priority>{priority}</priority>
    </url>""")

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>"""


def _generate_robots_txt(seo_config: Any, base_url: str = "") -> str:
    """Auto-generates robots.txt with sensible defaults."""
    lines = ["User-agent: *"]

    # Disallowed paths
    for path in seo_config.robots_disallow:
        if path:
            lines.append(f"Disallow: {path}")

    lines.append("")  # blank line

    # AI crawler policy
    if not seo_config.allow_ai_crawlers:
        ai_crawlers = [
            "GPTBot",
            "Claude-Web",
            "PerplexityBot",
            "ChatGPT-User",
            "anthropic-ai",
            "Bytespider",
        ]
        for crawler in ai_crawlers:
            lines.append(f"User-agent: {crawler}")
            lines.append("Disallow: /")
            lines.append("")

    # Sitemap
    if seo_config.sitemap_enabled:
        effective_base = seo_config.base_url or base_url
        sitemap_url = (
            f"{effective_base.rstrip('/')}/sitemap.xml"
            if effective_base
            else "/sitemap.xml"
        )
        lines.append(f"Sitemap: {sitemap_url}")

    return "\n".join(lines)
