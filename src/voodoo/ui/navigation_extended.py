"""Priority 3 — Adaptive Navigation.

Pagination, stepper, anchor navigation, action sheet, bottom sheet,
top bar, and navigation menu.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import uuid4

from voodoo.ui.component import Component
from voodoo.ui.events import bind_event
from voodoo.ui.interactive import Button
from voodoo.ui.library import Icon, Text

EventHandler = Callable[..., Any] | str


def _nav_id(prefix: str) -> str:
    return f"vd-{prefix}-{uuid4().hex[:8]}"


# ── Pagination ───────────────────────────────────────────────────────────────


class Pagination(Component):
    """Page-based navigation with prev/next and numbered pages.

    Automatically collapses page numbers on narrow screens, showing
    first, last, and a window around the current page.

    Example::

        Pagination(
            total_pages=20,
            current_page=5,
            label="Results pagination",
            on_change=go_to_page,
        )
    """

    style = "pagination"

    def __init__(
        self,
        *,
        total_pages: int,
        current_page: int = 1,
        sibling_count: int = 1,
        label: str = "Pagination",
        on_change: EventHandler | None = None,
        disabled: bool = False,
        **kwargs: Any,
    ) -> None:
        if total_pages < 1:
            raise ValueError("Pagination total_pages must be at least 1")
        if current_page < 1 or current_page > total_pages:
            raise ValueError(
                "Pagination current_page must be between 1 and total_pages"
            )
        if sibling_count < 0:
            raise ValueError("Pagination sibling_count must be non-negative")

        binding = bind_event(on_change) if on_change is not None else None

        items: list[Component] = []

        # Previous
        prev = _PaginationPrev(
            Icon("chevron-left", aria_hidden="true"),
            type="button",
            aria_label="Previous page",
            data_vd_page=str(current_page - 1),
            disabled=current_page <= 1 or disabled,
            data_vd_event_click=binding,
            data_vd_pagination_action=True,
        )
        items.append(prev)

        # Page numbers
        pages = _pagination_range(current_page, total_pages, sibling_count)
        for page in pages:
            if page == "…":
                items.append(_PaginationEllipsis())
            else:
                is_current = page == current_page
                items.append(
                    _PaginationPage(
                        str(page),
                        type="button",
                        aria_label=f"Page {page}",
                        aria_current="page" if is_current else None,
                        data_vd_page=str(page),
                        data_vd_event_click=binding,
                        disabled=disabled,
                        data_vd_pagination_action=True,
                    )
                )

        # Next
        next_btn = _PaginationNext(
            Icon("chevron-right", aria_hidden="true"),
            type="button",
            aria_label="Next page",
            data_vd_page=str(current_page + 1),
            disabled=current_page >= total_pages or disabled,
            data_vd_event_click=binding,
            data_vd_pagination_action=True,
        )
        items.append(next_btn)

        super().__init__(
            *items,
            role="navigation",
            aria_label=label,
            data_vd_pagination=True,
            data_vd_current_page=str(current_page),
            data_vd_total_pages=str(total_pages),
            **kwargs,
        )
        self.props = {"total_pages": total_pages, "current_page": current_page}


def _pagination_range(current: int, total: int, siblings: int) -> list[int | str]:
    """Calculate which page numbers and ellipses to show."""
    if total <= (2 * siblings + 5):
        return list(range(1, total + 1))

    pages: list[int | str] = []
    left = max(2, current - siblings)
    right = min(total - 1, current + siblings)

    pages.append(1)
    if left > 2:
        pages.append("…")
    pages.extend(range(left, right + 1))
    if right < total - 1:
        pages.append("…")
    pages.append(total)

    return pages


class _PaginationPrev(Component):
    tag = "button"
    style = "pagination.prev"
    auto_id = False


class _PaginationNext(Component):
    tag = "button"
    style = "pagination.next"
    auto_id = False


class _PaginationPage(Component):
    tag = "button"
    style = "pagination.page"
    auto_id = False


class _PaginationEllipsis(Component):
    tag = "span"
    style = "pagination.ellipsis"
    auto_id = False

    def __init__(self) -> None:
        super().__init__("…", aria_hidden="true")


# ── Stepper ──────────────────────────────────────────────────────────────────


class Stepper(Component):
    """Multi-step flow indicator for onboarding, checkout, and wizards.

    Example::

        Stepper(
            Step("Account", description="Create your account"),
            Step("Profile", description="Set up your profile"),
            Step("Billing", description="Add payment method"),
            Step("Confirm", description="Review and submit"),
            current=1,
            label="Setup progress",
        )
    """

    style = "stepper"

    def __init__(
        self,
        *steps: Step,
        current: int = 0,
        orientation: str = "horizontal",
        label: str = "Progress",
        on_step_click: EventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        if not steps:
            raise ValueError("Stepper requires at least one Step")
        if orientation not in {"horizontal", "vertical"}:
            raise ValueError("Stepper orientation must be horizontal or vertical")
        if current < 0 or current >= len(steps):
            raise ValueError("Stepper current must be a valid step index")

        binding = bind_event(on_step_click) if on_step_click is not None else None

        rendered: list[Component] = []
        for index, step in enumerate(steps):
            state = (
                "completed"
                if index < current
                else "active"
                if index == current
                else "upcoming"
            )
            rendered.append(step.render_step(index, state, binding))

        super().__init__(
            *rendered,
            role="navigation",
            aria_label=label,
            data_vd_stepper=True,
            data_vd_orientation=orientation,
            **kwargs,
        )
        self.props = {"current": current, "orientation": orientation}


class Step:
    """A single step in a :class:`Stepper`."""

    def __init__(
        self,
        label: str,
        *,
        description: str | None = None,
        icon: Component | None = None,
        disabled: bool = False,
    ) -> None:
        self.label = label
        self.description = description
        self.icon = icon
        self.disabled = disabled

    def render_step(
        self,
        index: int,
        state: str,
        binding: str | None,
    ) -> Component:
        attrs: dict[str, Any] = {
            "aria_current": "step" if state == "active" else None,
            "data_vd_step_state": state,
            "data_vd_step_index": str(index),
        }
        if binding and not self.disabled and state == "completed":
            attrs["data_vd_event_click"] = binding

        indicator_children: list[Any] = []
        if self.icon and state == "completed":
            indicator_children.append(self.icon)
        else:
            indicator_children.append(Text(str(index + 1), class_="vd-step-number"))

        copy_children: list[Any] = [
            _StepLabel(self.label),
        ]
        if self.description:
            copy_children.append(_StepDescription(self.description))

        return _StepItem(
            _StepIndicator(*indicator_children, data_vd_step_indicator=True),
            _StepContent(*copy_children),
            **attrs,
        )


class _StepItem(Component):
    style = "stepper.step"
    auto_id = False


class _StepIndicator(Component):
    tag = "span"
    style = "stepper.indicator"
    auto_id = False


class _StepContent(Component):
    style = "stepper.content"
    auto_id = False


class _StepLabel(Component):
    tag = "span"
    style = "stepper.label"
    auto_id = False


class _StepDescription(Component):
    tag = "span"
    style = "stepper.description"
    auto_id = False


# ── AnchorNavigation ─────────────────────────────────────────────────────────


class AnchorNavigation(Component):
    """Table of contents / anchor navigation with scroll-spy support.

    Renders a vertical list of anchor links that the client runtime
    highlights based on scroll position.

    Example::

        AnchorNavigation(
            AnchorLink("Introduction", href="#introduction"),
            AnchorLink("Getting started", href="#getting-started"),
            AnchorLink("Configuration", href="#configuration"),
            AnchorLink("API reference", href="#api"),
            label="On this page",
        )
    """

    style = "anchor-nav"

    def __init__(
        self,
        *links: AnchorLink,
        label: str = "On this page",
        active_class: str = "active",
        **kwargs: Any,
    ) -> None:
        if not links:
            raise ValueError("AnchorNavigation requires at least one AnchorLink")
        list_items = tuple(_AnchorItem(link.render_link()) for link in links)
        super().__init__(
            _AnchorHeading(label),
            _AnchorList(
                *list_items,
                role="list",
            ),
            role="navigation",
            aria_label=label,
            data_vd_anchor_nav=True,
            **kwargs,
        )


class AnchorLink:
    """An anchor link inside an :class:`AnchorNavigation`."""

    def __init__(
        self,
        label: str,
        *,
        href: str,
        level: int = 0,
        icon: Component | None = None,
    ) -> None:
        self.label = label
        self.href = href
        self.level = level
        self.icon = icon

    def render_link(self) -> Component:
        children: list[Any] = []
        if self.icon:
            children.append(self.icon)
        children.append(Text(self.label))
        return _AnchorLink(
            *children,
            href=self.href,
            data_vd_anchor_level=str(self.level),
            aria_label=self.label,
        )


class _AnchorHeading(Component):
    tag = "h2"
    style = "anchor-nav.heading"
    auto_id = False


class _AnchorList(Component):
    tag = "ul"
    style = "anchor-nav.list"
    auto_id = False


class _AnchorItem(Component):
    tag = "li"
    style = "anchor-nav.item"
    auto_id = False


class _AnchorLink(Component):
    tag = "a"
    style = "anchor-nav.link"
    auto_id = False


# ── ActionSheet ──────────────────────────────────────────────────────────────


class ActionSheet(Component):
    """Mobile bottom action picker with optional cancel.

    Example::

        ActionSheet(
            Action("Edit", icon=Icon("edit"), on_select=edit_item),
            Action("Share", icon=Icon("share"), on_select=share_item),
            Action("Delete", icon=Icon("trash"), destructive=True, on_select=delete_item),
            title="Choose action",
            cancel_label="Cancel",
        )
    """

    style = "action-sheet"

    def __init__(
        self,
        *actions: Action,
        title: str | None = None,
        description: str | None = None,
        cancel_label: str = "Cancel",
        on_cancel: EventHandler | None = None,
        open: bool = False,
        **kwargs: Any,
    ) -> None:
        if not actions:
            raise ValueError("ActionSheet requires at least one Action")
        super().__init__(**kwargs)
        sheet_id = f"{self.id}-panel" if self.id else _nav_id("action-sheet")

        header_children: list[Any] = []
        if title:
            header_children.append(_ActionSheetTitle(title))
        if description:
            header_children.append(_ActionSheetDescription(description))

        action_list = _ActionSheetList(
            *actions,
            role="list",
        )

        cancel = _ActionSheetCancel(
            cancel_label,
            type="button",
            data_vd_dialog_close=True,
            data_vd_event_click=bind_event(on_cancel) if on_cancel else None,
        )

        panel = _ActionSheetPanel(
            _ActionSheetHeader(*header_children) if header_children else None,
            action_list,
            cancel,
            id=sheet_id,
            role="dialog",
            aria_modal="true",
            aria_label=title or "Actions",
            tabindex="-1",
            data_vd_layer=True,
            data_vd_action_sheet=True,
            open=open,
        )
        self.children = (panel,)


class _ActionSheetPanel(Component):
    tag = "dialog"
    style = "action-sheet.panel"
    auto_id = False


class _ActionSheetHeader(Component):
    style = "action-sheet.header"
    auto_id = False


class _ActionSheetTitle(Component):
    tag = "h2"
    style = "action-sheet.title"
    auto_id = False


class _ActionSheetDescription(Component):
    tag = "p"
    style = "action-sheet.description"
    auto_id = False


class _ActionSheetList(Component):
    style = "action-sheet.list"
    auto_id = False


class _ActionSheetCancel(Component):
    tag = "button"
    style = "action-sheet.cancel"
    auto_id = False


class Action(Component):
    """An action item inside an :class:`ActionSheet`."""

    tag = "button"
    style = "action-item"

    def __init__(
        self,
        *children: Any,
        icon: Component | None = None,
        description: str | None = None,
        destructive: bool = False,
        disabled: bool = False,
        on_select: EventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        attrs: dict[str, Any] = {
            "type": "button",
            "role": "button",
        }
        if disabled:
            attrs["disabled"] = True
            attrs["aria_disabled"] = "true"
        if on_select is not None and not disabled:
            attrs["data_vd_event_click"] = bind_event(on_select)

        content: list[Any] = []
        if icon is not None:
            content.append(_ActionIcon(icon))
        copy_children: list[Any] = list(children)
        if description:
            copy_children.append(Component(description, class_="vd-action-description"))
        content.append(_ActionCopy(*copy_children))

        super().__init__(*content, **attrs, **kwargs)
        self.props = {"destructive": destructive, "disabled": disabled}


class _ActionIcon(Component):
    tag = "span"
    style = "action-item.icon"
    auto_id = False


class _ActionCopy(Component):
    tag = "span"
    style = "action-item.copy"
    auto_id = False


# ── BottomSheet ──────────────────────────────────────────────────────────────


class BottomSheet(Component):
    """Full-featured bottom sheet with snap points and drag gestures.

    Supports multiple snap points (e.g. 25%, 50%, 90%) and can be
    configured to be dismissible by swiping down.

    Example::

        BottomSheet(
            Heading("Filters", level=3),
            filter_form,
            snap_points=(25, 50, 90),
            default_snap=50,
            title="Filters",
            dismissible=True,
        )
    """

    style = "bottom-sheet"

    def __init__(
        self,
        *children: Any,
        title: str | None = None,
        snap_points: tuple[int, ...] = (50, 90),
        default_snap: int | None = None,
        dismissible: bool = True,
        open: bool = False,
        close_label: str = "Close",
        **kwargs: Any,
    ) -> None:
        if not snap_points:
            raise ValueError("BottomSheet requires at least one snap point")
        if any(p < 1 or p > 100 for p in snap_points):
            raise ValueError("BottomSheet snap_points must be percentages (1-100)")

        default = default_snap or snap_points[0]
        super().__init__(**kwargs)
        sheet_id = f"{self.id}-panel" if self.id else _nav_id("bottom-sheet")
        title_id = f"{sheet_id}-title"

        header_children: list[Any] = []
        header_children.append(_BottomSheetHandle())
        if title:
            header_children.append(_BottomSheetTitle(title, id=title_id))
        header_children.append(
            Button(
                close_label,
                type="button",
                variant="ghost",
                aria_label=close_label,
                data_vd_dialog_close=True,
            )
        )

        panel = _BottomSheetPanel(
            _BottomSheetHeader(*header_children),
            _BottomSheetBody(*children),
            id=sheet_id,
            role="dialog",
            aria_modal="true",
            aria_labelledby=title_id if title else None,
            tabindex="-1",
            data_vd_layer=True,
            data_vd_bottom_sheet=True,
            data_vd_dismissible=dismissible,
            data_vd_snap_points=",".join(str(p) for p in snap_points),
            data_vd_default_snap=str(default),
            open=open,
        )
        self.children = (panel,)


class _BottomSheetPanel(Component):
    tag = "dialog"
    style = "bottom-sheet.panel"
    auto_id = False


class _BottomSheetHeader(Component):
    style = "bottom-sheet.header"
    auto_id = False


class _BottomSheetTitle(Component):
    tag = "h2"
    style = "bottom-sheet.title"
    auto_id = False


class _BottomSheetHandle(Component):
    tag = "div"
    style = "bottom-sheet.handle"
    auto_id = False

    def __init__(self) -> None:
        super().__init__(aria_hidden="true")


class _BottomSheetBody(Component):
    style = "bottom-sheet.body"
    auto_id = False


# ── TopBar ───────────────────────────────────────────────────────────────────


class TopBar(Component):
    """Responsive application header with slots for branding, navigation, and actions.

    On mobile, the TopBar collapses the center slot into a hamburger menu.

    Example::

        TopBar(
            leading=Brand("Acme", logo="A", href="/"),
            center=Nav(
                NavLink("Products", href="/products"),
                NavLink("Docs", href="/docs"),
                NavLink("Pricing", href="/pricing"),
            ),
            trailing=Button("Sign in", variant="primary"),
            title="Acme",
        )
    """

    style = "top-bar"

    def __init__(
        self,
        *,
        leading: Component | None = None,
        center: Component | None = None,
        trailing: Component | None = None,
        title: str | None = None,
        sticky: bool = True,
        **kwargs: Any,
    ) -> None:
        children: list[Any] = []
        if leading:
            children.append(_TopBarLeading(leading))
        if title and not leading:
            children.append(_TopBarTitle(title))
        if center:
            children.append(_TopBarCenter(center))
        if trailing:
            children.append(_TopBarTrailing(trailing))

        attrs: dict[str, Any] = {
            "role": "banner",
            "data_vd_top_bar": True,
        }
        if sticky:
            attrs["data_vd_sticky"] = True

        super().__init__(*children, **attrs, **kwargs)
        self.props = {"sticky": sticky}


class _TopBarLeading(Component):
    style = "top-bar.leading"
    auto_id = False


class _TopBarCenter(Component):
    style = "top-bar.center"
    auto_id = False


class _TopBarTrailing(Component):
    style = "top-bar.trailing"
    auto_id = False


class _TopBarTitle(Component):
    tag = "span"
    style = "top-bar.title"
    auto_id = False


# ── NavigationMenu ──────────────────────────────────────────────────────────


class NavigationMenu(Component):
    """Mega-menu for websites and documentation with nested content.

    Each trigger opens a panel with rich content, not just links.

    Example::

        NavigationMenu(
            NavTrigger("Products",
                NavContent(
                    NavColumn(
                        NavLinkItem("Analytics", href="/analytics", description="Real-time insights"),
                        NavLinkItem("Automation", href="/automation", description="Workflow engine"),
                    ),
                    NavColumn(
                        NavLinkItem("Security", href="/security", description="Enterprise-grade"),
                        NavLinkItem("Compliance", href="/compliance", description="SOC2, GDPR"),
                    ),
                ),
            ),
            NavTrigger("Resources",
                NavContent(
                    NavLinkItem("Documentation", href="/docs"),
                    NavLinkItem("Blog", href="/blog"),
                    NavLinkItem("Community", href="/community"),
                ),
            ),
            label="Main navigation",
        )
    """

    style = "navigation-menu"

    def __init__(
        self,
        *triggers: NavTrigger,
        label: str = "Main navigation",
        **kwargs: Any,
    ) -> None:
        if not triggers:
            raise ValueError("NavigationMenu requires at least one NavTrigger")
        items = tuple(_NavItem(trigger.render_trigger()) for trigger in triggers)
        super().__init__(
            _NavList(*items, role="menubar", aria_label=label),
            data_vd_navigation_menu=True,
            **kwargs,
        )


class _NavList(Component):
    tag = "ul"
    style = "navigation-menu.list"
    auto_id = False


class _NavItem(Component):
    tag = "li"
    style = "navigation-menu.item"
    auto_id = False


class NavTrigger:
    """A trigger with its associated content panel in a :class:`NavigationMenu`."""

    def __init__(
        self,
        label: str,
        content: Component,
        *,
        href: str | None = None,
        disabled: bool = False,
    ) -> None:
        self.label = label
        self.content = content
        self.href = href
        self.disabled = disabled

    def render_trigger(self) -> Component:
        trigger_id = _nav_id("nav-trigger")
        content_id = _nav_id("nav-content")

        trigger = _NavTriggerButton(
            Text(self.label),
            id=trigger_id,
            type="button",
            aria_haspopup="true",
            aria_controls=content_id,
            aria_expanded="false",
            data_vd_nav_trigger=content_id,
            disabled=self.disabled,
        )

        panel = _NavContentPanel(
            self.content,
            id=content_id,
            data_vd_nav_content=True,
            hidden=True,
        )
        return _NavTriggerWrapper(trigger, panel)


class _NavTriggerWrapper(Component):
    auto_id = False


class _NavTriggerButton(Component):
    tag = "button"
    style = "navigation-menu.trigger"
    auto_id = False


class _NavContentPanel(Component):
    style = "navigation-menu.content"
    auto_id = False


class NavContent(Component):
    """Content panel inside a :class:`NavTrigger`."""

    style = "nav-content"

    def __init__(self, *children: Any, **kwargs: Any) -> None:
        super().__init__(*children, **kwargs)


class NavColumn(Component):
    """A vertical column of navigation items inside a :class:`NavContent`."""

    style = "nav-column"

    def __init__(self, *children: Any, **kwargs: Any) -> None:
        super().__init__(*children, **kwargs)


class NavLinkItem(Component):
    """A rich navigation link with optional icon and description."""

    style = "nav-link-item"

    def __init__(
        self,
        *children: Any,
        href: str,
        icon: Component | None = None,
        description: str | None = None,
        disabled: bool = False,
        **kwargs: Any,
    ) -> None:
        content: list[Any] = []
        if icon:
            content.append(_NavLinkIcon(icon))
        copy_children: list[Any] = list(children)
        if description:
            copy_children.append(
                Component(description, class_="vd-nav-link-description")
            )
        content.append(_NavLinkCopy(*copy_children))

        attrs: dict[str, Any] = {"href": href}
        if disabled:
            attrs["aria_disabled"] = "true"
            attrs["tabindex"] = "-1"

        super().__init__(*content, role="menuitem", **attrs, **kwargs)


class _NavLinkIcon(Component):
    tag = "span"
    style = "nav-link-item.icon"
    auto_id = False


class _NavLinkCopy(Component):
    tag = "span"
    style = "nav-link-item.copy"
    auto_id = False
