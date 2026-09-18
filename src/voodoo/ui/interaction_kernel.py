"""Priority 1 — Interaction Kernel.

Destructive confirmations, toggle controls, advanced menu patterns,
desktop context menus, command palette, and shared overlay infrastructure.
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


def _control_id(prefix: str) -> str:
    return f"vd-{prefix}-{uuid4().hex[:8]}"


def _ensure_id(component: Component, prefix: str) -> str:
    if component.id:
        return component.id
    generated = f"vd-{prefix}-{uuid4().hex[:8]}"
    component.attrs["id"] = generated
    return generated


def _require_button_trigger(component: Component, owner: str) -> None:
    if component.tag != "button":
        raise TypeError(f"{owner} trigger must render a button")


# ── AlertDialog ───────────────────────────────────────────────────────────────


class AlertDialog(Component):
    """Destructive confirmation dialog with explicit confirm/cancel actions.

    Unlike :class:`Dialog` or :class:`Modal`, ``AlertDialog`` is specifically
    for actions that need user confirmation before proceeding. It uses
    ``role="alertdialog"`` for screen readers and enforces a tone.

    Example::

        AlertDialog(
            "This action cannot be undone. All data will be permanently deleted.",
            title="Delete project?",
            confirm_label="Delete",
            cancel_label="Keep",
            tone="danger",
            on_confirm=delete_project,
        )
    """

    style = "alert-dialog"

    def __init__(
        self,
        *children: Any,
        title: str,
        confirm_label: str = "Confirm",
        cancel_label: str = "Cancel",
        tone: str = "danger",
        on_confirm: EventHandler | None = None,
        on_cancel: EventHandler | None = None,
        open: bool = False,
        close_label: str = "Close",
        **kwargs: Any,
    ) -> None:
        if tone not in {"danger", "warning", "info"}:
            raise ValueError("AlertDialog tone must be danger, warning, or info")
        super().__init__(**kwargs)
        dialog_id = f"{self.id}-panel" if self.id else _control_id("alert-dialog")
        title_id = f"{dialog_id}-title"
        description_id = f"{dialog_id}-desc"

        actions: list[Component] = []
        if on_cancel is not None:
            actions.append(
                Button(
                    cancel_label,
                    type="button",
                    variant="ghost",
                    data_vd_dialog_close=True,
                    data_vd_event_click=bind_event(on_cancel),
                )
            )
        else:
            actions.append(
                Button(
                    cancel_label,
                    type="button",
                    variant="ghost",
                    data_vd_dialog_close=True,
                )
            )
        confirm_variant = "danger" if tone == "danger" else "primary"
        confirm_attrs: dict[str, Any] = {
            "type": "button",
            "variant": confirm_variant,
        }
        if on_confirm is not None:
            confirm_attrs["data_vd_event_click"] = bind_event(on_confirm)
        actions.append(Button(confirm_label, **confirm_attrs))

        panel = _AlertDialogPanel(
            _AlertDialogHeader(
                _AlertDialogTitle(title, id=title_id),
            ),
            _AlertDialogBody(
                *children,
                id=description_id,
            ),
            _AlertDialogFooter(*actions),
            id=dialog_id,
            role="alertdialog",
            aria_modal="true",
            aria_labelledby=title_id,
            aria_describedby=description_id,
            tabindex="-1",
            data_vd_layer=True,
            data_vd_alert_dialog=True,
            data_vd_tone=tone,
            open=open,
        )
        self.children = (panel,)


class _AlertDialogPanel(Component):
    tag = "dialog"
    style = "alert-dialog.panel"
    auto_id = False


class _AlertDialogHeader(Component):
    style = "alert-dialog.header"
    auto_id = False


class _AlertDialogTitle(Component):
    tag = "h2"
    style = "alert-dialog.title"
    auto_id = False


class _AlertDialogBody(Component):
    style = "alert-dialog.body"
    auto_id = False


class _AlertDialogFooter(Component):
    style = "alert-dialog.footer"
    auto_id = False


# ── AlertDialog trigger ──────────────────────────────────────────────────────


class AlertDialogTrigger(Button):
    """Button that opens an :class:`AlertDialog`."""

    def __init__(
        self, *children: Any, target: Component | str, **kwargs: Any
    ) -> None:
        target_id = target.id if isinstance(target, Component) else target
        if not target_id:
            raise ValueError("AlertDialogTrigger target must have an id")
        super().__init__(*children, **kwargs)
        self.attrs["data_vd_dialog_open"] = target_id
        self.attrs["aria_controls"] = target_id
        self.attrs["aria_haspopup"] = "dialog"


# ── ToggleGroup ──────────────────────────────────────────────────────────────


class ToggleGroup(Component):
    """A group of toggle buttons supporting single or multiple selection.

    Example::

        ToggleGroup(
            ToggleItem("bold", icon=Icon("bold")),
            ToggleItem("italic", icon=Icon("italic")),
            ToggleItem("underline", icon=Icon("underline")),
            type="multiple",
            value=["bold"],
            label="Text formatting",
        )
    """

    style = "toggle-group"

    def __init__(
        self,
        *items: ToggleItem,
        type: str = "single",
        value: str | list[str] | None = None,
        label: str = "Toggle",
        orientation: str = "horizontal",
        on_change: EventHandler | None = None,
        disabled: bool = False,
        **kwargs: Any,
    ) -> None:
        if type not in {"single", "multiple"}:
            raise ValueError("ToggleGroup type must be single or multiple")
        if orientation not in {"horizontal", "vertical"}:
            raise ValueError("ToggleGroup orientation must be horizontal or vertical")
        if not items:
            raise ValueError("ToggleGroup requires at least one ToggleItem")
        if not all(isinstance(item, ToggleItem) for item in items):
            raise TypeError("ToggleGroup children must be ToggleItem instances")

        selected = set()
        if value is not None:
            selected = {value} if isinstance(value, str) else set(value)

        attrs: dict[str, Any] = {
            "role": "group",
            "aria_label": label,
            "data_vd_toggle_group": True,
            "data_vd_toggle_type": type,
        }
        if on_change is not None:
            attrs["data_vd_event_change"] = bind_event(on_change)
        if disabled:
            attrs["aria_disabled"] = "true"
        super().__init__(**attrs, **kwargs)
        self.props = {"type": type, "orientation": orientation}

        rendered_items = tuple(
            item.render_toggled(item.value in selected, disabled)
            for item in items
        )
        self.children = rendered_items


class ToggleItem(Component):
    """An individual toggle button inside a :class:`ToggleGroup`."""

    tag = "button"
    style = "toggle-item"

    def __init__(
        self,
        *children: Any,
        value: str,
        icon: Component | None = None,
        label: str | None = None,
        disabled: bool = False,
        **kwargs: Any,
    ) -> None:
        self.value = value
        self._icon = icon
        self._label_text = label
        self._disabled = disabled
        self._children_raw = children
        super().__init__(**kwargs)

    def render_toggled(self, pressed: bool, group_disabled: bool) -> Component:
        """Return a configured toggle button for the group."""
        disabled = self._disabled or group_disabled
        content: list[Any] = []
        if self._icon is not None:
            content.append(self._icon)
        if self._label_text:
            content.append(Text(self._label_text, class_="vd-toggle-label"))
        content.extend(self._children_raw)

        attrs: dict[str, Any] = {
            "type": "button",
            "role": "button",
            "aria_pressed": "true" if pressed else "false",
            "data_vd_toggle_value": self.value,
            "data_vd_toggle_item": True,
        }
        if disabled:
            attrs["disabled"] = True
            attrs["aria_disabled"] = "true"
        if self._label_text:
            attrs["aria_label"] = self._label_text

        btn = Button(*content, **attrs)
        btn.style = "toggle-item"
        btn.props = {"pressed": pressed, "disabled": disabled}
        return btn


# ── SegmentedControl ─────────────────────────────────────────────────────────


class SegmentedControl(Component):
    """iOS-style segmented selector — a single-select :class:`ToggleGroup` variant.

    Example::

        SegmentedControl(
            Segment("list", label="List", icon=Icon("list")),
            Segment("grid", label="Grid", icon=Icon("grid")),
            Segment("table", label="Table", icon=Icon("table")),
            value="list",
            label="View mode",
        )
    """

    style = "segmented-control"

    def __init__(
        self,
        *segments: Segment,
        value: str | None = None,
        label: str = "Options",
        on_change: EventHandler | None = None,
        disabled: bool = False,
        **kwargs: Any,
    ) -> None:
        if not segments:
            raise ValueError("SegmentedControl requires at least one Segment")
        if not all(isinstance(seg, Segment) for seg in segments):
            raise TypeError("SegmentedControl children must be Segment instances")

        selected = value or segments[0].value
        attrs: dict[str, Any] = {
            "role": "tablist",
            "aria_label": label,
            "data_vd_segmented": True,
        }
        if on_change is not None:
            attrs["data_vd_event_change"] = bind_event(on_change)
        super().__init__(**attrs, **kwargs)

        rendered = tuple(
            seg.render_selected(seg.value == selected, disabled) for seg in segments
        )
        self.children = rendered


class Segment(Component):
    """An individual segment inside a :class:`SegmentedControl`."""

    tag = "button"
    style = "segment"

    def __init__(
        self,
        value: str,
        *,
        label: str,
        icon: Component | None = None,
        disabled: bool = False,
        **kwargs: Any,
    ) -> None:
        self.value = value
        self._label_text = label
        self._icon = icon
        self._disabled = disabled
        super().__init__(**kwargs)

    def render_selected(self, selected: bool, group_disabled: bool) -> Component:
        disabled = self._disabled or group_disabled
        content: list[Any] = []
        if self._icon is not None:
            content.append(self._icon)
        content.append(Text(self._label_text, class_="vd-segment-label"))

        attrs: dict[str, Any] = {
            "type": "button",
            "role": "tab",
            "aria_selected": "true" if selected else "false",
            "data_vd_segment_value": self.value,
            "tabindex": "0" if selected else "-1",
        }
        if disabled:
            attrs["disabled"] = True
            attrs["aria_disabled"] = "true"

        btn = Button(*content, **attrs)
        btn.style = "segment"
        btn.props = {"selected": selected, "disabled": disabled}
        return btn


# ── Advanced Menu Items ──────────────────────────────────────────────────────


class MenuGroup(Component):
    """A labelled group of menu items within a :class:`DropdownMenu` or context menu."""

    style = "menu-group"

    def __init__(
        self,
        *items: Component,
        label: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            *items,
            role="group",
            aria_label=label,
            **kwargs,
        )


class MenuCheckboxItem(Component):
    """A toggle-able menu item with a checkbox indicator."""

    style = "menu-checkbox-item"

    def __init__(
        self,
        *children: Any,
        checked: bool = False,
        on_select: EventHandler | None = None,
        disabled: bool = False,
        shortcut: str | None = None,
        **kwargs: Any,
    ) -> None:
        attrs: dict[str, Any] = {
            "role": "menuitemcheckbox",
            "aria_checked": "true" if checked else "false",
            "tabindex": "-1",
            "type": "button",
        }
        if disabled:
            attrs["disabled"] = True
            attrs["aria_disabled"] = "true"
        if on_select is not None and not disabled:
            attrs["data_vd_event_click"] = bind_event(on_select)
        super().__init__(**attrs, **kwargs)
        self.props = {"checked": checked}
        content: list[Any] = [
            _MenuCheckboxIndicator(checked),
            _MenuItemLabel(*children),
        ]
        if shortcut:
            content.append(_MenuShortcut(shortcut))
        self.children = tuple(content)


class _MenuCheckboxIndicator(Component):
    tag = "span"
    style = "menu-checkbox-indicator"
    auto_id = False

    def __init__(self, checked: bool) -> None:
        super().__init__(aria_hidden="true")
        self.props = {"checked": checked}


class MenuRadioItem(Component):
    """A mutually-exclusive menu item with a radio indicator."""

    style = "menu-radio-item"

    def __init__(
        self,
        *children: Any,
        value: str,
        checked: bool = False,
        on_select: EventHandler | None = None,
        disabled: bool = False,
        shortcut: str | None = None,
        **kwargs: Any,
    ) -> None:
        attrs: dict[str, Any] = {
            "role": "menuitemradio",
            "aria_checked": "true" if checked else "false",
            "tabindex": "-1",
            "type": "button",
            "data_vd_radio_value": value,
        }
        if disabled:
            attrs["disabled"] = True
            attrs["aria_disabled"] = "true"
        if on_select is not None and not disabled:
            attrs["data_vd_event_click"] = bind_event(on_select)
        super().__init__(**attrs, **kwargs)
        self.props = {"checked": checked, "value": value}
        content: list[Any] = [
            _MenuRadioIndicator(checked),
            _MenuItemLabel(*children),
        ]
        if shortcut:
            content.append(_MenuShortcut(shortcut))
        self.children = tuple(content)


class _MenuRadioIndicator(Component):
    tag = "span"
    style = "menu-radio-indicator"
    auto_id = False

    def __init__(self, checked: bool) -> None:
        super().__init__(aria_hidden="true")
        self.props = {"checked": checked}


class SubMenu(Component):
    """A nested submenu that opens on hover or arrow key."""

    style = "sub-menu"

    def __init__(
        self,
        label: str,
        *items: Component,
        disabled: bool = False,
        **kwargs: Any,
    ) -> None:
        trigger_id = _control_id("submenu-trigger")
        menu_id = _control_id("submenu")
        trigger_attrs: dict[str, Any] = {
            "id": trigger_id,
            "type": "button",
            "role": "menuitem",
            "tabindex": "-1",
            "aria_haspopup": "menu",
            "aria_controls": menu_id,
            "aria_expanded": "false",
            "data_vd_submenu_trigger": menu_id,
        }
        if disabled:
            trigger_attrs["disabled"] = True
            trigger_attrs["aria_disabled"] = "true"

        trigger = _SubMenuTrigger(
            _MenuItemLabel(label),
            _SubMenuArrow(),
            **trigger_attrs,
        )
        panel = _SubMenuPanel(
            *items,
            id=menu_id,
            role="menu",
            aria_label=label,
            data_vd_submenu=True,
            hidden=True,
        )
        super().__init__(trigger, panel, **kwargs)


class _SubMenuTrigger(Component):
    tag = "button"
    style = "sub-menu.trigger"
    auto_id = False


class _SubMenuArrow(Component):
    tag = "span"
    style = "sub-menu.arrow"
    auto_id = False

    def __init__(self) -> None:
        super().__init__(aria_hidden="true")


class _SubMenuPanel(Component):
    style = "sub-menu.panel"
    auto_id = False


class _MenuItemLabel(Component):
    tag = "span"
    style = "menu-item.label"
    auto_id = False


class _MenuShortcut(Component):
    tag = "span"
    style = "menu-shortcut"
    auto_id = False


# ── ContextMenu ──────────────────────────────────────────────────────────────


class ContextMenu(Component):
    """Right-click context menu for desktop interactions.

    Example::

        ContextMenu(
            target=Card("Right-click me"),
            MenuItem("Copy", shortcut="Ctrl+C", on_select=copy),
            MenuItem("Paste", shortcut="Ctrl+V", on_select=paste),
            MenuSeparator(),
            MenuItem("Delete", destructive=True, on_select=delete),
        )
    """

    style = "context-menu-shell"

    def __init__(
        self,
        target: Component,
        *items: Component,
        label: str = "Actions",
        **kwargs: Any,
    ) -> None:
        if not items:
            raise ValueError("ContextMenu requires at least one item")
        super().__init__(**kwargs)
        menu_id = f"{self.id}-menu" if self.id else _control_id("ctx-menu")
        target_id = _ensure_id(target, "ctx-target")
        target.attrs["data_vd_context_menu"] = menu_id
        target.attrs["aria_haspopup"] = "menu"

        panel = _ContextMenuPanel(
            *items,
            id=menu_id,
            role="menu",
            aria_label=label,
            tabindex="-1",
            data_vd_context_menu_panel=True,
            data_vd_anchor=target_id,
            hidden=True,
        )
        self.children = (target, panel)


class _ContextMenuPanel(Component):
    style = "context-menu"
    auto_id = False


# ── CommandPalette ───────────────────────────────────────────────────────────


class CommandPalette(Component):
    """Full-screen command palette with search, groups, and keyboard navigation.

    Triggered by a keyboard shortcut (typically ⌘K or Ctrl+K). Supports
    grouped commands, search filtering, keyboard navigation, and shortcut hints.

    Example::

        CommandPalette(
            CommandGroup("Navigation",
                Command("Home", shortcut="G H", on_select=go_home),
                Command("Settings", shortcut="G S", on_select=go_settings),
            ),
            CommandGroup("Actions",
                Command("New project", shortcut="Ctrl+N", on_select=new_project),
                Command("New file", shortcut="Ctrl+Shift+N", on_select=new_file),
            ),
            placeholder="Type a command or search…",
            label="Command palette",
        )
    """

    style = "command-palette"

    def __init__(
        self,
        *groups: CommandGroup,
        placeholder: str = "Type a command or search…",
        label: str = "Command palette",
        empty_text: str = "No results found.",
        open: bool = False,
        **kwargs: Any,
    ) -> None:
        if not groups:
            raise ValueError("CommandPalette requires at least one CommandGroup")
        super().__init__(**kwargs)
        palette_id = f"{self.id}-panel" if self.id else _control_id("cmd-palette")
        input_id = f"{palette_id}-input"
        listbox_id = f"{palette_id}-listbox"

        search = _CommandSearch(
            Icon("search", class_="vd-cmd-search-icon"),
            _CommandInput(
                id=input_id,
                type="text",
                placeholder=placeholder,
                role="combobox",
                aria_label=label,
                aria_autocomplete="list",
                aria_controls=listbox_id,
                aria_expanded="true",
                autocomplete="off",
                data_vd_cmd_input=True,
            ),
            _CommandKbd("ESC"),
        )

        results = _CommandResults(
            *groups,
            _CommandEmpty(empty_text, data_vd_cmd_empty=True, hidden=True),
            id=listbox_id,
            role="listbox",
            aria_label="Commands",
            data_vd_cmd_results=True,
        )

        panel = _CommandPanel(
            search,
            results,
            id=palette_id,
            role="dialog",
            aria_modal="true",
            aria_label=label,
            tabindex="-1",
            data_vd_layer=True,
            data_vd_cmd_palette=True,
            open=open,
        )
        self.children = (panel,)


class _CommandPanel(Component):
    tag = "dialog"
    style = "command-palette.panel"
    auto_id = False


class _CommandSearch(Component):
    style = "command-palette.search"
    auto_id = False


class _CommandInput(Component):
    tag = "input"
    style = "command-palette.input"
    auto_id = False


class _CommandKbd(Component):
    tag = "kbd"
    style = "command-palette.kbd"
    auto_id = False


class _CommandResults(Component):
    style = "command-palette.results"
    auto_id = False


class _CommandEmpty(Component):
    style = "command-palette.empty"
    auto_id = False


class CommandGroup(Component):
    """A labelled group of commands within a :class:`CommandPalette`."""

    style = "command-group"

    def __init__(
        self,
        label: str,
        *commands: Command,
        **kwargs: Any,
    ) -> None:
        if not commands:
            raise ValueError("CommandGroup requires at least one Command")
        heading = _CommandGroupHeading(label)
        items = tuple(
            cmd.render_command(index) for index, cmd in enumerate(commands)
        )
        super().__init__(heading, *items, role="group", aria_label=label, **kwargs)


class _CommandGroupHeading(Component):
    tag = "h3"
    style = "command-group.heading"
    auto_id = False


class Command(Component):
    """An individual command inside a :class:`CommandPalette`."""

    def __init__(
        self,
        *children: Any,
        shortcut: str | None = None,
        icon: Component | None = None,
        description: str | None = None,
        on_select: EventHandler | None = None,
        disabled: bool = False,
        **kwargs: Any,
    ) -> None:
        self._children_raw = children
        self._shortcut = shortcut
        self._icon = icon
        self._description = description
        self._on_select = on_select
        self._disabled = disabled
        super().__init__(**kwargs)

    def render_command(self, index: int) -> Component:
        attrs: dict[str, Any] = {
            "role": "option",
            "aria_selected": "false",
            "tabindex": "-1",
            "type": "button",
            "data_vd_cmd_item": True,
            "data_vd_cmd_index": str(index),
        }
        if self._disabled:
            attrs["disabled"] = True
            attrs["aria_disabled"] = "true"
        if self._on_select is not None and not self._disabled:
            attrs["data_vd_event_click"] = bind_event(self._on_select)

        content: list[Any] = []
        if self._icon is not None:
            content.append(_CommandIcon(self._icon))
        copy: list[Any] = list(self._children_raw)
        if self._description:
            copy.append(
                Component(self._description, class_="vd-cmd-description")
            )
        content.append(_CommandCopy(*copy))
        if self._shortcut:
            content.append(_CommandShortcut(self._shortcut))

        item = _CommandItem(*content, **attrs)
        item.props = {"disabled": self._disabled}
        return item


class _CommandItem(Component):
    tag = "button"
    style = "command-item"
    auto_id = False


class _CommandIcon(Component):
    tag = "span"
    style = "command-item.icon"
    auto_id = False


class _CommandCopy(Component):
    tag = "span"
    style = "command-item.copy"
    auto_id = False


class _CommandShortcut(Component):
    tag = "span"
    style = "command-item.shortcut"
    auto_id = False


# ── Portal / Layer Manager ──────────────────────────────────────────────────


class Portal(Component):
    """Renders children into a portal container at the document body level.

    Overlays (dialogs, menus, tooltips, command palettes) should render through
    a portal so they are not clipped by overflow-hidden ancestors.

    The portal container uses a shared layer stack managed by ``data-vd-layer``
    attributes. The client runtime coordinates z-index ordering automatically.
    """

    style = "portal"

    def __init__(
        self,
        *children: Any,
        name: str | None = None,
        **kwargs: Any,
    ) -> None:
        portal_name = name or f"vd-portal-{uuid4().hex[:8]}"
        super().__init__(
            *children,
            data_vd_portal=portal_name,
            data_vd_layer=True,
            **kwargs,
        )


class LayerManager(Component):
    """Manages the z-index stack for nested overlays.

    Renders a container that the client runtime uses to coordinate overlay
    ordering. Each child with ``data-vd-layer`` receives an automatic z-index
    based on its insertion order.
    """

    style = "layer-manager"

    def __init__(
        self,
        *children: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            *children,
            data_vd_layer_manager=True,
            **kwargs,
        )


# ── DismissLayer ─────────────────────────────────────────────────────────────


class DismissLayer(Component):
    """Invisible backdrop that closes its parent overlay on click or touch.

    Used by drawers, modals, context menus, and other dismissible overlays.
    """

    style = "dismiss-layer"

    def __init__(
        self,
        *,
        target_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        attrs: dict[str, Any] = {
            "aria_hidden": "true",
            "data_vd_dismiss_layer": True,
        }
        if target_id:
            attrs["data_vd_dismiss_target"] = target_id
        super().__init__(**attrs, **kwargs)
