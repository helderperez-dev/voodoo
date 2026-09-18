from pathlib import Path

import pytest

import voodoo
from voodoo.adapters import TailwindAdapter, VoodooCSSAdapter
from voodoo.adapters.voodoo_css import generate_component_css
from voodoo.ui import (
    AppShell,
    BottomNav,
    BottomNavItem,
    Button,
    Component,
    Drawer,
    DropdownMenu,
    Icon,
    MenuItem,
    MenuSeparator,
    Modal,
    ModalClose,
    ModalTrigger,
    Sidebar,
    SidebarItem,
    SidebarToggle,
    Snackbar,
    Tab,
    Tabs,
    Text,
    Toast,
    ToastRegion,
    set_style_adapter,
)
from voodoo.ui.styles import current_adapter
from voodoo.ui.styles.theme import Theme


@pytest.fixture(params=[VoodooCSSAdapter, TailwindAdapter])
def adapter(request):
    original = current_adapter()
    set_style_adapter(request.param())
    yield request.param
    set_style_adapter(original)


def test_sidebar_supports_expanded_rail_and_hidden_modes(adapter):
    sidebar = Sidebar(
        SidebarItem("Home", href="/", icon=Icon("home"), active=True),
        SidebarItem("Settings", href="/settings", icon=Icon("settings")),
        mode="rail",
    )
    html = sidebar.render()
    assert 'data-vd-sidebar-mode="rail"' in html
    assert 'data-vd-sidebar-modes="expanded,rail"' in html
    assert 'data-vd-sidebar-mobile-mode="hidden"' in html
    assert 'data-vd-sidebar-dismiss-mode="hidden"' in html
    assert 'aria-current="page"' in html
    assert "data-vd-sidebar-label" in html
    assert "data-vd-sidebar-item" in html

    toggle = SidebarToggle(sidebar).render()
    assert f'data-vd-sidebar-toggle="{sidebar.id}"' in toggle
    assert 'data-vd-sidebar-modes="expanded,rail,hidden"' in toggle
    assert 'aria-label="Expand navigation"' in toggle
    assert "data-vd-sidebar-toggle-glyph" in toggle


def test_sidebar_rejects_unknown_mode():
    with pytest.raises(ValueError, match="invalid Sidebar mode"):
        Sidebar(mode="floating")


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"modes": ()}, "Sidebar modes"),
        ({"modes": ("expanded", "expanded")}, "Sidebar modes"),
        ({"mobile_mode": "floating"}, "mobile_mode"),
        ({"dismiss_mode": "floating"}, "dismiss_mode"),
    ],
)
def test_sidebar_rejects_invalid_behavior_configuration(kwargs, message):
    with pytest.raises(ValueError, match=message):
        Sidebar(**kwargs)


def test_hidden_sidebar_is_removed_from_interaction_flow(adapter):
    html = Sidebar(SidebarItem("Home", href="/"), mode="hidden").render()
    assert 'aria-hidden="true"' in html
    assert "inert" in html


def test_sidebar_toggle_can_report_mode_changes(adapter):
    sidebar = Sidebar(id="navigation")
    html = SidebarToggle(sidebar, on_change=lambda value: value).render()
    assert "data-vd-event-change" in html


def test_app_shell_supports_sidebar_and_mobile_bottom_navigation(adapter):
    sidebar = Sidebar(SidebarItem("Home", href="/"), id="primary-sidebar")
    bottom_nav = BottomNav(
        BottomNavItem("Home", "/", icon=Icon("home"), active=True),
        BottomNavItem("Settings", "/settings", icon=Icon("settings")),
    )
    html = AppShell(Text("Content"), sidebar=sidebar, bottom_nav=bottom_nav).render()
    assert "primary-sidebar" in html
    assert 'aria-label="Primary navigation"' in html
    assert html.count('aria-current="page"') == 1
    assert 'data-vd-sidebar-placement="inside"' in html
    assert 'data-vd-sidebar-placement="launcher"' in html
    assert 'aria-label="Collapse navigation"' in html
    assert html.count('data-vd-sidebar-toggle="primary-sidebar"') == 2
    assert html.index('data-vd-sidebar-placement="inside"') < html.index("</aside>")
    assert "data-vd-app-shell-content" in html
    assert 'aria-label="Voodoo"' in html
    assert "data-vd-sidebar-brand" in html
    assert ">V.<" in html
    assert ">Voodoo<" in html
    assert 'data-vd-sidebar-modes="expanded,rail"' in html


def test_app_shell_relocates_supplied_sidebar_toggle(adapter):
    sidebar = Sidebar(
        SidebarItem("Home", href="/"),
        id="primary-sidebar",
        modes=("rail", "hidden"),
    )
    toggle = SidebarToggle(
        sidebar,
        modes=("rail", "hidden"),
        on_change=lambda value: value,
    )
    html = AppShell(toggle, Text("Content"), sidebar=sidebar).render()

    assert html.count('data-vd-sidebar-placement="inside"') == 1
    assert html.count('data-vd-sidebar-placement="launcher"') == 1
    assert html.count("data-vd-event-change") == 2
    assert 'data-vd-sidebar-modes="rail"' in html


def test_sidebar_brand_and_responsive_behavior_are_customizable(adapter):
    sidebar = Sidebar(
        SidebarItem("Home", href="/"),
        id="primary-sidebar",
        brand="Acme",
        logo="A",
        brand_href="/",
        brand_label="Acme home",
        modes=("expanded", "hidden"),
        mobile_mode="rail",
        dismiss_mode="rail",
    )
    html = AppShell(Text("Content"), sidebar=sidebar).render()

    assert 'aria-label="Acme home"' in html
    assert 'href="/"' in html
    assert ">A<" in html
    assert ">Acme<" in html
    assert 'data-vd-sidebar-modes="expanded,hidden"' in html
    assert 'data-vd-sidebar-mobile-mode="rail"' in html
    assert 'data-vd-sidebar-dismiss-mode="rail"' in html


def test_app_shell_can_disable_integrated_sidebar_controls(adapter):
    sidebar = Sidebar(SidebarItem("Home", href="/"), id="primary-sidebar")
    html = AppShell(Text("Content"), sidebar=sidebar, sidebar_toggle=False).render()

    assert "data-vd-sidebar-toggle" not in html


def test_app_shell_content_padding_is_configurable(adapter):
    html = AppShell(Text("Content"), content_padding="none").render()

    assert "data-vd-app-shell-content" in html
    expected_class = (
        "vd-app-shell-content--pad-none" if adapter is VoodooCSSAdapter else "p-0"
    )
    assert expected_class in html


def test_app_shell_rejects_unknown_content_padding():
    with pytest.raises(ValueError, match="content_padding"):
        AppShell(Text("Content"), content_padding="huge")


def test_sidebar_toggle_rejects_unknown_placement():
    with pytest.raises(ValueError, match="placement"):
        SidebarToggle("primary-sidebar", placement="floating")


def test_drawer_wires_trigger_dialog_and_close_control(adapter):
    trigger = Button("Open navigation")
    html = Drawer(
        trigger,
        Text("Drawer content"),
        title="Navigation",
        side="left",
    ).render()
    assert "data-vd-dialog-open" in html
    assert "data-vd-drawer" in html
    assert 'aria-modal="true"' in html
    assert "data-vd-dialog-close" in html
    assert 'tabindex="-1"' in html


def test_drawer_can_disable_light_dismissal(adapter):
    html = Drawer(
        Button("Open"),
        Text("Critical flow"),
        title="Required action",
        dismissible=False,
    ).render()
    assert "data-vd-dismissible" not in html


def test_modal_trigger_and_close_target_existing_modal(adapter):
    modal = Modal(Text("Settings"), id="settings-dialog")
    trigger = ModalTrigger("Settings", target=modal)
    assert 'data-vd-dialog-open="settings-dialog"' in trigger.render()
    assert "data-vd-dialog-close" in ModalClose("Done").render()


def test_dropdown_menu_exposes_menu_semantics(adapter):
    html = DropdownMenu(
        Button("Actions"),
        MenuItem("Rename", shortcut="R"),
        MenuSeparator(),
        MenuItem("Delete", destructive=True),
        label="Project actions",
        align="end",
    ).render()
    assert 'role="menu"' in html
    assert html.count('role="menuitem"') == 2
    assert 'aria-haspopup="menu"' in html
    assert 'aria-expanded="false"' in html
    assert 'data-vd-align="end"' in html


def test_dropdown_menu_assigns_an_id_to_custom_triggers(adapter):
    class Trigger(Component):
        tag = "button"
        auto_id = False

    trigger = Trigger("Actions")
    html = DropdownMenu(trigger, MenuItem("Rename")).render()
    assert "vd-menu-trigger-" in html
    assert "data-vd-anchor=" in html


def test_overlays_reject_non_button_triggers():
    with pytest.raises(TypeError, match="Drawer trigger"):
        Drawer(Text("Open"), Text("Body"), title="Drawer")
    with pytest.raises(TypeError, match="DropdownMenu trigger"):
        DropdownMenu(Text("Actions"), MenuItem("Rename"))


def test_disabled_menu_link_cannot_navigate_or_dispatch(adapter):
    html = MenuItem(
        "Delete",
        href="/danger",
        disabled=True,
        on_select=lambda: None,
    ).render()
    assert html.startswith("<button")
    assert "disabled" in html
    assert 'aria-disabled="true"' in html
    assert "href=" not in html
    assert "data-vd-event-click" not in html


def test_tabs_generate_linked_aria_contract(adapter):
    html = Tabs(
        Tab("overview", "Overview", Text("Summary")),
        Tab("activity", "Activity", Text("Recent changes")),
        value="activity",
    ).render()
    assert 'role="tablist"' in html
    assert html.count('role="tab"') == 2
    assert html.count('role="tabpanel"') == 2
    assert 'data-vd-tab="activity"' in html
    assert 'aria-selected="true"' in html
    assert 'data-vd-tab-panel="overview"' in html
    assert "hidden" in html


def test_tabs_validate_identity_selection_and_activation(adapter):
    with pytest.raises(ValueError, match="unique"):
        Tabs(Tab("same", "One"), Tab("same", "Two"))
    with pytest.raises(ValueError, match="enabled"):
        Tabs(Tab("disabled", "Disabled", disabled=True))
    with pytest.raises(ValueError, match="disabled"):
        Tabs(
            Tab("one", "One"),
            Tab("disabled", "Disabled", disabled=True),
            value="disabled",
        )

    html = Tabs(
        Tab("account settings", "Account"),
        Tab("security", "Security"),
        activation="manual",
        on_change=lambda value: value,
    ).render()
    assert 'data-vd-activation="manual"' in html
    assert "data-vd-event-change" in html
    assert "-tab-0" in html
    assert 'id="account settings"' not in html


def test_toast_and_snackbar_support_mobile_feedback(adapter):
    html = ToastRegion(
        Toast("Profile updated", title="Saved", tone="success", duration=4000),
        Snackbar("Connection restored"),
        position="bottom-right",
    ).render()
    assert 'aria-live="polite"' in html
    assert html.count("data-vd-toast") >= 2
    assert 'data-vd-duration="4000"' in html
    assert "data-vd-dismiss" in html


def test_interaction_runtime_contains_shared_behaviors():
    client = Path(voodoo.__file__).parent / "static" / "client.js"
    source = client.read_text(encoding="utf-8")
    assert "setupAdaptiveNavigation" in source
    assert "setSidebarMode" in source
    assert "toggle.dataset.vdSidebarCurrentMode = mode" in source
    assert "sidebar.dataset.vdSidebarMobileMode || 'hidden'" in source
    assert "sidebarDismiss.dataset.vdSidebarDismissMode || 'hidden'" in source
    assert "matches && mode === 'expanded'" in source
    assert "openDialog" in source
    assert "positionAnchored" in source
    assert "_menuItems" in source
    assert "_vdTypeahead" in source
    assert "activateTab" in source
    assert "window.setTimeout(function()" in source
    assert "setupToasts" in source
    assert "snackbar" in source
    assert "prefers-reduced-motion" in source


def test_native_styles_include_adaptive_and_overlay_contracts():
    css = generate_component_css(Theme())
    assert '.vd-sidebar[data-vd-sidebar-mode="rail"]' in css
    assert "position: relative; inset: auto; width: 4.5rem" in css
    assert ".vd-sidebar-header" in css
    assert ".vd-sidebar-brand-mark" in css
    assert ".vd-sidebar-controls" in css
    assert "justify-content: center; gap: 0" in css
    assert "position: absolute; inset:" in css
    assert 'data-vd-sidebar-current-mode="rail"' in css
    assert ".vd-app-shell-content" in css
    assert "padding: clamp(" in css
    assert '.vd-sidebar-toggle--launcher[data-vd-sidebar-current-mode="hidden"]' in css
    assert ".vd-sidebar-scrim" in css
    assert ".vd-bottom-nav" in css
    assert ".vd-drawer::backdrop" in css
    assert ".vd-drawer--top.vd-drawer--sm" in css
    assert ".vd-dropdown-menu:popover-open" in css
    assert ".vd-dropdown-menu[data-vd-fallback-open]" in css
    assert '.vd-tabs-trigger[aria-selected="true"]' in css
    assert ".vd-toast-region--bottom-right" in css
