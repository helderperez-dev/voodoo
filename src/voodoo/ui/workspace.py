"""Priority 4 — Desktop Workspaces.

Resizable panels, scroll area, tree view, toolbar, menubar, dock,
master-detail layout, and keyboard shortcut registry.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any
from uuid import uuid4

from voodoo.ui.component import Component
from voodoo.ui.events import bind_event
from voodoo.ui.library import Icon, Text

EventHandler = Callable[..., Any] | str


def _ws_id(prefix: str) -> str:
    return f"vd-{prefix}-{uuid4().hex[:8]}"


# ── ResizablePanels ──────────────────────────────────────────────────────────


class ResizablePanels(Component):
    """Resizable split panels with drag handles.

    Supports 2- or 3-panel layouts (vertical or horizontal split)
    with configurable min/max sizes and persistence.

    Example::

        ResizablePanels(
            Panel("sidebar", min_size=200, max_size=400, default_size=280, children=[sidebar]),
            Panel("main", min_size=300, children=[main_content]),
            orientation="horizontal",
            persist_id="main-layout",
        )
    """

    style = "resizable-panels"

    def __init__(
        self,
        *panels: Panel,
        orientation: str = "horizontal",
        persist_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        if len(panels) < 2:
            raise ValueError("ResizablePanels requires at least 2 Panel children")
        if len(panels) > 3:
            raise ValueError("ResizablePanels supports at most 3 panels")
        if orientation not in {"horizontal", "vertical"}:
            raise ValueError("ResizablePanels orientation must be horizontal or vertical")

        rendered: list[Any] = []
        for i, panel in enumerate(panels):
            rendered.append(panel.render_panel(i))
            if i < len(panels) - 1:
                rendered.append(
                    _ResizeHandle(
                        orientation,
                        index=i,
                        data_vd_resize_handle=str(i),
                        data_vd_orientation=orientation,
                        aria_orientation=orientation,
                        aria_valuenow=str(panel.default_size or 50),
                        aria_label=f"Resize panels {i + 1} and {i + 2}",
                        role="separator",
                        tabindex="0",
                    )
                )

        attrs: dict[str, Any] = {
            "data_vd_resizable": True,
            "data_vd_orientation": orientation,
        }
        if persist_id:
            attrs["data_vd_persist"] = persist_id

        super().__init__(*rendered, **attrs, **kwargs)
        self.props = {"orientation": orientation, "panel_count": len(panels)}


class Panel:
    """A single panel inside :class:`ResizablePanels`."""

    def __init__(
        self,
        name: str,
        *,
        children: Sequence[Component | Any] = (),
        min_size: int | None = None,
        max_size: int | None = None,
        default_size: int | None = None,
        collapsible: bool = False,
        collapsed: bool = False,
        snap_points: tuple[int, ...] | None = None,
    ) -> None:
        self.name = name
        self.children = list(children)
        self.min_size = min_size
        self.max_size = max_size
        self.default_size = default_size
        self.collapsible = collapsible
        self.collapsed = collapsed
        self.snap_points = snap_points

    def render_panel(self, index: int) -> Component:
        attrs: dict[str, Any] = {
            "data_vd_panel": True,
            "data_vd_panel_name": self.name,
            "data_vd_panel_index": str(index),
        }
        if self.min_size is not None:
            attrs["data_vd_min_size"] = str(self.min_size)
        if self.max_size is not None:
            attrs["data_vd_max_size"] = str(self.max_size)
        if self.default_size is not None:
            attrs["data_vd_default_size"] = str(self.default_size)
        if self.collapsible:
            attrs["data_vd_collapsible"] = True
        if self.collapsed:
            attrs["data_vd_collapsed"] = True
            attrs["aria_hidden"] = "true"
        if self.snap_points:
            attrs["data_vd_snap_points"] = ",".join(str(s) for s in self.snap_points)
        return _PanelItem(*self.children, **attrs)


class _PanelItem(Component):
    style = "resizable-panels.panel"
    auto_id = False


class _ResizeHandle(Component):
    tag = "div"
    style = "resizable-panels.handle"
    auto_id = False


# ── ScrollArea ───────────────────────────────────────────────────────────────


class ScrollArea(Component):
    """Custom-styled scrollable container with scrollbar theming.

    Wraps content in a container that the CSS adapter styles with
    custom scrollbars. Supports horizontal, vertical, or both axes.

    Example::

        ScrollArea(
            *long_list_of_items,
            orientation="vertical",
            height="400px",
        )
    """

    style = "scroll-area"

    def __init__(
        self,
        *children: Any,
        orientation: str = "vertical",
        height: str | None = None,
        width: str | None = None,
        max_height: str | None = None,
        max_width: str | None = None,
        **kwargs: Any,
    ) -> None:
        if orientation not in {"vertical", "horizontal", "both"}:
            raise ValueError("ScrollArea orientation must be vertical, horizontal, or both")

        css: dict[str, str] = {}
        if height:
            css["height"] = height
        if width:
            css["width"] = width
        if max_height:
            css["max-height"] = max_height
        if max_width:
            css["max-width"] = max_width

        overflow = {"vertical": "auto hidden", "horizontal": "hidden auto", "both": "auto"}

        super().__init__(
            *children,
            data_vd_scroll_area=True,
            data_vd_scroll_axis=orientation,
            css={
                **css,
                "overflow": overflow[orientation],
                "overscroll-behavior": "contain",
            },
            **kwargs,
        )
        self.props = {"orientation": orientation}


# ── TreeView ─────────────────────────────────────────────────────────────────


class TreeView(Component):
    """Hierarchical tree view with expand/collapse and keyboard navigation.

    Example::

        TreeView(
            TreeNode("src",
                TreeNode("components", children=[
                    TreeNode("Button.tsx"),
                    TreeNode("Card.tsx"),
                ]),
                TreeNode("utils", children=[
                    TreeNode("helpers.ts"),
                    TreeNode("format.ts"),
                ]),
                TreeNode("index.ts"),
            ),
            label="Project files",
            on_select=show_file,
        )
    """

    style = "tree-view"

    def __init__(
        self,
        *nodes: TreeNode,
        label: str = "Tree",
        on_select: EventHandler | None = None,
        on_expand: EventHandler | None = None,
        on_collapse: EventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        if not nodes:
            raise ValueError("TreeView requires at least one TreeNode")

        select_binding = bind_event(on_select) if on_select else None
        expand_binding = bind_event(on_expand) if on_expand else None
        collapse_binding = bind_event(on_collapse) if on_collapse else None

        rendered = tuple(
            node.render_node(0, select_binding, expand_binding, collapse_binding)
            for node in nodes
        )

        super().__init__(
            _TreeList(
                *rendered,
                role="tree",
                aria_label=label,
            ),
            data_vd_tree_view=True,
            **kwargs,
        )


class TreeNode:
    """A node in a :class:`TreeView`."""

    def __init__(
        self,
        label: str,
        *,
        children: Sequence[TreeNode] = (),
        icon: Component | None = None,
        expanded: bool = False,
        selected: bool = False,
        disabled: bool = False,
    ) -> None:
        self.label = label
        self.children = list(children)
        self.icon = icon
        self.expanded = expanded
        self.selected = selected
        self.disabled = disabled

    def render_node(
        self,
        depth: int,
        select_binding: str | None,
        expand_binding: str | None,
        collapse_binding: str | None,
    ) -> Component:
        node_id = _ws_id("tree-node")

        # Build label content
        label_children: list[Any] = []
        if self.children:
            toggle = _TreeToggle(
                Icon("chevron-right", aria_hidden="true") if not self.expanded else Icon("chevron-down", aria_hidden="true"),
                type="button",
                aria_expanded="true" if self.expanded else "false",
                data_vd_event_click=expand_binding if self.expanded else collapse_binding,
                data_vd_tree_toggle=True,
            )
            label_children.append(toggle)
        else:
            label_children.append(_TreeSpacer())

        if self.icon:
            label_children.append(_TreeIcon(self.icon))
        label_children.append(Text(self.label))

        row_attrs: dict[str, Any] = {
            "role": "treeitem",
            "aria_selected": "true" if self.selected else "false",
            "aria_disabled": "true" if self.disabled else None,
            "aria_level": str(depth + 1),
            "data_vd_tree_node=True": True,
            "data_vd_depth": str(depth),
        }
        if select_binding and not self.disabled:
            row_attrs["data_vd_event_click"] = select_binding

        children_list: list[Any] = [
            _TreeRow(*label_children, **row_attrs),
        ]

        if self.children:
            rendered_children = tuple(
                child.render_node(depth + 1, select_binding, expand_binding, collapse_binding)
                for child in self.children
            )
            children_list.append(
                _TreeGroup(
                    *rendered_children,
                    role="group",
                    hidden=not self.expanded,
                )
            )

        return _TreeNodeWrapper(
            *children_list,
            id=node_id,
        )


class _TreeList(Component):
    tag = "ul"
    style = "tree-view.list"
    auto_id = False


class _TreeNodeWrapper(Component):
    tag = "li"
    style = "tree-view.node"
    auto_id = False


class _TreeRow(Component):
    style = "tree-view.row"
    auto_id = False


class _TreeToggle(Component):
    tag = "button"
    style = "tree-view.toggle"
    auto_id = False


class _TreeSpacer(Component):
    tag = "span"
    style = "tree-view.spacer"
    auto_id = False

    def __init__(self) -> None:
        super().__init__(aria_hidden="true")


class _TreeIcon(Component):
    tag = "span"
    style = "tree-view.icon"
    auto_id = False


class _TreeGroup(Component):
    tag = "ul"
    style = "tree-view.group"
    auto_id = False


# ── Toolbar ──────────────────────────────────────────────────────────────────


class Toolbar(Component):
    """Horizontal or vertical toolbar with grouped controls.

    Example::

        Toolbar(
            ToolbarGroup(
                ToolbarButton("Bold", icon=Icon("bold")),
                ToolbarButton("Italic", icon=Icon("italic")),
                ToolbarButton("Underline", icon=Icon("underline")),
            ),
            ToolbarSeparator(),
            ToolbarGroup(
                ToolbarButton("Align left", icon=Icon("align-left")),
                ToolbarButton("Align center", icon=Icon("align-center")),
                ToolbarButton("Align right", icon=Icon("align-right")),
            ),
            label="Text formatting",
        )
    """

    style = "toolbar"

    def __init__(
        self,
        *children: Any,
        orientation: str = "horizontal",
        label: str = "Toolbar",
        **kwargs: Any,
    ) -> None:
        if orientation not in {"horizontal", "vertical"}:
            raise ValueError("Toolbar orientation must be horizontal or vertical")

        super().__init__(
            *children,
            role="toolbar",
            aria_label=label,
            aria_orientation=orientation,
            data_vd_toolbar=True,
            **kwargs,
        )
        self.props = {"orientation": orientation}


class ToolbarGroup(Component):
    """A logical group of controls within a :class:`Toolbar`."""

    style = "toolbar.group"

    def __init__(self, *children: Any, label: str | None = None, **kwargs: Any) -> None:
        attrs: dict[str, Any] = {"role": "group"}
        if label:
            attrs["aria_label"] = label
        super().__init__(*children, **attrs, **kwargs)


class ToolbarButton(Component):
    """A toggle or action button inside a :class:`Toolbar`."""

    tag = "button"
    style = "toolbar.button"

    def __init__(
        self,
        *children: Any,
        icon: Component | None = None,
        label: str | None = None,
        pressed: bool | None = None,
        disabled: bool = False,
        on_click: EventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        content: list[Any] = []
        if icon:
            content.append(_ToolbarButtonIcon(icon))
        if children:
            content.extend(children)

        attrs: dict[str, Any] = {
            "type": "button",
            "aria_label": label,
        }
        if pressed is not None:
            attrs["aria_pressed"] = "true" if pressed else "false"
        if disabled:
            attrs["disabled"] = True
        if on_click is not None and not disabled:
            attrs["data_vd_event_click"] = bind_event(on_click)

        super().__init__(*content, **attrs, **kwargs)
        self.props = {"pressed": pressed, "disabled": disabled}


class _ToolbarButtonIcon(Component):
    tag = "span"
    style = "toolbar.button-icon"
    auto_id = False


class ToolbarSeparator(Component):
    """Visual separator between toolbar groups."""

    style = "toolbar.separator"

    def __init__(self) -> None:
        super().__init__(role="separator", aria_orientation="vertical")


# ── Menubar ──────────────────────────────────────────────────────────────────


class Menubar(Component):
    """Desktop-style menubar (File, Edit, View, etc.).

    Example::

        Menubar(
            MenubarMenu("File",
                MenubarItem("New", shortcut="⌘N", on_select=new_file),
                MenubarItem("Open…", shortcut="⌘O", on_select=open_file),
                MenubarSeparator(),
                MenubarItem("Save", shortcut="⌘S", on_select=save_file),
            ),
            MenubarMenu("Edit",
                MenubarItem("Undo", shortcut="⌘Z", on_select=undo),
                MenubarItem("Redo", shortcut="⇧⌘Z", on_select=redo),
                MenubarSeparator(),
                MenubarItem("Cut", shortcut="⌘X"),
                MenubarItem("Copy", shortcut="⌘C"),
                MenubarItem("Paste", shortcut="⌘V"),
            ),
            label="Application menu",
        )
    """

    style = "menubar"

    def __init__(
        self,
        *menus: MenubarMenu,
        label: str = "Application menu",
        **kwargs: Any,
    ) -> None:
        if not menus:
            raise ValueError("Menubar requires at least one MenubarMenu")

        rendered = tuple(
            _MenubarItem(m.render_menu()) for m in menus
        )
        super().__init__(
            _MenubarList(*rendered, role="menubar", aria_label=label),
            data_vd_menubar=True,
            **kwargs,
        )


class _MenubarList(Component):
    tag = "ul"
    style = "menubar.list"
    auto_id = False


class _MenubarItem(Component):
    tag = "li"
    style = "menubar.item"
    auto_id = False


class MenubarMenu:
    """A top-level menu in a :class:`Menubar`."""

    def __init__(
        self,
        label: str,
        *items: Component,
        disabled: bool = False,
    ) -> None:
        self.label = label
        self.items = list(items)
        self.disabled = disabled

    def render_menu(self) -> Component:
        trigger_id = _ws_id("menubar-trigger")
        content_id = _ws_id("menubar-content")

        trigger = _MenubarTrigger(
            Text(self.label),
            id=trigger_id,
            type="button",
            aria_haspopup="menu",
            aria_controls=content_id,
            aria_expanded="false",
            data_vd_menubar_trigger=content_id,
            disabled=self.disabled,
            role="menuitem",
        )

        menu = _MenubarDropdown(
            *self.items,
            id=content_id,
            role="menu",
            hidden=True,
            data_vd_menubar_dropdown=True,
            aria_labelledby=trigger_id,
        )
        return _MenubarMenu(trigger, menu)


class _MenubarMenu(Component):
    style = "menubar.menu"
    auto_id = False


class _MenubarTrigger(Component):
    tag = "button"
    style = "menubar.trigger"
    auto_id = False


class _MenubarDropdown(Component):
    style = "menubar.dropdown"
    auto_id = False


class MenubarItem(Component):
    """An item inside a :class:`MenubarMenu` dropdown."""

    style = "menubar.dropdown-item"

    def __init__(
        self,
        *children: Any,
        shortcut: str | None = None,
        disabled: bool = False,
        on_select: EventHandler | None = None,
        **kwargs: Any,
    ) -> None:
        content: list[Any] = list(children)
        if shortcut:
            content.append(
                Component(shortcut, class_="vd-menubar-shortcut", aria_label=shortcut)
            )

        attrs: dict[str, Any] = {
            "type": "button",
            "role": "menuitem",
        }
        if disabled:
            attrs["disabled"] = True
            attrs["aria_disabled"] = "true"
        if on_select is not None and not disabled:
            attrs["data_vd_event_click"] = bind_event(on_select)

        super().__init__(*content, **attrs, **kwargs)


class MenubarSeparator(Component):
    """Visual separator inside a menubar dropdown."""

    tag = "hr"
    style = "menubar.separator"
    auto_id = False

    def __init__(self) -> None:
        super().__init__(role="separator")


# ── Dock ─────────────────────────────────────────────────────────────────────


class Dock(Component):
    """macOS-style application dock with magnification effect data.

    Renders items with size/position data attributes for the client
    runtime to apply a fisheye/magnification effect on hover.

    Example::

        Dock(
            DockItem(Icon("home"), label="Home", active=True),
            DockItem(Icon("search"), label="Search"),
            DockItem(Icon("settings"), label="Settings"),
            DockItem(Icon("user"), label="Profile"),
            position="bottom",
            label="Application dock",
        )
    """

    style = "dock"

    def __init__(
        self,
        *items: DockItem,
        position: str = "bottom",
        label: str = "Dock",
        magnification: float = 1.5,
        **kwargs: Any,
    ) -> None:
        if position not in {"bottom", "top", "left", "right"}:
            raise ValueError("Dock position must be bottom, top, left, or right")
        if magnification < 1.0:
            raise ValueError("Dock magnification must be >= 1.0")

        rendered = tuple(
            _DockSlot(item.render_item(i)) for i, item in enumerate(items)
        )

        super().__init__(
            _DockList(*rendered, role="list", aria_label=label),
            data_vd_dock=True,
            data_vd_dock_position=position,
            data_vd_magnification=str(magnification),
            **kwargs,
        )
        self.props = {"position": position, "magnification": magnification}


class DockItem:
    """An item in a :class:`Dock`."""

    def __init__(
        self,
        icon: Component,
        *,
        label: str,
        active: bool = False,
        badge: int | None = None,
        on_click: EventHandler | None = None,
        disabled: bool = False,
    ) -> None:
        self.icon = icon
        self.label = label
        self.active = active
        self.badge = badge
        self.on_click = on_click
        self.disabled = disabled

    def render_item(self, index: int) -> Component:
        attrs: dict[str, Any] = {
            "type": "button",
            "aria_label": self.label,
            "aria_current": "true" if self.active else None,
            "data_vd_dock_index": str(index),
            "data_vd_dock_active": self.active,
        }
        if self.on_click and not self.disabled:
            attrs["data_vd_event_click"] = bind_event(self.on_click)
        if self.disabled:
            attrs["disabled"] = True

        children: list[Any] = [
            _DockIcon(self.icon),
            _DockTooltip(self.label),
        ]
        if self.badge is not None:
            children.append(_DockBadge(str(self.badge), aria_label=f"{self.badge} notifications"))

        return _DockButton(*children, **attrs)


class _DockSlot(Component):
    tag = "li"
    style = "dock.slot"
    auto_id = False


class _DockList(Component):
    tag = "ul"
    style = "dock.list"
    auto_id = False


class _DockButton(Component):
    tag = "button"
    style = "dock.button"
    auto_id = False


class _DockIcon(Component):
    tag = "span"
    style = "dock.icon"
    auto_id = False


class _DockTooltip(Component):
    tag = "span"
    style = "dock.tooltip"
    auto_id = False


class _DockBadge(Component):
    tag = "span"
    style = "dock.badge"
    auto_id = False


# ── MasterDetail ─────────────────────────────────────────────────────────────


class MasterDetail(Component):
    """Master-detail layout that collapses to a list on mobile.

    The master pane shows a list of items; selecting one shows the
    detail pane. On narrow viewports, only one pane is visible at a time.

    Example::

        MasterDetail(
            MasterList(
                MasterItem("Project A", selected=True, summary="3 tasks"),
                MasterItem("Project B", summary="7 tasks"),
                MasterItem("Project C", summary="1 task"),
            ),
            DetailPane(
                Heading("Project A", level=2),
                Text("Project details go here."),
            ),
            label="Projects",
        )
    """

    style = "master-detail"

    def __init__(
        self,
        master: MasterList,
        detail: DetailPane,
        *,
        label: str = "Master-detail",
        master_width: str = "320px",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            _MasterPane(master, style={"width": master_width}),
            _DetailSeparator(role="separator", aria_orientation="vertical"),
            detail,
            aria_label=label,
            data_vd_master_detail=True,
            **kwargs,
        )


class _MasterPane(Component):
    style = "master-detail.master"
    auto_id = False


class _DetailSeparator(Component):
    tag = "hr"
    style = "master-detail.separator"
    auto_id = False


class MasterList(Component):
    """The list pane in a :class:`MasterDetail`."""

    style = "master-detail.list"

    def __init__(self, *items: MasterItem, **kwargs: Any) -> None:
        rendered = tuple(
            _MasterListItem(item.render_item()) for item in items
        )
        super().__init__(*rendered, role="listbox", **kwargs)


class _MasterListItem(Component):
    tag = "li"
    style = "master-detail.list-item"
    auto_id = False


class MasterItem:
    """An item in the master list of a :class:`MasterDetail`."""

    def __init__(
        self,
        label: str,
        *,
        summary: str | None = None,
        icon: Component | None = None,
        selected: bool = False,
        disabled: bool = False,
        on_select: EventHandler | None = None,
    ) -> None:
        self.label = label
        self.summary = summary
        self.icon = icon
        self.selected = selected
        self.disabled = disabled
        self.on_select = on_select

    def render_item(self) -> Component:
        content: list[Any] = []
        if self.icon:
            content.append(_MasterItemIcon(self.icon))
        copy: list[Any] = [
            _MasterItemLabel(self.label),
        ]
        if self.summary:
            copy.append(_MasterItemSummary(self.summary))
        content.append(_MasterItemCopy(*copy))

        attrs: dict[str, Any] = {
            "type": "button",
            "role": "option",
            "aria_selected": "true" if self.selected else "false",
            "aria_disabled": "true" if self.disabled else None,
            "tabindex": "0" if self.selected else "-1",
        }
        if self.on_select and not self.disabled:
            attrs["data_vd_event_click"] = bind_event(self.on_select)

        return _MasterItemButton(*content, **attrs)


class _MasterItemButton(Component):
    tag = "button"
    style = "master-detail.item-button"
    auto_id = False


class _MasterItemIcon(Component):
    tag = "span"
    style = "master-detail.item-icon"
    auto_id = False


class _MasterItemCopy(Component):
    tag = "span"
    style = "master-detail.item-copy"
    auto_id = False


class _MasterItemLabel(Component):
    tag = "span"
    style = "master-detail.item-label"
    auto_id = False


class _MasterItemSummary(Component):
    tag = "span"
    style = "master-detail.item-summary"
    auto_id = False


class DetailPane(Component):
    """The detail/content pane in a :class:`MasterDetail`."""

    style = "master-detail.detail"

    def __init__(self, *children: Any, **kwargs: Any) -> None:
        super().__init__(*children, role="region", aria_label="Detail", **kwargs)


# ── KeyboardShortcutRegistry ────────────────────────────────────────────────


class KeyboardShortcutRegistry(Component):
    """Declares keyboard shortcuts and renders an accessible shortcut reference.

    Renders ``<kbd>`` elements with the appropriate ``data-vd-shortcut``
    attributes for the client runtime to bind. Also serves as a visual
    cheat-sheet that can be shown in a command palette or help dialog.

    Example::

        KeyboardShortcutRegistry(
            KeyBinding("save", "⌘S", description="Save document"),
            KeyBinding("undo", "⌘Z", description="Undo last action"),
            KeyBinding("redo", "⇧⌘Z", description="Redo last action"),
            KeyBinding("command_palette", "⌘K", description="Open command palette"),
            label="Keyboard shortcuts",
        )
    """

    style = "keyboard-shortcuts"

    def __init__(
        self,
        *bindings: KeyBinding,
        label: str = "Keyboard shortcuts",
        visible: bool = False,
        **kwargs: Any,
    ) -> None:
        rendered = tuple(
            _ShortcutRow(b.render_binding()) for b in bindings
        )

        attrs: dict[str, Any] = {
            "data_vd_shortcut_registry": True,
            "hidden": not visible,
        }

        super().__init__(
            _ShortcutHeading(label),
            _ShortcutList(*rendered, role="list"),
            **attrs,
            **kwargs,
        )
        self.props = {"visible": visible}


class _ShortcutHeading(Component):
    tag = "h2"
    style = "keyboard-shortcuts.heading"
    auto_id = False


class _ShortcutList(Component):
    tag = "ul"
    style = "keyboard-shortcuts.list"
    auto_id = False


class _ShortcutRow(Component):
    tag = "li"
    style = "keyboard-shortcuts.row"
    auto_id = False


class KeyBinding:
    """A keyboard shortcut declaration for :class:`KeyboardShortcutRegistry`."""

    def __init__(
        self,
        action: str,
        keys: str,
        *,
        description: str | None = None,
        disabled: bool = False,
        scope: str = "global",
    ) -> None:
        self.action = action
        self.keys = keys
        self.description = description
        self.disabled = disabled
        self.scope = scope

    def render_binding(self) -> Component:
        content: list[Any] = [
            _ShortcutKeys(self.keys, data_vd_shortcut_keys=self.keys),
        ]
        if self.description:
            content.append(_ShortcutDescription(self.description))

        return _ShortcutBinding(
            *content,
            data_vd_shortcut_action=self.action,
            data_vd_shortcut_scope=self.scope,
            aria_disabled="true" if self.disabled else None,
        )


class _ShortcutBinding(Component):
    style = "keyboard-shortcuts.binding"
    auto_id = False


class _ShortcutKeys(Component):
    tag = "kbd"
    style = "keyboard-shortcuts.keys"
    auto_id = False


class _ShortcutDescription(Component):
    tag = "span"
    style = "keyboard-shortcuts.description"
    auto_id = False
