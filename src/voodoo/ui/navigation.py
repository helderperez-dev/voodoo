"""Adaptive application navigation primitives."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from voodoo.ui.component import Component
from voodoo.ui.events import bind_event
from voodoo.ui.library import Sidebar

EventHandler = Callable[..., Any] | str


class AppShell(Component):
    """Full-height application frame for sidebars, content, and mobile nav.

    Collapsible sidebars receive an integrated control row and a launcher that
    is only exposed while the sidebar is fully hidden.
    """

    style = "app-shell"

    def __init__(
        self,
        *children: Any,
        sidebar: Sidebar | None = None,
        bottom_nav: BottomNav | None = None,
        sidebar_toggle: bool = True,
        content_padding: str = "lg",
        **kwargs: Any,
    ) -> None:
        if content_padding not in {"none", "sm", "md", "lg", "xl"}:
            raise ValueError(
                "AppShell content_padding must be none, sm, md, lg, or xl"
            )
        shell_children = list(children)
        content: list[Any] = []
        if sidebar is not None:
            collapsible = bool(sidebar.props.get("collapsible", True))
            supplied_toggle = next(
                (
                    child
                    for child in shell_children
                    if isinstance(child, SidebarToggle)
                    and child.attrs.get("data_vd_sidebar_toggle") == sidebar.id
                ),
                None,
            )
            if supplied_toggle is not None and sidebar_toggle and collapsible:
                shell_children.remove(supplied_toggle)
            header_children: list[Component] = []
            brand = _SidebarBrand(
                logo=sidebar.props.get("logo"),
                brand=sidebar.props.get("brand"),
                href=sidebar.props.get("brand_href"),
                label=sidebar.props.get("brand_label"),
            )
            if not brand.attrs.get("hidden"):
                header_children.append(brand)
            if sidebar_toggle and collapsible:
                sidebar_modes = tuple(
                    sidebar.props.get("modes", ("expanded", "rail"))
                )
                integrated = supplied_toggle or SidebarToggle(
                    sidebar,
                    modes=sidebar_modes,
                )
                integrated.attrs["data_vd_sidebar_modes"] = ",".join(sidebar_modes)
                _configure_sidebar_toggle(integrated, sidebar, "inside")
                header_children.append(_SidebarControls(integrated))
                open_mode = next(
                    (mode for mode in sidebar_modes if mode != "hidden"),
                    "expanded",
                )
                launcher = SidebarToggle(
                    sidebar,
                    modes=(open_mode,),
                    label="Open navigation",
                    placement="launcher",
                )
                binding = integrated.attrs.get("data_vd_event_change")
                if binding:
                    launcher.attrs["data_vd_event_change"] = binding
            if header_children:
                sidebar.children = (
                    _SidebarHeader(*header_children),
                    *sidebar.children,
                )
            content.append(sidebar)
            if sidebar_toggle and collapsible:
                content.append(launcher)
        content.append(
            _AppShellContent(
                *shell_children,
                padding=content_padding,
            )
        )
        if bottom_nav is not None:
            content.append(bottom_nav)
        super().__init__(*content, **kwargs)


class _AppShellContent(Component):
    style = "app-shell.content"
    auto_id = False

    def __init__(
        self,
        *children: Any,
        padding: str,
    ) -> None:
        super().__init__(*children, data_vd_app_shell_content=True)
        self.props = {"padding": padding}


class SidebarItem(Component):
    """A destination that remains understandable in expanded and rail modes."""

    style = "sidebar-item"

    def __init__(
        self,
        label: str,
        *,
        href: str | None = None,
        icon: Component | None = None,
        badge: str | int | None = None,
        active: bool = False,
        disabled: bool = False,
        on_click: EventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        self.tag = "a" if href and not disabled else "button"
        attrs: dict[str, Any] = {"aria_label": label}
        if href and not disabled:
            attrs["href"] = href
        else:
            attrs["type"] = "button"
        if disabled:
            attrs["disabled"] = True
            attrs["aria_disabled"] = "true"
        if on_click is not None and not disabled:
            attrs["data_vd_event_click"] = bind_event(on_click)
        if active:
            attrs["aria_current"] = "page"
        super().__init__(data_vd_sidebar_item=True, **attrs, **kwargs)
        self.props = {"active": active}
        children: list[Component] = []
        if icon is not None:
            children.append(_SidebarIcon(icon))
        children.append(_SidebarLabel(label))
        if badge is not None:
            children.append(_SidebarBadge(str(badge)))
        self.children = tuple(children)


class _SidebarIcon(Component):
    tag = "span"
    style = "sidebar-item.icon"
    auto_id = False


class _SidebarLabel(Component):
    tag = "span"
    style = "sidebar-item.label"
    auto_id = False

    def __init__(self, *children: Any, **kwargs: Any) -> None:
        super().__init__(*children, data_vd_sidebar_label=True, **kwargs)


class _SidebarBadge(Component):
    tag = "span"
    style = "sidebar-item.badge"
    auto_id = False

    def __init__(self, *children: Any, **kwargs: Any) -> None:
        super().__init__(*children, data_vd_sidebar_label=True, **kwargs)


class SidebarToggle(Component):
    """Cycles an adaptive sidebar through configured display modes."""

    tag = "button"
    style = "sidebar-toggle"

    def __init__(
        self,
        target: Sidebar | str,
        *,
        modes: tuple[str, ...] = ("expanded", "rail", "hidden"),
        label: str = "Toggle navigation",
        on_change: EventHandler | None = None,
        placement: str = "standalone",
        **kwargs: Any,
    ) -> None:
        if not modes or any(mode not in {"expanded", "rail", "hidden"} for mode in modes):
            raise ValueError("SidebarToggle modes must use expanded, rail, or hidden")
        if placement not in {"standalone", "inside", "launcher"}:
            raise ValueError(
                "SidebarToggle placement must be standalone, inside, or launcher"
            )
        target_id = target.id if isinstance(target, Sidebar) else target
        if not target_id:
            raise ValueError("SidebarToggle target must have an id")
        current_mode = (
            target.attrs.get("data_vd_sidebar_mode", "expanded")
            if isinstance(target, Sidebar)
            else "expanded"
        )
        attrs: dict[str, Any] = {
            "data_vd_sidebar_toggle": target_id,
            "data_vd_sidebar_modes": ",".join(modes),
            "data_vd_sidebar_placement": placement,
            "data_vd_sidebar_current_mode": current_mode,
            "data_vd_sidebar_expand_label": (
                "Expand navigation" if label == "Toggle navigation" else label
            ),
            "data_vd_sidebar_collapse_label": (
                "Collapse navigation" if label == "Toggle navigation" else label
            ),
        }
        if on_change is not None:
            attrs["data_vd_event_change"] = bind_event(on_change)
        super().__init__(
            _SidebarToggleGlyph(),
            type="button",
            aria_label=(
                attrs["data_vd_sidebar_collapse_label"]
                if current_mode == "expanded"
                else attrs["data_vd_sidebar_expand_label"]
            ),
            aria_controls=target_id,
            aria_expanded=(
                "true"
                if isinstance(target, Sidebar)
                and target.attrs.get("data_vd_sidebar_mode") == "expanded"
                else "false"
            ),
            **attrs,
            **kwargs,
        )
        self.props = {"placement": placement}


def _configure_sidebar_toggle(
    toggle: SidebarToggle,
    sidebar: Sidebar,
    placement: str,
) -> None:
    toggle.props["placement"] = placement
    toggle.attrs["data_vd_sidebar_placement"] = placement
    toggle.attrs["data_vd_sidebar_current_mode"] = sidebar.attrs.get(
        "data_vd_sidebar_mode", "expanded"
    )


class _SidebarControls(Component):
    style = "sidebar-controls"
    auto_id = False


class _SidebarHeader(Component):
    style = "sidebar-header"
    auto_id = False


class _SidebarBrand(Component):
    style = "sidebar-brand"
    auto_id = False

    def __init__(
        self,
        *,
        logo: Any | None,
        brand: Any | None,
        href: str | None,
        label: str | None,
    ) -> None:
        self.tag = "a" if href else "div"
        children: list[Any] = []
        if logo is not None:
            children.append(_SidebarBrandMark(logo))
        if brand is not None:
            children.append(_SidebarBrandText(brand))
        accessible_label = label
        if accessible_label is None:
            accessible_label = brand if isinstance(brand, str) else "Application"
        super().__init__(
            *children,
            href=href,
            aria_label=accessible_label,
            data_vd_sidebar_brand=True,
        )
        if not children:
            self.attrs["hidden"] = True


class _SidebarBrandMark(Component):
    tag = "span"
    style = "sidebar-brand.mark"
    auto_id = False

    def __init__(self, *children: Any) -> None:
        super().__init__(*children, aria_hidden="true")


class _SidebarBrandText(Component):
    tag = "span"
    style = "sidebar-brand.text"
    auto_id = False

    def __init__(self, *children: Any) -> None:
        super().__init__(*children, data_vd_sidebar_label=True)


class _SidebarToggleGlyph(Component):
    tag = "span"
    style = "sidebar-toggle.glyph"
    auto_id = False

    def __init__(self) -> None:
        super().__init__(data_vd_sidebar_toggle_glyph=True, aria_hidden="true")


class BottomNav(Component):
    """Touch-friendly primary navigation for compact PWA layouts."""

    tag = "nav"
    style = "bottom-nav"

    def __init__(
        self,
        *items: BottomNavItem,
        label: str = "Primary navigation",
        **kwargs: Any,
    ) -> None:
        if not 2 <= len(items) <= 5:
            raise ValueError("BottomNav requires between two and five items")
        if not all(isinstance(item, BottomNavItem) for item in items):
            raise TypeError("BottomNav children must be BottomNavItem instances")
        super().__init__(*items, aria_label=label, **kwargs)


class BottomNavItem(Component):
    """One icon-and-label destination in a mobile bottom bar."""

    tag = "a"
    style = "bottom-nav-item"

    def __init__(
        self,
        label: str,
        href: str,
        *,
        icon: Component | None = None,
        active: bool = False,
        on_click: EventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        attrs: dict[str, Any] = {"href": href, "aria_label": label}
        if active:
            attrs["aria_current"] = "page"
        if on_click is not None:
            attrs["data_vd_event_click"] = bind_event(on_click)
        super().__init__(**attrs, **kwargs)
        self.props = {"active": active}
        children: list[Component] = []
        if icon is not None:
            children.append(_BottomNavIcon(icon))
        children.append(_BottomNavLabel(label))
        self.children = tuple(children)


class _BottomNavIcon(Component):
    tag = "span"
    style = "bottom-nav-item.icon"
    auto_id = False


class _BottomNavLabel(Component):
    tag = "span"
    style = "bottom-nav-item.label"
    auto_id = False


__all__ = [
    "AppShell",
    "BottomNav",
    "BottomNavItem",
    "SidebarItem",
    "SidebarToggle",
]
