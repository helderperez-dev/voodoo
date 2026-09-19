"""
voodoo.seo — First-class SEO & GEO (Generative Engine Optimization) support.

Provides Pydantic models for page-level metadata that the framework
automatically injects into the rendered HTML <head>.

Usage in page.py:
    from voodoo.seo import SEO, OpenGraph, GEO, FAQ

    def page():
        seo = SEO(
            title="My Page",
            description="A description.",
            geo=GEO(author="Author Name", tldr="Quick summary."),
        )
        component = Div(Heading("Hello"))
        return seo, component
"""

import html as html_mod
import json

from pydantic import BaseModel


class OpenGraph(BaseModel):
    """Open Graph protocol metadata for rich social sharing."""

    title: str | None = None
    description: str | None = None
    image: str | None = None
    type: str = "website"
    url: str | None = None
    site_name: str | None = None
    locale: str | None = None


class TwitterCard(BaseModel):
    """Twitter/X card metadata for social sharing."""

    card: str = "summary_large_image"
    title: str | None = None
    description: str | None = None
    image: str | None = None
    creator: str | None = None
    site: str | None = None


class FAQ(BaseModel):
    """A single FAQ entry — used for GEO and auto-generates FAQPage schema."""

    question: str
    answer: str


class GEO(BaseModel):
    """
    Generative Engine Optimization metadata.
    Helps AI search engines (ChatGPT, Perplexity, Claude, Gemini)
    understand, cite, and surface your content.
    """

    author: str | None = None
    author_credentials: str | None = None
    author_url: str | None = None
    published_date: str | None = None  # ISO 8601 (e.g. "2026-08-15")
    modified_date: str | None = None  # ISO 8601
    sources: list[str] | None = None  # citation URLs
    faq: list[FAQ] | None = None  # auto-generates FAQPage JSON-LD
    tldr: str | None = None  # summary for AI extraction


class SEO(BaseModel):
    """
    Page-level SEO & GEO metadata for Voodoo.
    Return alongside a Component from any page() function:
        return SEO(title="My Page"), MyComponent(...)
    """

    title: str = "Voodoo App"
    description: str = ""
    canonical: str | None = None
    robots: str = "index, follow"

    # Social
    og: OpenGraph | None = None
    twitter: TwitterCard | None = None

    # Structured data (raw JSON-LD dicts)
    structured_data: list[dict] | None = None

    # i18n
    lang: str = "en"
    hreflang: dict[str, str] | None = None  # {"en": "/", "pt": "/pt"}

    # GEO
    geo: GEO | None = None

    # Escape hatch
    extra_head: str = ""

    def render_meta_tags(
        self, site_name: str = "", base_url: str = "", default_og_image: str = ""
    ) -> str:
        """Renders all SEO/GEO metadata as HTML tags for injection into <head>."""
        tags = self._core_meta_tags()
        og_title, og_desc, og_image = self._append_open_graph(
            tags, site_name, default_og_image
        )
        self._append_twitter(tags, og_title, og_desc, og_image)
        self._append_geo(tags)
        self._append_hreflang(tags, base_url)
        if self.extra_head:
            tags.append(self.extra_head)
        return "\n        ".join(tags)

    def _core_meta_tags(self) -> list[str]:
        tags: list[str] = []
        if self.description:
            tags.append(f'<meta name="description" content="{_esc(self.description)}">')
        if self.robots:
            tags.append(f'<meta name="robots" content="{_esc(self.robots)}">')
        if self.canonical:
            tags.append(f'<link rel="canonical" href="{_esc(self.canonical)}">')
        return tags

    def _append_open_graph(
        self, tags: list[str], site_name: str, default_og_image: str
    ) -> tuple[str | None, str | None, str | None]:
        og = self.og
        title = (
            (og.title if og and og.title else self.title)
            if (og or self.title != "Voodoo App")
            else None
        )
        desc = (
            (og.description if og and og.description else self.description)
            if (og or self.description)
            else None
        )
        image = (
            (og.image if og and og.image else default_og_image)
            if (og or default_og_image)
            else None
        )
        values = (
            ("og:title", title),
            ("og:description", desc),
            ("og:image", image),
            ("og:type", og.type if og else "website"),
            ("og:url", og.url if og and og.url else self.canonical),
            (
                "og:site_name",
                (og.site_name if og and og.site_name else site_name)
                if (og or site_name)
                else None,
            ),
            ("og:locale", og.locale if og and og.locale else None),
        )
        for name, value in values:
            if value:
                tags.append(f'<meta property="{name}" content="{_esc(value)}">')
        return title, desc, image

    def _append_twitter(
        self,
        tags: list[str],
        og_title: str | None,
        og_desc: str | None,
        og_image: str | None,
    ) -> None:
        tw = self.twitter
        if not (tw or og_title):
            return
        values = (
            ("twitter:card", tw.card if tw and tw.card else "summary_large_image"),
            ("twitter:title", tw.title if tw and tw.title else og_title),
            ("twitter:description", tw.description if tw and tw.description else og_desc),
            ("twitter:image", tw.image if tw and tw.image else og_image),
            ("twitter:creator", tw.creator if tw else None),
            ("twitter:site", tw.site if tw else None),
        )
        for name, value in values:
            if value:
                tags.append(f'<meta name="{name}" content="{_esc(value)}">')

    def _append_geo(self, tags: list[str]) -> None:
        geo = self.geo
        if not geo:
            return
        values = (
            ("author", geo.author, "name"),
            ("article:published_time", geo.published_date, "property"),
            ("article:modified_time", geo.modified_date, "property"),
        )
        for name, value, attribute in values:
            if value:
                tags.append(f'<meta {attribute}="{name}" content="{_esc(value)}">')

    def _append_hreflang(self, tags: list[str], base_url: str) -> None:
        if not self.hreflang:
            return
        for lang_code, href in self.hreflang.items():
            full_href = (
                f"{base_url}{href}"
                if base_url and not href.startswith("http")
                else href
            )
            tags.append(
                f'<link rel="alternate" hreflang="{_esc(lang_code)}" href="{_esc(full_href)}">'
            )

    def render_structured_data(self, site_name: str = "", base_url: str = "") -> str:
        """Renders JSON-LD structured data blocks."""
        schemas = list(self.structured_data or [])
        geo = self.geo
        if geo:
            article = self._article_schema(site_name)
            if article and not self._has_schema_type(
                schemas, "Article", "BlogPosting", "NewsArticle"
            ):
                schemas.append(article)
            faq = self._faq_schema()
            if faq and not self._has_schema_type(schemas, "FAQPage"):
                schemas.append(faq)
        return self._render_schema_blocks(schemas)

    @staticmethod
    def _has_schema_type(schemas: list[dict], *types: str) -> bool:
        return any(schema.get("@type") in types for schema in schemas)

    def _article_schema(self, site_name: str) -> dict | None:
        geo = self.geo
        if not geo or not geo.author or not (geo.published_date or geo.modified_date):
            return None
        schema: dict = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": self.title,
        }
        if self.description:
            schema["description"] = self.description
        author: dict = {"@type": "Person", "name": geo.author}
        if geo.author_url:
            author["url"] = geo.author_url
        if geo.author_credentials:
            author["jobTitle"] = geo.author_credentials
        schema["author"] = author
        optional = (
            ("datePublished", geo.published_date),
            ("dateModified", geo.modified_date),
            ("mainEntityOfPage", self.canonical),
        )
        for key, value in optional:
            if value:
                schema[key] = value
        if site_name:
            schema["publisher"] = {"@type": "Organization", "name": site_name}
        return schema

    def _faq_schema(self) -> dict | None:
        geo = self.geo
        if not geo or not geo.faq:
            return None
        return {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": faq.question,
                    "acceptedAnswer": {"@type": "Answer", "text": faq.answer},
                }
                for faq in geo.faq
            ],
        }

    @staticmethod
    def _render_schema_blocks(schemas: list[dict]) -> str:
        blocks = [
            f'<script type="application/ld+json">\\n{json.dumps(schema, ensure_ascii=False, indent=2)}\\n</script>'
            for schema in schemas
        ]
        return "\n        ".join(blocks)


def _esc(value: str) -> str:
    """HTML-escape a string for safe attribute injection."""
    return html_mod.escape(str(value), quote=True)
