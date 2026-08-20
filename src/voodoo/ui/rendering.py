"""Server-side rendering: full HTML documents from component trees.

Sitemap/robots generation lives in ``voodoo.core.sitemap`` (SEO concern, not
rendering). This module owns the HTML document shell, the client runtime
(``voodoo/static/client.js``), and the project ``styles.css`` convention.
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
            os.path.dirname(os.path.dirname(__file__)), "static", "client.js"
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
    from voodoo.ui.component import Component
    from voodoo.ui.styles.theme import default_theme

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
        </script>
        """
        body_classes = (
            "bg-[var(--vd-color-background)] text-[var(--vd-color-text)] "
            "min-h-screen antialiased "
            "selection:bg-[var(--vd-color-secondary)] selection:text-white"
        )

    # Resolve light/dark/system once. The persisted cookie override and the
    # prefers-color-scheme fallback are applied by an inline script that runs
    # before the stylesheet, avoiding a flash of the wrong theme.
    mode = default_theme.mode or "dark"
    if mode not in ("dark", "light", "system"):
        mode = "dark"
    html_class = mode
    theme_init_script = f"""<script>
(function () {{
    var mode = "{mode}";
    var m = document.cookie.match(/(?:^|;\\s*)voodoo_theme=([^;]+)/);
    var resolved = m ? m[1] : mode;
    if (resolved === "system") {{
        resolved = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
            ? "dark" : "light";
    }}
    document.documentElement.classList.toggle("dark", resolved === "dark");
}})();
</script>"""

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
        {theme_init_script}
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
