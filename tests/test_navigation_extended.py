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

        on_change=lambda p: p,
    ).render()
    assert "data-vd-event-click" in html


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


# ── Top Bar ─────────────────────────────────────────────────────────────────


def test_top_bar_renders(adapter):
    html = TopBar().render()
    assert "vd-top-bar" in html


def test_top_bar_with_title(adapter):
    html = TopBar(title="My App").render()
    assert "My App" in html


def test_top_bar_sticky(adapter):
    html = TopBar(sticky=True).render()



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
