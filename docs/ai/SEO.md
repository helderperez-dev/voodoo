# Voodoo SEO & GEO

Voodoo provides a robust, native SEO and Generative Engine Optimization (GEO) system built specifically to help Voodoo apps rank highly on standard search engines and AI engines like ChatGPT, Claude, and Perplexity.

## Architecture

Voodoo pages can optionally return a tuple of `(SEO, Component)` or `(Component, SEO)` instead of just a Component. If returned, the framework injects the metadata into the `<head>` of the server-side rendered HTML response before the app hydrates on the client.

## SEO Configuration

Global SEO configuration is defined in `voodoo.yaml` and loaded via `voodoo.config`. This manages dynamic sitemap generation, robots.txt, and default site names.

## Usage

```python
from voodoo.components import Div, Heading, Text
from voodoo.seo import SEO, OpenGraph, TwitterCard, GEO

def page():
    ui = Div(
        Heading("Voodoo Analytics", level=1),
        Text("Real-time telemetry for your framework.")
    )
    
    seo = SEO(
        title="Voodoo Analytics Dashboard",
        description="Monitor real-time metrics and telemetry.",
        canonical="https://voodoo.example.com/analytics",
        og=OpenGraph(
            image="https://voodoo.example.com/og.png",
            type="website"
        ),
        twitter=TwitterCard(
            card="summary_large_image",
            site="@voodoo_app"
        ),
        geo=GEO(
            author="Voodoo Team",
            tags=["analytics", "telemetry", "python"],
            is_article=True,
            publish_date="2026-08-15"
        )
    )
    
    return seo, ui
```

## Features

- **Dynamic Sitemaps**: `sitemap.xml` is generated automatically based on `app/` folder routing. Add `SITEMAP_EXCLUDE = True` to a `page.py` to hide it.
- **Dynamic Robots**: `robots.txt` automatically reflects `sitemap.xml` and blocks/allows configurable paths.
- **Structured Data (JSON-LD)**: When using `GEO(is_article=True)` or `FAQ` models, Voodoo automatically compiles and injects valid JSON-LD tags into the head of the page for rich results.
- **Hreflang Support**: Add `seo.alternate_urls = {"fr": "https://..."}` to auto-inject hreflang links.
- **Graceful Fallbacks**: OpenGraph and TwitterCard automatically fall back to base `SEO` values (like title and description) if omitted.
