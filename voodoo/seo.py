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

import json
import html as html_mod
from typing import Optional
from pydantic import BaseModel, Field


class OpenGraph(BaseModel):
    """Open Graph protocol metadata for rich social sharing."""
    title: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None
    type: str = "website"
    url: Optional[str] = None
    site_name: Optional[str] = None
    locale: Optional[str] = None


class TwitterCard(BaseModel):
    """Twitter/X card metadata for social sharing."""
    card: str = "summary_large_image"
    title: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None
    creator: Optional[str] = None
    site: Optional[str] = None


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
    author: Optional[str] = None
    author_credentials: Optional[str] = None
    author_url: Optional[str] = None
    published_date: Optional[str] = None      # ISO 8601 (e.g. "2026-08-15")
    modified_date: Optional[str] = None       # ISO 8601
    sources: Optional[list[str]] = None       # citation URLs
    faq: Optional[list[FAQ]] = None           # auto-generates FAQPage JSON-LD
    tldr: Optional[str] = None                # summary for AI extraction


class SEO(BaseModel):
    """
    Page-level SEO & GEO metadata for Voodoo.
    
    Return alongside a Component from any page() function:
        return SEO(title="My Page"), MyComponent(...)
    """
    title: str = "Voodoo App"
    description: str = ""
    canonical: Optional[str] = None
    robots: str = "index, follow"
    
    # Social
    og: Optional[OpenGraph] = None
    twitter: Optional[TwitterCard] = None
    
    # Structured data (raw JSON-LD dicts)
    structured_data: Optional[list[dict]] = None
    
    # i18n
    lang: str = "en"
    hreflang: Optional[dict[str, str]] = None   # {"en": "/", "pt": "/pt"}
    
    # GEO
    geo: Optional[GEO] = None
    
    # Escape hatch
    extra_head: str = ""

    def render_meta_tags(self, site_name: str = "", base_url: str = "", default_og_image: str = "") -> str:
        """Renders all SEO/GEO metadata as HTML tags for injection into <head>."""
        tags: list[str] = []
        
        # --- Core meta ---
        if self.description:
            tags.append(f'<meta name="description" content="{_esc(self.description)}">')
        if self.robots:
            tags.append(f'<meta name="robots" content="{_esc(self.robots)}">')
        if self.canonical:
            tags.append(f'<link rel="canonical" href="{_esc(self.canonical)}">')
        
        # --- Open Graph ---
        og = self.og
        og_title = (og.title if og and og.title else self.title) if (og or self.title != "Voodoo App") else None
        og_desc = (og.description if og and og.description else self.description) if (og or self.description) else None
        og_image = (og.image if og and og.image else default_og_image) if (og or default_og_image) else None
        og_type = og.type if og else "website"
        og_url = og.url if og and og.url else self.canonical
        og_site = (og.site_name if og and og.site_name else site_name) if (og or site_name) else None
        og_locale = og.locale if og and og.locale else None
        
        if og_title:
            tags.append(f'<meta property="og:title" content="{_esc(og_title)}">')
        if og_desc:
            tags.append(f'<meta property="og:description" content="{_esc(og_desc)}">')
        if og_image:
            tags.append(f'<meta property="og:image" content="{_esc(og_image)}">')
        tags.append(f'<meta property="og:type" content="{_esc(og_type)}">')
        if og_url:
            tags.append(f'<meta property="og:url" content="{_esc(og_url)}">')
        if og_site:
            tags.append(f'<meta property="og:site_name" content="{_esc(og_site)}">')
        if og_locale:
            tags.append(f'<meta property="og:locale" content="{_esc(og_locale)}">')
        
        # --- Twitter Card ---
        tw = self.twitter
        if tw or og_title:
            card_type = tw.card if tw and tw.card else "summary_large_image"
            tw_title = (tw.title if tw and tw.title else og_title)
            tw_desc = (tw.description if tw and tw.description else og_desc)
            tw_image = (tw.image if tw and tw.image else og_image)
            
            tags.append(f'<meta name="twitter:card" content="{_esc(card_type)}">')
            if tw_title:
                tags.append(f'<meta name="twitter:title" content="{_esc(tw_title)}">')
            if tw_desc:
                tags.append(f'<meta name="twitter:description" content="{_esc(tw_desc)}">')
            if tw_image:
                tags.append(f'<meta name="twitter:image" content="{_esc(tw_image)}">')
            if tw and tw.creator:
                tags.append(f'<meta name="twitter:creator" content="{_esc(tw.creator)}">')
            if tw and tw.site:
                tags.append(f'<meta name="twitter:site" content="{_esc(tw.site)}">')
        
        # --- GEO / Article metadata ---
        geo = self.geo
        if geo:
            if geo.author:
                tags.append(f'<meta name="author" content="{_esc(geo.author)}">')
            if geo.published_date:
                tags.append(f'<meta property="article:published_time" content="{_esc(geo.published_date)}">')
            if geo.modified_date:
                tags.append(f'<meta property="article:modified_time" content="{_esc(geo.modified_date)}">')
        
        # --- hreflang ---
        if self.hreflang:
            for lang_code, href in self.hreflang.items():
                full_href = f"{base_url}{href}" if base_url and not href.startswith("http") else href
                tags.append(f'<link rel="alternate" hreflang="{_esc(lang_code)}" href="{_esc(full_href)}">')
        
        # --- Extra head ---
        if self.extra_head:
            tags.append(self.extra_head)
        
        return "\n        ".join(tags)

    def render_structured_data(self, site_name: str = "", base_url: str = "") -> str:
        """Renders JSON-LD structured data blocks."""
        schemas: list[dict] = []
        
        # User-provided structured data
        if self.structured_data:
            schemas.extend(self.structured_data)
        
        # Auto-generate from GEO metadata
        geo = self.geo
        if geo:
            # Article schema (if we have author + dates)
            if geo.author and (geo.published_date or geo.modified_date):
                article_schema: dict = {
                    "@context": "https://schema.org",
                    "@type": "Article",
                    "headline": self.title,
                }
                if self.description:
                    article_schema["description"] = self.description
                    
                author_obj: dict = {"@type": "Person", "name": geo.author}
                if geo.author_url:
                    author_obj["url"] = geo.author_url
                if geo.author_credentials:
                    author_obj["jobTitle"] = geo.author_credentials
                article_schema["author"] = author_obj
                
                if geo.published_date:
                    article_schema["datePublished"] = geo.published_date
                if geo.modified_date:
                    article_schema["dateModified"] = geo.modified_date
                if self.canonical:
                    article_schema["mainEntityOfPage"] = self.canonical
                if site_name:
                    article_schema["publisher"] = {
                        "@type": "Organization",
                        "name": site_name
                    }
                    
                # Check if user already provided an Article schema — don't duplicate
                has_article = any(
                    s.get("@type") in ("Article", "BlogPosting", "NewsArticle")
                    for s in schemas
                )
                if not has_article:
                    schemas.append(article_schema)
            
            # FAQPage schema
            if geo.faq:
                faq_schema = {
                    "@context": "https://schema.org",
                    "@type": "FAQPage",
                    "mainEntity": [
                        {
                            "@type": "Question",
                            "name": faq.question,
                            "acceptedAnswer": {
                                "@type": "Answer",
                                "text": faq.answer
                            }
                        }
                        for faq in geo.faq
                    ]
                }
                # Check if user already provided FAQPage
                has_faq = any(s.get("@type") == "FAQPage" for s in schemas)
                if not has_faq:
                    schemas.append(faq_schema)
        
        if not schemas:
            return ""
        
        blocks = []
        for schema in schemas:
            json_str = json.dumps(schema, ensure_ascii=False, indent=2)
            blocks.append(f'<script type="application/ld+json">\n{json_str}\n</script>')
        
        return "\n        ".join(blocks)


def _esc(value: str) -> str:
    """HTML-escape a string for safe attribute injection."""
    return html_mod.escape(str(value), quote=True)
