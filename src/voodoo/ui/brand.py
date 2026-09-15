"""Branding primitives for logos and wordmarks.

``Brand`` preserves the existing child-based API while adding a first-class
image mode that can switch logo assets with the active light/dark theme.
"""

from __future__ import annotations

from typing import Any

from voodoo.ui.component import Component


BRAND_CSS = """
/* Brand image contract */
.vd-brand-logo {
    display: block;
    max-width: 100%;
    height: auto;
    border-radius: 0 !important;
}
.vd-brand-logo--light { display: block; }
.vd-brand-logo--dark { display: none; }
.dark .vd-brand-logo--light { display: none; }
.dark .vd-brand-logo--dark { display: block; }
"""


class _BrandLogo(Component):
    """Internal logo image with no generic ``Img`` presentation styles."""

    tag = "img"
    auto_id = False

    def __init__(
        self,
        *,
        src: str,
        alt: str,
        variant: str | None = None,
        width: str | int | None = None,
        height: str | int | None = None,
    ) -> None:
        classes = "vd-brand-logo"
        if variant:
            classes += f" vd-brand-logo--{variant}"
        super().__init__(class_=classes)
        self.attrs["src"] = src
        self.attrs["alt"] = alt
        if width is not None:
            self.attrs["width"] = width
        if height is not None:
            self.attrs["height"] = height


class Brand(Component):
    """Brand link supporting either child content or theme-aware logo assets.

    Existing usage remains valid::

        Brand("Acme", href="/")
        Brand(Img(src="/logo.png", alt="Acme"), href="/")

    Image mode keeps branding free of generic image presentation styles and
    automatically selects the correct asset for the active theme::

        Brand(
            light="/logo-black.png",
            dark="/logo-white.png",
            alt="Acme",
            width=160,
            href="/",
        )

    When only ``light`` or ``dark`` is supplied, that asset is used for both
    themes. Image mode and explicit children are intentionally mutually
    exclusive so the rendered brand stays unambiguous.
    """

    tag = "a"
    style = "brand"

    def __init__(
        self,
        *children: Any,
        href: str = "/",
        light: str | None = None,
        dark: str | None = None,
        alt: str = "",
        width: str | int | None = None,
        height: str | int | None = None,
        **kwargs: Any,
    ) -> None:
        image_mode = light is not None or dark is not None
        if image_mode and children:
            raise ValueError(
                "Brand image mode cannot be combined with child content. "
                "Use either Brand(...children) or Brand(light=..., dark=...)."
            )

        super().__init__(*children, **kwargs)
        self.attrs["href"] = href

        if not image_mode:
            return

        light_src = light or dark
        dark_src = dark or light
        assert light_src is not None
        assert dark_src is not None

        if light_src == dark_src:
            self.children = (
                _BrandLogo(
                    src=light_src,
                    alt=alt,
                    width=width,
                    height=height,
                ),
            )
            return

        self.children = (
            _BrandLogo(
                src=light_src,
                alt=alt,
                variant="light",
                width=width,
                height=height,
            ),
            _BrandLogo(
                src=dark_src,
                alt=alt,
                variant="dark",
                width=width,
                height=height,
            ),
        )
