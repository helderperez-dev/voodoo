"""Server-side rendering: full HTML documents from component trees.

Sitemap/robots generation lives in ``voodoo.core.sitemap`` (SEO concern, not
rendering). This module owns the HTML document shell, the client runtime
(``voodoo/static/client.js``), and the active theme's ``custom.css``.
"""

import os
from typing import Any

from voodoo.ui.assets import publish_asset

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


_BASE_CSS = """
body {
    background-color: var(--vd-color-background);
    color: var(--vd-color-text);
    font-family: var(--vd-font-sans);
}
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
    background: var(--vd-color-surface);
    border-radius: 4px;
    border: 1px solid var(--vd-color-border);
}
::-webkit-scrollbar-thumb:hover { background: var(--vd-color-text-muted); }
"""


def _semantic_attribute_css() -> str:
    """Rules for semantic attributes (adapter-agnostic, CSP-safe)."""
    from voodoo.ui.component import tone_css
    from voodoo.ui.library import HEADING_SIZES, Box

    sizes = "\n".join(
        f'.vd-heading[data-vd-heading-size="{name}"] {{ font-size: {value}; }}'
        for name, value in HEADING_SIZES.items()
    )
    align = "\n".join(
        f'[data-vd-text-align="{name}"] {{ text-align: {name}; }}'
        for name in ("center", "right")
    )
    from voodoo.ui.foundation import AspectRatio
    from voodoo.ui.workspace import MASTER_WIDTHS

    padding = "\n".join(
        f'[data-vd-padding="{name}"] {{ padding: {value}; }}'
        for name, value in Box._PADDING_MAP.items()
        if name != "none"
    )
    ratios = "\n".join(
        f'[data-vd-ratio="{ratio}"] {{ aspect-ratio: {ratio.replace("/", " / ")}; }}'
        for ratio in AspectRatio.PRESETS
    )
    master = "\n".join(
        f'[data-vd-master-width="{name}"] {{ width: {value}; }}'
        for name, value in MASTER_WIDTHS.items()
    )
    return "\n".join((tone_css(), sizes, align, padding, ratios, master)) + "\n"


def _compose_stylesheet(
    *,
    css_vars: str,
    component_css: str,
    brand_css: str,
    product_css: str,
    extended_css: str,
    voodoo_system_css: str,
    design_system_css: str,
    design_system_theme_css: str,
    project_styles: str,
) -> str:
    """Join the framework CSS layers in cascade order into one stylesheet."""
    sections = (
        css_vars,
        _BASE_CSS,
        "/* Semantic attributes: tone, heading size and alignment */\n"
        + _semantic_attribute_css(),
        "/* Stable primitive component layer */\n" + component_css,
        "/* Brand asset switching */\n" + brand_css,
        "/* Reusable product patterns */\n" + product_css,
        "/* Extended UI components */\n" + extended_css,
        "/* Canonical Voodoo runtime/system concepts */\n" + voodoo_system_css,
        "/* Voodoo Design System 4 — final convergence layer */\n" + design_system_css,
        "/* Theme-authoritative Design System visual tokens */\n"
        + design_system_theme_css,
        "/* Project theme customization — always wins */\n" + project_styles,
    )
    return "\n".join(sections)


def render_page(component: Any, seo: Any = None) -> str:
    """Render a complete HTML document for a Voodoo component tree."""
    from voodoo.config import config
    from voodoo.seo import SEO
    from voodoo.ui.brand import BRAND_CSS
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
    from voodoo.ui.styles.extended import generate_extended_css
    from voodoo.ui.styles.product import generate_product_css
    from voodoo.ui.styles.system import generate_design_system_css
    from voodoo.ui.styles.theme_contract import generate_design_system_theme_css
    from voodoo.ui.styles.voodoo_system import generate_voodoo_system_css

    adapter = current_adapter()
    is_voodoo_css = isinstance(adapter, VoodooCSSAdapter)

    if is_voodoo_css:
        component_css = generate_component_css(default_theme)
        design_system_css = generate_design_system_css(default_theme)
        design_system_theme_css = generate_design_system_theme_css(default_theme)
        extended_css = generate_extended_css(default_theme)
        product_css = generate_product_css(default_theme)
        voodoo_system_css = generate_voodoo_system_css(default_theme)
        head_scripts = ""
        body_classes = "min-h-screen antialiased"
    else:
        tailwind_config = default_theme.to_tailwind_config()
        component_css = ""
        design_system_css = ""
        design_system_theme_css = ""
        extended_css = ""
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

    stylesheet = publish_asset(
        _compose_stylesheet(
            css_vars=css_vars,
            component_css=component_css,
            brand_css=BRAND_CSS,
            product_css=product_css,
            extended_css=extended_css,
            voodoo_system_css=voodoo_system_css,
            design_system_css=design_system_css,
            design_system_theme_css=design_system_theme_css,
            project_styles=project_styles,
        ),
        "css",
    )
    runtime = publish_asset(client_js, "js")

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
        <link rel="stylesheet" href="{stylesheet.url}">
    </head>
    <body class="{body_classes}">
        <div id="root">
            {html_content}
        </div>
        <script src="{runtime.url}" defer></script>
    </body>
    </html>
    """
