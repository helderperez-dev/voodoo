"""Server-side rendering: full HTML documents from component trees, plus
sitemap/robots generation consumed by the application factory.
"""

import os
from typing import Any

# In-memory cache for client.js and styles.css to prevent disk I/O on every request
_client_js_cache: str | None = None
_styles_css_cache: str | None = None


def _read_optional(path: str) -> str:
    """Read a file if it exists; return ``""`` otherwise."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _get_client_js() -> str:
    global _client_js_cache
    if _client_js_cache is None:
        client_js_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "client.js"
        )
        _client_js_cache = _read_optional(client_js_path)
    return _client_js_cache


def _get_project_styles() -> str:
    """Load a project-level ``styles.css`` (next to the app dir) by convention.

    Apps can drop a ``styles.css`` file in their root to add custom CSS beyond
    the theme. The file is read once and cached.
    """
    global _styles_css_cache
    if _styles_css_cache is None:
        candidate = os.path.join(os.getcwd(), "styles.css")
        _styles_css_cache = _read_optional(candidate)
    return _styles_css_cache


def render_page(component: Any, seo: Any = None) -> str:
    """
    Renders a full HTML page with the given component tree and optional SEO metadata.

    Args:
        component: A Component instance, a string, or a tuple of (SEO, Component) / (Component, SEO).
        seo: An optional SEO instance with page-level metadata.
    """
    from voodoo.config import config
    from voodoo.seo import SEO
    from voodoo.theme import default_theme
    from voodoo.ui.component import Component

    # Handle tuple if passed directly as component
    if isinstance(component, tuple) and len(component) == 2:
        first, second = component
        if isinstance(first, SEO):
            seo = first
            component = second
        elif isinstance(second, SEO):
            seo = second
            component = first

    # Use provided SEO or create defaults
    if seo is None:
        seo = SEO()

    seo_config = config.seo

    html_content = (
        component.render() if isinstance(component, Component) else str(component)
    )

    client_js = _get_client_js()
    project_styles = _get_project_styles()
    css_vars = default_theme.to_css_variables()

    # Detect active adapter to include the right CSS runtime
    from voodoo.adapters.voodoo_css import VoodooCSSAdapter, generate_component_css
    from voodoo.ui.styles import current_adapter

    adapter = current_adapter()
    is_voodoo_css = isinstance(adapter, VoodooCSSAdapter)

    if is_voodoo_css:
        component_css = generate_component_css(default_theme)
        head_scripts = ""
        body_classes = "min-h-screen antialiased"
    else:
        tailwind_config = default_theme.to_tailwind_config()
        component_css = ""
        head_scripts = f"""
        <script src="https://cdn.tailwindcss.com"></script>
        <script>
            tailwind.config = {tailwind_config};

            // Prevent flash of incorrect theme
            if (document.cookie.includes('voodoo_theme=light')) {{
                document.documentElement.classList.remove('dark');
                document.documentElement.classList.add('light');
            }} else if (document.cookie.includes('voodoo_theme=dark')) {{
                document.documentElement.classList.remove('light');
                document.documentElement.classList.add('dark');
            }}
        </script>
        """
        body_classes = (
            "bg-[var(--vd-color-background)] text-[var(--vd-color-text)] "
            "min-h-screen antialiased "
            "selection:bg-[var(--vd-color-secondary)] selection:text-white"
        )

    html_class = (
        f"dark {default_theme.mode}"
        if default_theme.mode == "dark"
        else default_theme.mode
    )

    # --- SEO: Build <head> content ---
    page_lang = seo.lang or seo_config.default_lang or "en"
    page_title = seo.title

    # Meta tags (description, robots, canonical, OG, Twitter, GEO author/dates, hreflang)
    meta_tags = seo.render_meta_tags(
        site_name=seo_config.site_name,
        base_url=seo_config.base_url,
        default_og_image=seo_config.default_og_image,
    )

    # Structured data (JSON-LD)
    structured_data = seo.render_structured_data(
        site_name=seo_config.site_name,
        base_url=seo_config.base_url,
    )

    # Generator meta tag
    generator_tag = (
        '<meta name="generator" content="Voodoo Framework">'
        if seo_config.generator_meta
        else ""
    )

    return f"""
    <!DOCTYPE html>
    <html lang="{page_lang}" class="{html_class}">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{page_title}</title>
        {meta_tags}
        {generator_tag}
        {structured_data}
        {head_scripts}
        <style>
            {css_vars}
            body {{
                background-color: var(--vd-color-background);
                color: var(--vd-color-text);
                font-family: var(--vd-font-sans);
            }}
            ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
            ::-webkit-scrollbar-track {{ background: transparent; }}
            ::-webkit-scrollbar-thumb {{ background: var(--vd-color-surface); border-radius: 4px; border: 1px solid var(--vd-color-border); }}
            ::-webkit-scrollbar-thumb:hover {{ background: var(--vd-color-text-muted); }}

            /* Voodoo component CSS (when using VoodooCSS adapter) */
            {component_css}

            /* Project custom styles (styles.css by convention) */
            {project_styles}
        </style>
    </head>
    <body class="{body_classes}">
        <div id="root">
            {html_content}
        </div>
        <script>
            {client_js}
        </script>
    </body>
    </html>
    """


def _generate_sitemap_xml(app_dir: str, base_url: str = "") -> str:  # noqa: C901
    """Auto-generates deterministic sitemap.xml from file-based routes."""
    from datetime import datetime

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
                    import ast

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
