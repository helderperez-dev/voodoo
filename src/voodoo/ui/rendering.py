"""Server-side rendering: full HTML documents from component trees.

Sitemap/robots generation lives in ``voodoo.core.sitemap`` (SEO concern, not
rendering). This module owns the HTML document shell, the client runtime
(``voodoo/static/client.js``), and the active theme's ``custom.css``.
"""

import os
from typing import Any

_client_js_cache: str | None = None


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
    from voodoo.ui.styles.presets import get_active_custom_css

    return get_active_custom_css()


def render_page(component: Any, seo: Any = None) -> str:
    """Render a complete HTML document for a Voodoo component tree."""
    from voodoo.config import config
    from voodoo.seo import SEO
    from voodoo.ui.component import Component
    from voodoo.ui.styles.theme import default_theme

    if isinstance(component, tuple) and len(component) == 2:
        first, second = component
        if isinstance(first, SEO):
            seo = first
            component = second
        elif isinstance(second, SEO):
            seo = second
            component = first

    if seo is None:
        seo = SEO()

    seo_config = config.seo
    html_content = (
        component.render() if isinstance(component, Component) else str(component)
    )

    client_js = _get_client_js()
    project_styles = _get_project_styles()
    css_vars = default_theme.to_css_variables()

    from voodoo.adapters.voodoo_css import VoodooCSSAdapter, generate_component_css
    from voodoo.ui.styles import current_adapter
    from voodoo.ui.styles.product import generate_product_css
    from voodoo.ui.styles.system import generate_design_system_css
    from voodoo.ui.styles.voodoo_system import generate_voodoo_system_css

    adapter = current_adapter()
    is_voodoo_css = isinstance(adapter, VoodooCSSAdapter)

    if is_voodoo_css:
        component_css = generate_component_css(default_theme)
        design_system_css = generate_design_system_css(default_theme)
        product_css = generate_product_css(default_theme)
        voodoo_system_css = generate_voodoo_system_css(default_theme)
        head_scripts = ""
        body_classes = "min-h-screen antialiased"
    else:
        tailwind_config = default_theme.to_tailwind_config()
        component_css = ""
        design_system_css = ""
        product_css = ""
        voodoo_system_css = ""
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

    page_lang = seo.lang or seo_config.default_lang or "en"
    page_title = seo.title
    meta_tags = seo.render_meta_tags(
        site_name=seo_config.site_name,
        base_url=seo_config.base_url,
        default_og_image=seo_config.default_og_image,
    )
    structured_data = seo.render_structured_data(
        site_name=seo_config.site_name,
        base_url=seo_config.base_url,
    )
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

            /* Stable primitive component layer */
            {component_css}

            /* Voodoo Design System 2 */
            {design_system_css}

            /* Reusable product patterns */
            {product_css}

            /* Canonical Voodoo runtime/system concepts */
            {voodoo_system_css}

            /* Project theme customization */
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
