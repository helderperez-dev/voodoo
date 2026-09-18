"""Tests for Priority 4: Desktop Workspace components."""

import pytest

from voodoo.adapters import TailwindAdapter, VoodooCSSAdapter
from voodoo.ui import set_style_adapter
from voodoo.ui.styles import current_adapter
from voodoo.ui.workspace import (
    DetailPane,
    Dock,
    DockItem,
    KeyBinding,
    KeyboardShortcutRegistry,
    MasterDetail,
    MasterItem,
    MasterList,
    Menubar,
    MenubarItem,
    MenubarMenu,
    MenubarSeparator,
    Panel,
    ResizablePanels,
    ScrollArea,
    Toolbar,
    ToolbarButton,
    ToolbarGroup,
    ToolbarSeparator,
    TreeNode,
    TreeView,
)


@pytest.fixture(params=[VoodooCSSAdapter, TailwindAdapter])
def adapter(request):
    original = current_adapter()
    set_style_adapter(request.param())
    yield request.param
    set_style_adapter(original)


# ── Resizable Panels ────────────────────────────────────────────────────────


def test_resizable_panels_renders(adapter):
    html = ResizablePanels(
        Panel("left", children=["Left content"]),
        Panel("right", children=["Right content"]),
    ).render()
    assert "Left content" in html
    assert "Right content" in html
    assert "data-vd-resizable" in html


def test_resizable_panels_three(adapter):
    html = ResizablePanels(
        Panel("a", children=["A"]),
        Panel("b", children=["B"]),
        Panel("c", children=["C"]),
    ).render()
    assert "A" in html
    assert "B" in html
    assert "C" in html


def test_resizable_panels_vertical(adapter):
    html = ResizablePanels(
        Panel("top", children=["Top"]),
        Panel("bottom", children=["Bottom"]),
        orientation="vertical",
    ).render()
    assert 'data-vd-orientation="vertical"' in html


def test_panel_collapsible(adapter):
    html = Panel("hidden", children=["Hidden"], collapsible=True).render_panel(0).render()
    assert "Hidden" in html


# ── Scroll Area ─────────────────────────────────────────────────────────────


def test_scroll_area_renders(adapter):
    html = ScrollArea("Scrollable content").render()
    assert "Scrollable content" in html
    assert "data-vd-scroll" in html


def test_scroll_area_vertical(adapter):
    html = ScrollArea("Content", orientation="vertical").render()
    assert "Content" in html


# ── Tree View ───────────────────────────────────────────────────────────────


def test_tree_view_renders(adapter):
    html = TreeView(
        TreeNode("Documents", children=[
            TreeNode("Report.pdf"),
            TreeNode("Data.csv"),
        ]),
        TreeNode("Images", children=[
            TreeNode("Photo.jpg"),
        ]),
    ).render()
    assert 'role="tree"' in html
    assert "Documents" in html
    assert "Report.pdf" in html
    assert "Images" in html


def test_tree_node_selected(adapter):
    html = TreeView(
        TreeNode("Selected", selected=True),
    ).render()
    assert 'aria-selected="true"' in html


# ── Toolbar ─────────────────────────────────────────────────────────────────


def test_toolbar_renders(adapter):
    html = Toolbar(
        ToolbarGroup(
            ToolbarButton("Bold"),
            ToolbarButton("Italic"),
        ),
        ToolbarSeparator(),
        ToolbarGroup(
            ToolbarButton("Align"),
        ),
    ).render()
    assert 'role="toolbar"' in html
    assert "Bold" in html
    assert "Italic" in html


def test_toolbar_vertical(adapter):
    html = Toolbar(
        ToolbarButton("A"),
        orientation="vertical",
    ).render()
    assert 'aria-orientation="vertical"' in html


def test_toolbar_button_pressed(adapter):
    html = ToolbarButton("Bold", pressed=True).render()
    assert 'aria-pressed="true"' in html


def test_toolbar_separator(adapter):
    html = ToolbarSeparator().render()
    assert 'role="separator"' in html


# ── Menubar ─────────────────────────────────────────────────────────────────


def test_menubar_renders(adapter):
    html = Menubar(
        MenubarMenu("File",
            MenubarItem("New"),
            MenubarItem("Open"),
            MenubarSeparator(),
            MenubarItem("Exit"),
        ),
        MenubarMenu("Edit",
            MenubarItem("Undo"),
            MenubarItem("Redo"),
        ),
    ).render()
    assert 'role="menubar"' in html
    assert "File" in html
    assert "Edit" in html
    assert "New" in html
    assert "Undo" in html


def test_menubar_item_with_shortcut(adapter):
    html = MenubarItem("Save", shortcut="⌘S").render()
    assert "Save" in html
    assert "⌘S" in html


# ── Dock ────────────────────────────────────────────────────────────────────


def test_dock_renders(adapter):
    html = Dock(
        DockItem(icon="🔍", label="Finder"),
        DockItem(icon="💻", label="Terminal"),
    ).render()
    assert "Finder" in html
    assert "Terminal" in html


def test_dock_item_with_badge(adapter):
    # DockItem is not a Component; test through Dock
    html = Dock(
        DockItem(icon="✉️", label="Mail", badge=5),
    ).render()
    assert "5" in html
    assert "Mail" in html


# ── Master-Detail ───────────────────────────────────────────────────────────


def test_master_detail_renders(adapter):
    html = MasterDetail(
        master=MasterList(
            MasterItem("Item 1"),
            MasterItem("Item 2"),
        ),
        detail=DetailPane("Detail content"),
    ).render()
    assert "Item 1" in html
    assert "Item 2" in html
    assert "Detail content" in html


def test_master_item_selected(adapter):
    html = MasterItem("Selected", selected=True).render_item().render()
    assert 'aria-selected="true"' in html


def test_master_detail_with_event(adapter):
    html = MasterItem("Clickable", on_select=lambda: None).render_item().render()
    assert "data-vd-event-click" in html


# ── Keyboard Shortcut Registry ──────────────────────────────────────────────


def test_keyboard_shortcuts_renders(adapter):
    html = KeyboardShortcutRegistry(
        KeyBinding("New file", "⌘N"),
        KeyBinding("Save", "⌘S"),
    ).render()
    assert "New file" in html
    assert "Save" in html


def test_keyboard_shortcuts_heading(adapter):
    html = KeyboardShortcutRegistry(
        KeyBinding("Print", "⌘P"),
        label="File shortcuts",
    ).render()
    assert "File shortcuts" in html
