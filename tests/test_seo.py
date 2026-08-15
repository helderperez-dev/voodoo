"""Tests for voodoo.seo — SEO & GEO metadata system."""

import json

from voodoo.components import (
    Address,
    Article,
    Aside,
    Div,
    FigCaption,
    Figure,
    Footer,
    Header,
    Img,
    Main,
    Nav,
    Paragraph,
    Section,
    Time,
)
from voodoo.core import render_page
from voodoo.seo import FAQ, GEO, SEO, OpenGraph, TwitterCard, _esc

# ==============================================================================
# SEO Model Basics
# ==============================================================================


class TestSEOModel:
    def test_defaults(self):
        seo = SEO()
        assert seo.title == "Voodoo App"
        assert seo.description == ""
        assert seo.robots == "index, follow"
        assert seo.lang == "en"
        assert seo.og is None
        assert seo.twitter is None
        assert seo.geo is None

    def test_custom_values(self):
        seo = SEO(
            title="My Page",
            description="A great page.",
            canonical="https://example.com/page",
            robots="noindex, nofollow",
            lang="pt",
        )
        assert seo.title == "My Page"
        assert seo.description == "A great page."
        assert seo.canonical == "https://example.com/page"
        assert seo.robots == "noindex, nofollow"
        assert seo.lang == "pt"


# ==============================================================================
# Meta Tag Rendering
# ==============================================================================


class TestMetaTags:
    def test_description_meta(self):
        seo = SEO(description="Hello world")
        tags = seo.render_meta_tags()
        assert '<meta name="description" content="Hello world">' in tags

    def test_robots_meta(self):
        seo = SEO(robots="noindex, nofollow")
        tags = seo.render_meta_tags()
        assert '<meta name="robots" content="noindex, nofollow">' in tags

    def test_canonical_link(self):
        seo = SEO(canonical="https://example.com/page")
        tags = seo.render_meta_tags()
        assert '<link rel="canonical" href="https://example.com/page">' in tags

    def test_no_description_no_tag(self):
        seo = SEO(description="")
        tags = seo.render_meta_tags()
        assert 'name="description"' not in tags

    def test_html_escaping(self):
        seo = SEO(description='He said "hello" & <goodbye>')
        tags = seo.render_meta_tags()
        assert "&quot;hello&quot;" in tags
        assert "&amp;" in tags
        assert "&lt;goodbye&gt;" in tags


# ==============================================================================
# OpenGraph Tags
# ==============================================================================


class TestOpenGraph:
    def test_og_from_explicit(self):
        seo = SEO(
            title="Page Title",
            og=OpenGraph(title="OG Title", description="OG Desc", image="/img.jpg"),
        )
        tags = seo.render_meta_tags()
        assert '<meta property="og:title" content="OG Title">' in tags
        assert '<meta property="og:description" content="OG Desc">' in tags
        assert '<meta property="og:image" content="/img.jpg">' in tags

    def test_og_falls_back_to_seo_values(self):
        seo = SEO(
            title="Page Title",
            description="Page Desc",
            og=OpenGraph(),  # empty OG — should fallback
        )
        tags = seo.render_meta_tags()
        assert '<meta property="og:title" content="Page Title">' in tags
        assert '<meta property="og:description" content="Page Desc">' in tags

    def test_og_type_default(self):
        seo = SEO(title="Test", og=OpenGraph())
        tags = seo.render_meta_tags()
        assert '<meta property="og:type" content="website">' in tags

    def test_og_site_name_from_config(self):
        seo = SEO(title="Test", og=OpenGraph())
        tags = seo.render_meta_tags(site_name="My Site")
        assert '<meta property="og:site_name" content="My Site">' in tags

    def test_default_og_image_fallback(self):
        seo = SEO(title="Test", og=OpenGraph())
        tags = seo.render_meta_tags(default_og_image="/default.jpg")
        assert '<meta property="og:image" content="/default.jpg">' in tags


# ==============================================================================
# Twitter Card Tags
# ==============================================================================


class TestTwitterCard:
    def test_twitter_explicit(self):
        seo = SEO(
            twitter=TwitterCard(
                title="TW Title", description="TW Desc", creator="@user"
            )
        )
        tags = seo.render_meta_tags()
        assert '<meta name="twitter:card" content="summary_large_image">' in tags
        assert '<meta name="twitter:title" content="TW Title">' in tags
        assert '<meta name="twitter:description" content="TW Desc">' in tags
        assert '<meta name="twitter:creator" content="@user">' in tags

    def test_twitter_falls_back_to_og(self):
        seo = SEO(
            title="Page",
            description="Desc",
            og=OpenGraph(title="OG Title", image="/og.jpg"),
        )
        tags = seo.render_meta_tags()
        # Twitter should use OG values as fallback
        assert '<meta name="twitter:title" content="OG Title">' in tags
        assert '<meta name="twitter:image" content="/og.jpg">' in tags


# ==============================================================================
# GEO Metadata
# ==============================================================================


class TestGEO:
    def test_author_meta(self):
        seo = SEO(geo=GEO(author="Merlin"))
        tags = seo.render_meta_tags()
        assert '<meta name="author" content="Merlin">' in tags

    def test_article_dates(self):
        seo = SEO(
            geo=GEO(
                author="Author", published_date="2026-08-15", modified_date="2026-08-16"
            )
        )
        tags = seo.render_meta_tags()
        assert '<meta property="article:published_time" content="2026-08-15">' in tags
        assert '<meta property="article:modified_time" content="2026-08-16">' in tags


# ==============================================================================
# Structured Data (JSON-LD)
# ==============================================================================


class TestStructuredData:
    def test_custom_structured_data(self):
        schema = {"@context": "https://schema.org", "@type": "Product", "name": "Wand"}
        seo = SEO(structured_data=[schema])
        ld = seo.render_structured_data()
        assert '<script type="application/ld+json">' in ld
        assert '"@type": "Product"' in ld
        assert '"name": "Wand"' in ld

    def test_auto_article_schema_from_geo(self):
        seo = SEO(
            title="My Article",
            description="An article.",
            geo=GEO(
                author="Merlin",
                author_credentials="Chief Wizard",
                published_date="2026-08-15",
            ),
        )
        ld = seo.render_structured_data(site_name="Voodoo Site")
        parsed = json.loads(
            ld.split('<script type="application/ld+json">')[1].split("</script>")[0]
        )
        assert parsed["@type"] == "Article"
        assert parsed["headline"] == "My Article"
        assert parsed["author"]["name"] == "Merlin"
        assert parsed["author"]["jobTitle"] == "Chief Wizard"
        assert parsed["datePublished"] == "2026-08-15"
        assert parsed["publisher"]["name"] == "Voodoo Site"

    def test_auto_faq_schema_from_geo(self):
        seo = SEO(
            geo=GEO(
                faq=[
                    FAQ(question="What is Voodoo?", answer="A Python framework."),
                    FAQ(question="Is it fast?", answer="Yes."),
                ]
            )
        )
        ld = seo.render_structured_data()
        parsed = json.loads(
            ld.split('<script type="application/ld+json">')[1].split("</script>")[0]
        )
        assert parsed["@type"] == "FAQPage"
        assert len(parsed["mainEntity"]) == 2
        assert parsed["mainEntity"][0]["name"] == "What is Voodoo?"
        assert (
            parsed["mainEntity"][0]["acceptedAnswer"]["text"] == "A Python framework."
        )

    def test_no_duplicate_article_schema(self):
        """If user provides Article schema, GEO should not auto-generate another."""
        custom_article = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": "Custom",
        }
        seo = SEO(
            structured_data=[custom_article],
            geo=GEO(author="Author", published_date="2026-01-01"),
        )
        ld = seo.render_structured_data()
        # Should only have ONE Article block
        assert ld.count('"@type": "Article"') == 1
        assert '"headline": "Custom"' in ld

    def test_no_duplicate_faq_schema(self):
        """If user provides FAQPage schema, GEO should not auto-generate another."""
        custom_faq = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [],
        }
        seo = SEO(
            structured_data=[custom_faq], geo=GEO(faq=[FAQ(question="Q?", answer="A.")])
        )
        ld = seo.render_structured_data()
        assert ld.count('"@type": "FAQPage"') == 1

    def test_empty_structured_data(self):
        seo = SEO()
        ld = seo.render_structured_data()
        assert ld == ""


# ==============================================================================
# hreflang
# ==============================================================================


class TestHreflang:
    def test_hreflang_tags(self):
        seo = SEO(hreflang={"en": "/", "pt": "/pt", "es": "/es"})
        tags = seo.render_meta_tags()
        assert '<link rel="alternate" hreflang="en" href="/">' in tags
        assert '<link rel="alternate" hreflang="pt" href="/pt">' in tags
        assert '<link rel="alternate" hreflang="es" href="/es">' in tags

    def test_hreflang_with_base_url(self):
        seo = SEO(hreflang={"en": "/", "pt": "/pt"})
        tags = seo.render_meta_tags(base_url="https://example.com")
        assert 'href="https://example.com/"' in tags
        assert 'href="https://example.com/pt"' in tags

    def test_hreflang_absolute_url_not_prefixed(self):
        seo = SEO(hreflang={"en": "https://en.example.com/"})
        tags = seo.render_meta_tags(base_url="https://example.com")
        assert 'href="https://en.example.com/"' in tags


# ==============================================================================
# render_page() Integration
# ==============================================================================


class TestRenderPage:
    def test_backwards_compatible_no_seo(self):
        """render_page(component) without SEO still works with defaults."""
        comp = Div("Hello", id="test")
        html = render_page(comp)
        assert "<title>Voodoo App</title>" in html
        assert '<div id="test">Hello</div>' in html
        assert "<!DOCTYPE html>" in html

    def test_with_seo_title(self):
        seo = SEO(title="Custom Title")
        comp = Div("Content", id="main")
        html = render_page(comp, seo=seo)
        assert "<title>Custom Title</title>" in html

    def test_with_seo_description(self):
        seo = SEO(title="Test", description="My description")
        html = render_page(Div("x", id="t"), seo=seo)
        assert '<meta name="description" content="My description">' in html

    def test_with_seo_lang(self):
        seo = SEO(lang="pt")
        html = render_page(Div("x", id="t"), seo=seo)
        assert 'lang="pt"' in html

    def test_generator_meta_tag(self):
        html = render_page(Div("x", id="t"))
        assert '<meta name="generator" content="Voodoo Framework">' in html

    def test_structured_data_in_page(self):
        seo = SEO(
            structured_data=[
                {"@context": "https://schema.org", "@type": "WebSite", "name": "Test"}
            ]
        )
        html = render_page(Div("x", id="t"), seo=seo)
        assert '<script type="application/ld+json">' in html
        assert '"@type": "WebSite"' in html


# ==============================================================================
# Semantic HTML Components
# ==============================================================================


class TestSemanticComponents:
    def test_nav(self):
        nav = Nav("Links", id="nav-1")
        assert nav.render() == '<nav id="nav-1">Links</nav>'

    def test_header(self):
        hdr = Header("Title", id="hdr-1")
        assert hdr.render() == '<header id="hdr-1">Title</header>'

    def test_footer(self):
        ftr = Footer("Copyright", id="ftr-1")
        assert ftr.render() == '<footer id="ftr-1">Copyright</footer>'

    def test_main(self):
        m = Main("Content", id="main-1")
        assert m.render() == '<main id="main-1">Content</main>'

    def test_section(self):
        s = Section("Block", id="sec-1")
        assert s.render() == '<section id="sec-1">Block</section>'

    def test_article(self):
        a = Article("Post", id="art-1")
        assert a.render() == '<article id="art-1">Post</article>'

    def test_aside(self):
        a = Aside("Sidebar", id="side-1")
        assert a.render() == '<aside id="side-1">Sidebar</aside>'

    def test_figure_and_figcaption(self):
        fig = Figure(
            Img(src="/photo.jpg", alt="A photo", id="img-1"),
            FigCaption("A beautiful photo", id="cap-1"),
            id="fig-1",
        )
        html = fig.render()
        assert html.startswith('<figure id="fig-1">')
        assert "<img" in html
        assert '<figcaption id="cap-1">A beautiful photo</figcaption>' in html

    def test_time_with_datetime(self):
        t = Time("August 15", datetime="2026-08-15", id="time-1")
        html = t.render()
        assert '<time id="time-1" datetime="2026-08-15">August 15</time>' == html

    def test_time_without_datetime(self):
        t = Time("Today", id="time-2")
        assert t.render() == '<time id="time-2">Today</time>'

    def test_address(self):
        a = Address("123 Main St", id="addr-1")
        assert a.render() == '<address id="addr-1">123 Main St</address>'

    def test_img_with_alt(self):
        img = Img(src="/photo.jpg", alt="A photo", id="img-1")
        html = img.render()
        assert 'alt="A photo"' in html
        assert 'src="/photo.jpg"' in html

    def test_img_self_closing(self):
        img = Img(src="/photo.jpg", alt="Photo", id="img-2")
        html = img.render()
        assert html.endswith("/>")

    def test_img_missing_alt_warning(self, capsys):
        """Img without alt should print a warning and set alt=""."""
        img = Img(src="/photo.jpg", id="img-3")
        html = img.render()
        assert 'alt=""' in html
        captured = capsys.readouterr()
        assert "[Voodoo SEO Warning]" in captured.err

    def test_paragraph(self):
        p = Paragraph("Some text", id="p-1")
        assert p.render() == '<p id="p-1">Some text</p>'


# ==============================================================================
# Helper: _esc
# ==============================================================================


class TestEsc:
    def test_escapes_quotes(self):
        assert _esc('"hello"') == "&quot;hello&quot;"

    def test_escapes_ampersand(self):
        assert _esc("a & b") == "a &amp; b"

    def test_escapes_angle_brackets(self):
        assert _esc("<script>") == "&lt;script&gt;"

    def test_passes_plain_text(self):
        assert _esc("hello world") == "hello world"


# ==============================================================================
# Route Endpoints & Tuple Page Integration
# ==============================================================================


class TestAppSEOEndpoints:
    def test_sitemap_and_robots_routes(self, tmp_path, monkeypatch):
        from starlette.testclient import TestClient

        import voodoo.data
        from voodoo.core import create_app

        # Create temporary app directory structure
        app_dir = tmp_path / "app"
        app_dir.mkdir()
        (app_dir / "page.py").write_text(
            'from voodoo import Div, Heading\nfrom voodoo.seo import SEO\ndef page():\n    return SEO(title="Home Page"), Div(Heading("Home"))'
        )
        about_dir = app_dir / "about"
        about_dir.mkdir()
        (about_dir / "page.py").write_text(
            'from voodoo import Div\ndef page():\n    return Div("About Us")'
        )

        async def mock_init_db(db_path=":memory:"):
            pass

        monkeypatch.setattr(voodoo.data, "init_db", mock_init_db)

        app = create_app(app_dir=str(app_dir))
        with TestClient(app) as client:
            # Test sitemap.xml
            res = client.get("/sitemap.xml")
            assert res.status_code == 200
            assert res.headers["content-type"].startswith("application/xml")
            assert "<loc>http://testserver/</loc>" in res.text
            assert "<loc>http://testserver/about</loc>" in res.text

            # Test robots.txt
            res_robots = client.get("/robots.txt")
            assert res_robots.status_code == 200
            assert "User-agent: *" in res_robots.text
            assert "Disallow: /_voodoo_ws" in res_robots.text
            assert "Sitemap: http://testserver/sitemap.xml" in res_robots.text

            # Test page with (SEO, Component) tuple
            res_home = client.get("/")
            assert res_home.status_code == 200
            assert "<title>Home Page</title>" in res_home.text
            assert "Home</h1>" in res_home.text

            # Test page with plain Component (backwards compatible)
            res_about = client.get("/about")
            assert res_about.status_code == 200
            assert "<title>Voodoo App</title>" in res_about.text
            assert "About Us</div>" in res_about.text
