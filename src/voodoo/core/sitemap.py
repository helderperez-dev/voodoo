"""SEO route artifacts: sitemap.xml and robots.txt generation."""

from __future__ import annotations

import ast
import os
from datetime import datetime
from typing import Any


def _route_is_excluded(filepath: str) -> bool:
    try:
        with open(filepath, encoding="utf-8") as file:
            tree = ast.parse(file.read(), filename=filepath)
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "SITEMAP_EXCLUDE"
                    and isinstance(node.value, ast.Constant)
                    and node.value.value is True
                ):
                    return True
    except Exception:
        return False
    return False


def _route_path(root: str, app_dir: str) -> str:
    rel_path = os.path.relpath(root, app_dir)
    return "/" if rel_path == "." else "/" + rel_path.replace("\\\\", "/")


def _last_modified(filepath: str) -> str:
    try:
        timestamp = os.path.getmtime(filepath)
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


def _discover_sitemap_routes(app_dir: str) -> list[tuple[str, str, str]]:
    routes: list[tuple[str, str, str]] = []
    if not os.path.exists(app_dir):
        return routes
    for root, _dirs, files in os.walk(app_dir):
        if "page.py" not in files:
            continue
        filepath = os.path.join(root, "page.py")
        route_path = _route_path(root, app_dir)
        if "[" in route_path or "{" in route_path or _route_is_excluded(filepath):
            continue
        priority = "1.0" if route_path == "/" else "0.8"
        routes.append((route_path, _last_modified(filepath), priority))
    routes.sort(key=lambda route: "" if route[0] == "/" else route[0])
    return routes


def _sitemap_location(route_path: str, base_url: str) -> str:
    if not base_url:
        return route_path
    root = base_url.rstrip("/")
    return f"{root}{route_path}" if route_path != "/" else f"{root}/"


def _generate_sitemap_xml(app_dir: str, base_url: str = "") -> str:
    """Auto-generates deterministic sitemap.xml from file-based routes."""
    urls = []
    for route_path, lastmod, priority in _discover_sitemap_routes(app_dir):
        loc = _sitemap_location(route_path, base_url)
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
    for path in seo_config.robots_disallow:
        if path:
            lines.append(f"Disallow: {path}")
    lines.append("")
    if not seo_config.allow_ai_crawlers:
        for crawler in ["GPTBot", "Claude-Web", "PerplexityBot", "ChatGPT-User", "anthropic-ai", "Bytespider"]:
            lines.extend([f"User-agent: {crawler}", "Disallow: /", ""])
    if seo_config.sitemap_enabled:
        effective_base = seo_config.base_url or base_url
        sitemap_url = f"{effective_base.rstrip('/')}/sitemap.xml" if effective_base else "/sitemap.xml"
        lines.append(f"Sitemap: {sitemap_url}")
    return "\n".join(lines)
