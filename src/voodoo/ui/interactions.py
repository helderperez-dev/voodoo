"""Interactive overlays, menus, tabs, and transient feedback."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import uuid4

from voodoo.ui.component import Component
from voodoo.ui.events import bind_event
from voodoo.ui.interactive import Button

EventHandler = Callable[..., Any] | str


def _target_id(target: Component | str) -> str:
    target_id = target.id if isinstance(target, Component) else target
    if not target_id:
        raise ValueError("interaction target must have an id")
    return target_id


def _ensure_id(component: Component, prefix: str) -> str:
    """Ensure externally supplied triggers can participate in ARIA relationships."""
    if component.id:
        return component.id
    generated = f"vd-{prefix}-{uuid4().hex[:8]}"
    component.attrs["id"] = generated
    return generated


def _require_button_trigger(component: Component, owner: str) -> None:
    if component.tag != "button":
        raise TypeError(f"{owner} trigger must render a button")


class ModalTrigger(Button):
    """Button that opens a native Voodoo ``Modal`` or ``Dialog``."""

    def __init__(self, *children: Any, target: Component | str, **kwargs: Any) -> None:
        target_id = _target_id(target)
        super().__init__(*children, **kwargs)
        self.attrs["data_vd_dialog_open"] = target_id
        self.attrs["aria_controls"] = target_id
        self.attrs["aria_haspopup"] = "dialog"


class ModalClose(Button):
    """Button that closes its nearest dialog."""

    def __init__(self, *children: Any, **kwargs: Any) -> None:
        kwargs.setdefault("variant", "ghost")
        super().__init__(*children, **kwargs)
        self.attrs["data_vd_dialog_close"] = True


class Drawer(Component):
    """Responsive modal panel entering from a screen edge."""

    style = "drawer-shell"

    def __init__(
        self,
        trigger: Component,
        *children: Any,
        title: Any,
        description: Any | None = None,
        side: str = "left",
        size: str = "md",
        open: bool = False,
        dismissible: bool = True,
        close_label: str = "Close",
        **kwargs: Any,
    ) -> None:
        if side not in {"left", "right", "top", "bottom"}:
            raise ValueError("Drawer side must be left, right, top, or bottom")
        if size not in {"sm", "md", "lg", "full"}:
            raise ValueError("Drawer size must be sm, md, lg, or full")
        _require_button_trigger(trigger, "Drawer")
        super().__init__(**kwargs)
        drawer_id = f"{self.id}-panel" if self.id else f"vd-drawer-{uuid4().hex[:8]}"
        title_id = f"{drawer_id}-title"
        _ensure_id(trigger, "drawer-trigger")
        trigger.attrs["data_vd_dialog_open"] = drawer_id
        trigger.attrs["aria_controls"] = drawer_id
        trigger.attrs["aria_haspopup"] = "dialog"
        header_children: list[Any] = [_DrawerTitle(title, id=title_id)]
        if description:
            header_children.append(_DrawerDescription(description))
        header_children.append(ModalClose(close_label, aria_label=close_label))
        panel = _DrawerPanel(
            _DrawerHeader(*header_children),
            _DrawerBody(*children),
            id=drawer_id,
            open=open,
            role="dialog",
            tabindex="-1",
            aria_modal="true",
            aria_labelledby=title_id,
            data_vd_layer=True,
            data_vd_drawer=True,
            data_vd_dismissible=dismissible,
        )
        panel.props = {"side": side, "size": size}
        self.children = (trigger, panel)


class _DrawerPanel(Component):
    tag = "dialog"
    style = "drawer"


class _DrawerHeader(Component):
    style = "drawer.header"
    auto_id = False


class _DrawerTitle(Component):
    tag = "h2"
    style = "drawer.title"


class _DrawerDescription(Component):
    tag = "p"
    style = "drawer.description"
    auto_id = False


class _DrawerBody(Component):
    style = "drawer.body"
    auto_id = False


class DropdownMenu(Component):
    """Anchored action menu using the native Popover API."""

    style = "dropdown-shell"

    def __init__(
        self,
        trigger: Component,
        *items: MenuItem | MenuSeparator,
        label: str = "Menu",
        align: str = "start",
        **kwargs: Any,
    ) -> None:
        if align not in {"start", "center", "end"}:
            raise ValueError("DropdownMenu align must be start, center, or end")
        if not items:
            raise ValueError("DropdownMenu requires at least one MenuItem")
        if not all(isinstance(item, (MenuItem, MenuSeparator)) for item in items):
            raise TypeError("DropdownMenu children must be MenuItem or MenuSeparator")
        _require_button_trigger(trigger, "DropdownMenu")
        super().__init__(**kwargs)
        menu_id = f"{self.id}-menu" if self.id else f"vd-menu-{uuid4().hex[:8]}"
        trigger_id = _ensure_id(trigger, "menu-trigger")
        trigger.attrs["popovertarget"] = menu_id
        trigger.attrs["aria_haspopup"] = "menu"
        trigger.attrs["aria_controls"] = menu_id
        trigger.attrs["aria_expanded"] = "false"
        trigger.attrs["data_vd_menu_trigger"] = menu_id
        panel = _MenuPanel(
            *items,
            id=menu_id,
            popover=True,
            role="menu",
            aria_label=label,
            tabindex="-1",
            data_vd_menu=True,
            data_vd_align=align,
            data_vd_anchor=trigger_id,
        )
        self.children = (trigger, panel)


class _MenuPanel(Component):
    style = "dropdown-menu"


class MenuItem(Component):
    """One menu action or destination."""

    style = "menu-item"

    def __init__(
        self,
        *children: Any,
        href: str | None = None,
        on_select: EventHandler | None = None,
        disabled: bool = False,
        destructive: bool = False,
        shortcut: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.tag = "a" if href and not disabled else "button"
        attrs: dict[str, Any] = {"role": "menuitem", "tabindex": "-1"}
        if href and not disabled:
            attrs["href"] = href
        else:
            attrs["type"] = "button"
        if disabled:
            attrs["disabled"] = True
            attrs["aria_disabled"] = "true"
        if on_select is not None and not disabled:
            attrs["data_vd_event_click"] = bind_event(on_select)
        super().__init__(**attrs, **kwargs)
        self.props = {"destructive": destructive}
        content: list[Component] = [_MenuItemLabel(*children)]
        if shortcut:
            content.append(_MenuShortcut(shortcut))
        self.children = tuple(content)


class _MenuItemLabel(Component):
    tag = "span"
    style = "menu-item.label"
    auto_id = False


class _MenuShortcut(Component):
    tag = "span"
    style = "menu-shortcut"
    auto_id = False


class MenuSeparator(Component):
    tag = "hr"
    style = "menu-separator"
    auto_id = False

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(role="separator", **kwargs)


class Tabs(Component):
    """Accessible tab set with automatic keyboard navigation."""

    style = "tabs"

    def __init__(
        self,
        *tabs: Tab,
        value: str | None = None,
        orientation: str = "horizontal",
        activation: str = "automatic",
        on_change: EventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        if not tabs:
            raise ValueError("Tabs requires at least one Tab")
        if not all(isinstance(tab, Tab) for tab in tabs):
            raise TypeError("Tabs children must be Tab instances")
        if orientation not in {"horizontal", "vertical"}:
            raise ValueError("Tabs orientation must be horizontal or vertical")
        if activation not in {"automatic", "manual"}:
            raise ValueError("Tabs activation must be automatic or manual")
        values = [tab.value for tab in tabs]
        if len(values) != len(set(values)):
            raise ValueError("Tabs values must be unique")
        enabled = [tab for tab in tabs if not tab.disabled]
        if not enabled:
            raise ValueError("Tabs requires at least one enabled Tab")
        selected = value or enabled[0].value
        if selected not in {tab.value for tab in tabs}:
            raise ValueError(f"Tabs value {selected!r} does not match a Tab")
        if next(tab for tab in tabs if tab.value == selected).disabled:
            raise ValueError("Tabs value cannot select a disabled Tab")
        attrs: dict[str, Any] = {
            "data_vd_tabs": True,
            "data_vd_orientation": orientation,
            "data_vd_activation": activation,
        }
        if on_change is not None:
            attrs["data_vd_event_change"] = bind_event(on_change)
        super().__init__(
            **attrs,
            **kwargs,
        )
        self.props = {"orientation": orientation, "activation": activation}
        tablist = _TabList(
            *(
                tab.trigger(selected, self.id or "", index)
                for index, tab in enumerate(tabs)
            ),
            role="tablist",
            aria_orientation=orientation,
        )
        panels = tuple(

        )
        self.children = (tablist, *panels)


class Tab:
    """Declarative label/content pair consumed by :class:`Tabs`."""

    def __init__(
        self,
        value: str,
        label: Any,
        *children: Any,
        disabled: bool = False,
    ) -> None:
        if not value:
            raise ValueError("Tab value cannot be empty")
        self.value = value
        self.label = label
        self.children = children
        self.disabled = disabled

    def trigger(self, selected: str, root_id: str, index: int) -> Component:
        active = self.value == selected
        return _TabTrigger(
            self.label,
            id=f"{root_id}-tab-{index}",
            type="button",
            role="tab",
            aria_selected="true" if active else "false",
            aria_controls=f"{root_id}-panel-{index}",
            tabindex="0" if active else "-1",
            disabled=self.disabled,
            data_vd_tab=self.value,
        )

    def panel(self, selected: str, root_id: str, index: int) -> Component:
        active = self.value == selected
        return _TabPanel(
            *self.children,
            id=f"{root_id}-panel-{index}",
            role="tabpanel",
            aria_labelledby=f"{root_id}-tab-{index}",
            tabindex="0",
            hidden=not active,
            data_vd_tab_panel=self.value,
        )


class _TabList(Component):
    style = "tabs.list"
    auto_id = False


class _TabTrigger(Component):
    tag = "button"
    style = "tabs.trigger"


class _TabPanel(Component):
    style = "tabs.panel"


class ToastRegion(Component):
    """Accessible container for transient notifications."""

    style = "toast-region"

    def __init__(
        self,
        *toasts: Toast,
        position: str = "bottom-right",
        label: str = "Notifications",
        **kwargs: Any,
    ) -> None:
        if position not in {"top-left", "top-right", "bottom-left", "bottom-right"}:
            raise ValueError("invalid ToastRegion position")
        if not all(isinstance(toast, Toast) for toast in toasts):
            raise TypeError("ToastRegion children must be Toast instances")
        super().__init__(
            *toasts,
            aria_label=label,
            aria_live="polite",
            aria_relevant="additions removals",
            **kwargs,
        )
        self.props = {"position": position}
        self.attrs["data_vd_toast_region"] = True


class Toast(Component):
    """Transient status message with optional action and dismissal."""

    style = "toast"

    def __init__(
        self,
        message: str,
        *,
        title: str | None = None,
        tone: str = "default",
        duration: int | None = 5000,
        action: Component | None = None,
        dismissible: bool = True,
        variant: str = "toast",
        **kwargs: Any,
    ) -> None:
        if tone not in {"default", "info", "success", "warning", "danger"}:
            raise ValueError("invalid Toast tone")
        if duration is not None and duration < 0:
            raise ValueError("Toast duration cannot be negative")
        if action is not None and not isinstance(action, Component):
            raise TypeError("Toast action must be a Component")
        super().__init__(
            role="alert" if tone == "danger" else "status",
            data_vd_toast=True,
            data_vd_duration=duration,
            **kwargs,
        )
        self.props = {"tone": tone, "variant": variant}
        content: list[Any] = []
        if title:
            content.append(_ToastTitle(title))
        content.append(_ToastMessage(message))
        actions = [action] if action is not None else []
        if dismissible:
            actions.append(_ToastDismiss("Close", aria_label="Dismiss notification"))
        children: list[Component] = [_ToastContent(*content)]
        if actions:
            children.append(_ToastActions(*actions))
        self.children = tuple(children)


class Snackbar(Toast):
    """Compact, bottom-oriented toast suitable for mobile and PWA actions."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        kwargs["variant"] = "snackbar"
        super().__init__(message, **kwargs)


class _ToastContent(Component):
    style = "toast.content"
    auto_id = False


class _ToastTitle(Component):
    style = "toast.title"
    auto_id = False


class _ToastMessage(Component):
    style = "toast.message"
    auto_id = False


class _ToastActions(Component):
    style = "toast.actions"
    auto_id = False


class _ToastDismiss(Component):
    tag = "button"
    style = "toast.dismiss"
    auto_id = False

    def __init__(self, *children: Any, **kwargs: Any) -> None:
        super().__init__(*children, type="button", data_vd_dismiss=True, **kwargs)


__all__ = [
    "Drawer",
    "DropdownMenu",
    "MenuItem",
    "MenuSeparator",
    "ModalClose",
    "ModalTrigger",
    "Snackbar",
    "Tab",
    "Tabs",
    "Toast",
    "ToastRegion",
]
