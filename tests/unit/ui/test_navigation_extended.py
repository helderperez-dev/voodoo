"""Tests for Priority 3: Adaptive Navigation components."""

import pytest

from voodoo.adapters import TailwindAdapter, VoodooCSSAdapter
from voodoo.ui import set_style_adapter
from voodoo.ui.navigation_extended import (
    Action,
    ActionSheet,
    AnchorLink,
    AnchorNavigation,
    BottomSheet,
    NavColumn,
    NavContent,
    NavigationMenu,
    NavLinkItem,
    NavTrigger,
    Pagination,
    Step,
    Stepper,
    TopBar,
)
from voodoo.ui.styles import current_adapter


@pytest.fixture(params=[VoodooCSSAdapter, TailwindAdapter])
def adapter(request):
    original = current_adapter()
    set_style_adapter(request.param())
    yield request.param
    set_style_adapter(original)


# ── Pagination ──────────────────────────────────────────────────────────────


def test_pagination_renders(adapter):
    html = Pagination(total_pages=10, current_page=1).render()
    assert 'aria-label="Pagination"' in html
    assert 'role="navigation"' in html


def test_pagination_shows_pages(adapter):
    html = Pagination(total_pages=5, current_page=1).render()
    assert "1" in html
    assert "5" in html


def test_pagination_current_page(adapter):
    html = Pagination(total_pages=5, current_page=3).render()
    assert 'aria-current="page"' in html


def test_pagination_prev_next(adapter):
    html = Pagination(total_pages=5, current_page=3).render()
    assert 'aria-label="Previous page"' in html
    assert 'aria-label="Next page"' in html


def test_pagination_disabled_prev_on_first(adapter):
    html = Pagination(total_pages=5, current_page=1).render()
    assert "disabled" in html


def test_pagination_with_event(adapter):
    html = Pagination(
        total_pages=5,
        current_page=1,
        on_change=lambda p: p,
    ).render()
    assert "data-vd-event-click" in html


def test_pagination_shared_control_states_disable_navigation(adapter):
    html = Pagination(
        total_pages=8,
        current_page=3,
        loading=True,
        error="Pages unavailable",
        on_change=lambda page: page,
    ).render()
    assert 'aria-busy="true"' in html
    assert 'aria-invalid="true"' in html
    assert html.count("disabled") >= 3
    assert "data-vd-event-click" not in html


# ── Stepper ─────────────────────────────────────────────────────────────────


def test_stepper_renders(adapter):
    html = Stepper(
        Step("Account", description="Create account"),
        Step("Profile", description="Fill profile"),
        Step("Done", description="Complete"),
        current=0,
    ).render()
    assert 'role="navigation"' in html
    assert "Account" in html
    assert "Profile" in html
    assert "Done" in html


def test_stepper_vertical(adapter):
    html = Stepper(
        Step("A"),
        Step("B"),
        orientation="vertical",
    ).render()
    assert 'data-vd-orientation="vertical"' in html


def test_stepper_step_states(adapter):
    html = Stepper(
        Step("Done"),
        Step("Active"),
        Step("Next"),
        current=1,
    ).render()
    assert "completed" in html or "active" in html


def test_stepper_shared_control_states_disable_completed_steps(adapter):
    html = Stepper(
        Step("Account"),
        Step("Profile"),
        current=1,
        loading=True,
        error="Progress unavailable",
        on_step_click=lambda index: index,
    ).render()
    assert 'aria-busy="true"' in html
    assert 'aria-invalid="true"' in html
    assert 'aria-disabled="true"' in html
    assert "data-vd-event-click" not in html


@pytest.mark.parametrize(
    "state, expected",
    [
        ({"disabled": True}, 'aria-disabled="true"'),
        ({"read_only": True}, 'aria-readonly="true"'),
        ({"loading": True}, 'aria-busy="true"'),
        ({"error": "Step unavailable"}, 'data-vd-error="Step unavailable"'),
    ],
)
def test_step_item_unavailable_states_suppress_completed_selection(
    adapter, state, expected
):
    html = Stepper(
        Step("Done", **state),
        Step("Current"),
        current=1,
        on_step_click=lambda index: index,
    ).render()
    assert expected in html
    assert "data-vd-event-click" not in html


# ── Anchor Navigation ───────────────────────────────────────────────────────


def test_anchor_navigation_renders(adapter):
    html = AnchorNavigation(
        AnchorLink("Introduction", href="#intro"),
        AnchorLink("Setup", href="#setup"),
    ).render()
    assert "Introduction" in html
    assert "Setup" in html
    assert "#intro" in html
    assert "#setup" in html


def test_anchor_navigation_heading(adapter):
    html = AnchorNavigation(
        AnchorLink("A", href="#a"),
        label="On this page",
    ).render()
    assert "On this page" in html


@pytest.mark.parametrize(
    "state, expected",
    [
        ({"disabled": True}, 'aria-disabled="true"'),
        ({"read_only": True}, 'aria-readonly="true"'),
        ({"loading": True}, 'aria-busy="true"'),
        ({"error": "anchor unavailable"}, 'data-vd-error="anchor unavailable"'),
    ],
)
def test_anchor_link_unavailable_states_remove_target(adapter, state, expected):
    html = AnchorNavigation(
        AnchorLink("Setup", href="#setup", **state),
    ).render()
    assert expected in html
    assert 'href="#setup"' not in html


# ── Action Sheet ────────────────────────────────────────────────────────────


def test_action_sheet_renders(adapter):
    html = ActionSheet(
        Action("Edit", description="Edit item"),
        Action("Delete", destructive=True),
        title="Actions",
    ).render()
    assert "Edit" in html
    assert "Delete" in html
    assert "Actions" in html


def test_action_sheet_has_cancel(adapter):
    html = ActionSheet(Action("A")).render()
    assert "Cancel" in html


def test_action_sheet_custom_cancel(adapter):
    html = ActionSheet(
        Action("A"),
        cancel_label="Close",
    ).render()
    assert "Close" in html


def test_action_destructive(adapter):
    html = Action("Delete", destructive=True).render()
    assert "Delete" in html


def test_action_state_contract_suppresses_unavailable_selection(adapter):
    html = Action(
        "Delete",
        on_select=lambda: None,
        read_only=True,
        loading=True,
        error="Unavailable",
    ).render()
    assert 'aria-disabled="true"' in html
    assert 'aria-busy="true"' in html
    assert 'aria-invalid="true"' in html
    assert 'data-vd-error="Unavailable"' in html
    assert "data-vd-event-click" not in html


def test_action_sheet_state_contract_blocks_unavailable_actions(adapter):
    html = ActionSheet(
        Action("Delete", on_select=lambda: None),
        on_cancel=lambda: None,
        open=True,
        read_only=True,
        loading=True,
        error="Unavailable",
    ).render()
    assert 'aria-disabled="true"' in html
    assert 'aria-busy="true"' in html
    assert 'aria-invalid="true"' in html
    assert 'data-vd-error="Unavailable"' in html
    assert 'open="open"' not in html
    assert "data-vd-event-click" not in html


# ── Bottom Sheet ────────────────────────────────────────────────────────────


def test_bottom_sheet_renders(adapter):
    html = BottomSheet(
        "Content here",
        title="Details",
    ).render()
    assert "Details" in html
    assert "Content here" in html


def test_bottom_sheet_with_snap_points(adapter):
    html = BottomSheet(
        "X",
        snap_points=(25, 50, 100),
    ).render()
    assert "X" in html


def test_bottom_sheet_state_contract_blocks_unavailable_opening(adapter):
    html = BottomSheet(
        "Filters",
        open=True,
        read_only=True,
        loading=True,
        error="Unavailable",
    ).render()
    assert 'aria-disabled="true"' in html
    assert 'aria-busy="true"' in html
    assert 'aria-invalid="true"' in html
    assert 'data-vd-error="Unavailable"' in html
    assert 'open="open"' not in html


# ── Top Bar ─────────────────────────────────────────────────────────────────


def test_top_bar_renders(adapter):
    html = TopBar().render()
    assert "vd-top-bar" in html


def test_top_bar_with_title(adapter):
    html = TopBar(title="My App").render()
    assert "My App" in html


def test_top_bar_sticky(adapter):
    html = TopBar(sticky=True).render()
    assert "data-vd-sticky" in html


# ── Navigation Menu ─────────────────────────────────────────────────────────


def test_navigation_menu_renders(adapter):
    html = NavigationMenu(
        NavTrigger("Products", NavContent()),
        NavTrigger("Company", NavContent()),
    ).render()
    assert "Products" in html
    assert "Company" in html


def test_navigation_menu_with_content(adapter):
    html = NavigationMenu(
        NavTrigger(
            "Products",
            NavContent(
                NavColumn(
                    NavLinkItem("Analytics", href="/analytics"),
                ),
            ),
        ),
    ).render()
    assert "Products" in html
    assert "Analytics" in html


def test_navigation_menu_state_contract_blocks_all_triggers(adapter):
    html = NavigationMenu(
        NavTrigger("Products", NavContent()),
        NavTrigger("Company", NavContent()),
        read_only=True,
        loading=True,
        error="Navigation unavailable",
    ).render()
    assert html.count('aria-disabled="true"') >= 3
    assert 'aria-readonly="true"' in html
    assert 'aria-busy="true"' in html
    assert 'data-vd-error="Navigation unavailable"' in html
    assert "data-vd-nav-trigger" not in html


@pytest.mark.parametrize(
    "state, expected",
    [
        ({"disabled": True}, 'aria-disabled="true"'),
        ({"read_only": True}, 'aria-readonly="true"'),
        ({"loading": True}, 'aria-busy="true"'),
        ({"error": "menu unavailable"}, 'data-vd-error="menu unavailable"'),
    ],
)
def test_nav_trigger_unavailable_states_disable_activation(adapter, state, expected):
    html = NavigationMenu(NavTrigger("Products", NavContent(), **state)).render()
    assert expected in html
    assert " disabled" in html


@pytest.mark.parametrize(
    "state, expected",
    [
        ({"disabled": True}, 'aria-disabled="true"'),
        ({"read_only": True}, 'aria-readonly="true"'),
        ({"loading": True}, 'aria-busy="true"'),
        ({"error": "link unavailable"}, 'data-vd-error="link unavailable"'),
    ],
)
def test_nav_link_item_unavailable_states_remove_target(adapter, state, expected):
    html = NavLinkItem("Analytics", href="/analytics", **state).render()
    assert expected in html
    assert 'href="/analytics"' not in html


def test_anchor_navigation_state_contract_blocks_all_links(adapter):
    html = AnchorNavigation(
        AnchorLink("Intro", href="#intro"),
        AnchorLink("Config", href="#config"),
        read_only=True,
        loading=True,
        error="Anchors unavailable",
    ).render()
    assert html.count('aria-disabled="true"') >= 3
    assert 'aria-readonly="true"' in html
    assert 'aria-busy="true"' in html
    assert 'data-vd-error="Anchors unavailable"' in html
    assert 'href="#intro"' not in html
    assert 'href="#config"' not in html
