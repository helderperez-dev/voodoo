"""Validate the explicit shared state API for canonical interactive controls."""

from __future__ import annotations

import inspect

import voodoo.ui as ui

CONTROL_STATES: dict[str, frozenset[str]] = {
    "Button": frozenset({"disabled", "read_only", "loading", "error"}),
    "Form": frozenset({"disabled", "read_only", "loading", "error"}),
    "Field": frozenset({"disabled", "read_only", "loading", "error"}),
    "Card": frozenset({"disabled", "read_only", "loading", "error"}),
    "Composer": frozenset({"disabled", "read_only", "loading", "error"}),
    "SidebarToggle": frozenset({"disabled", "read_only", "loading", "error"}),
    "Popover": frozenset({"disabled", "read_only", "loading", "error"}),
    "A": frozenset({"disabled", "read_only", "loading", "error"}),
    "Link": frozenset({"disabled", "read_only", "loading", "error"}),
    "ListOption": frozenset({"disabled", "read_only", "loading", "error"}),
    "MenubarMenu": frozenset({"disabled", "read_only", "loading", "error"}),
    "NavigationMenu": frozenset({"disabled", "read_only", "loading", "error"}),
    "BottomNav": frozenset({"disabled", "read_only", "loading", "error"}),
    "AnchorNavigation": frozenset({"disabled", "read_only", "loading", "error"}),
    "MasterList": frozenset({"disabled", "read_only", "loading", "error"}),
    "Menubar": frozenset({"disabled", "read_only", "loading", "error"}),
    "ButtonGroup": frozenset({"disabled", "read_only", "loading", "error"}),
    "InputGroup": frozenset({"disabled", "read_only", "loading", "error"}),
    "NavLink": frozenset({"disabled", "read_only", "loading", "error"}),
    "BackLink": frozenset({"disabled", "read_only", "loading", "error"}),
    "LinkArrow": frozenset({"disabled", "read_only", "loading", "error"}),
    "ThemeToggle": frozenset({"disabled", "read_only", "loading", "error"}),
    "AlertDialogTrigger": frozenset({"disabled", "read_only", "loading", "error"}),
    "ModalTrigger": frozenset({"disabled", "read_only", "loading", "error"}),
    "ModalClose": frozenset({"disabled", "read_only", "loading", "error"}),
    "AccordionItem": frozenset({"disabled", "read_only", "loading", "error"}),
    "BreadcrumbItem": frozenset({"disabled", "read_only", "loading", "error"}),
    "LoginForm": frozenset({"disabled", "read_only", "loading", "error"}),
    "RegisterForm": frozenset({"disabled", "read_only", "loading", "error"}),
    "UserBadge": frozenset({"disabled", "read_only", "loading", "error"}),
    "Option": frozenset({"disabled", "read_only", "loading", "error"}),
    "Progress": frozenset({"disabled", "read_only", "loading", "error"}),
    "Spinner": frozenset({"disabled", "read_only", "loading", "error"}),
    "Alert": frozenset({"disabled", "read_only", "loading", "error"}),
    "EmptyState": frozenset({"disabled", "read_only", "loading", "error"}),
    "Toast": frozenset({"disabled", "read_only", "loading", "error"}),
    "Snackbar": frozenset({"disabled", "read_only", "loading", "error"}),
    "StatusBadge": frozenset({"disabled", "read_only", "loading", "error"}),
    "Input": frozenset({"disabled", "read_only", "loading", "error"}),
    "Textarea": frozenset({"disabled", "read_only", "loading", "error"}),
    "Select": frozenset({"disabled", "read_only", "loading", "error"}),
    "Checkbox": frozenset({"disabled", "read_only", "loading", "error"}),
    "Radio": frozenset({"disabled", "read_only", "loading", "error"}),
    "DatePicker": frozenset({"disabled", "read_only", "loading", "error"}),
    "TimePicker": frozenset({"disabled", "read_only", "loading", "error"}),
    "Switch": frozenset({"disabled", "read_only", "loading", "error"}),
    "NumberInput": frozenset({"disabled", "read_only", "loading", "error"}),
    "SearchInput": frozenset({"disabled", "read_only", "loading", "error"}),
    "PasswordInput": frozenset({"disabled", "read_only", "loading", "error"}),
    "Combobox": frozenset({"disabled", "read_only", "loading", "error"}),
    "MultiSelect": frozenset({"disabled", "read_only", "loading", "error"}),
    "RadioGroup": frozenset({"disabled", "read_only", "loading", "error"}),
    "CheckboxGroup": frozenset({"disabled", "read_only", "loading", "error"}),
    "Slider": frozenset({"disabled", "read_only", "loading", "error"}),
    "Calendar": frozenset({"disabled", "read_only", "loading", "error"}),
    "OTPInput": frozenset({"disabled", "read_only", "loading", "error"}),
    "RangeSlider": frozenset({"disabled", "read_only", "loading", "error"}),
    "Autocomplete": frozenset({"disabled", "read_only", "loading", "error"}),
    "FileUpload": frozenset({"disabled", "read_only", "loading", "error"}),
    "DropZone": frozenset({"disabled", "read_only", "loading", "error"}),
    "ListBox": frozenset({"disabled", "read_only", "loading", "error"}),
    "Pagination": frozenset({"disabled", "read_only", "loading", "error"}),
    "Stepper": frozenset({"disabled", "read_only", "loading", "error"}),
    "SegmentedControl": frozenset({"disabled", "read_only", "loading", "error"}),
    "Tabs": frozenset({"disabled", "read_only", "loading", "error"}),
    "CommandPalette": frozenset({"disabled", "read_only", "loading", "error"}),
    "Drawer": frozenset({"disabled", "read_only", "loading", "error"}),
    "DropdownMenu": frozenset({"disabled", "read_only", "loading", "error"}),
    "Modal": frozenset({"disabled", "read_only", "loading", "error"}),
    "Dialog": frozenset({"disabled", "read_only", "loading", "error"}),
    "ContextMenu": frozenset({"disabled", "read_only", "loading", "error"}),
    "AlertDialog": frozenset({"disabled", "read_only", "loading", "error"}),
    "ActionSheet": frozenset({"disabled", "read_only", "loading", "error"}),
    "BottomSheet": frozenset({"disabled", "read_only", "loading", "error"}),
    "Action": frozenset({"disabled", "read_only", "loading", "error"}),
    "ToggleGroup": frozenset({"disabled", "read_only", "loading", "error"}),
    "ToggleItem": frozenset({"disabled", "read_only", "loading", "error"}),
    "Segment": frozenset({"disabled", "read_only", "loading", "error"}),
    "MenuItem": frozenset({"disabled", "read_only", "loading", "error"}),
    "MenuCheckboxItem": frozenset({"disabled", "read_only", "loading", "error"}),
    "MenuRadioItem": frozenset({"disabled", "read_only", "loading", "error"}),
    "SubMenu": frozenset({"disabled", "read_only", "loading", "error"}),
    "ToolbarButton": frozenset({"disabled", "read_only", "loading", "error"}),
    "MenubarItem": frozenset({"disabled", "read_only", "loading", "error"}),
    "DockItem": frozenset({"disabled", "read_only", "loading", "error"}),
    "MasterItem": frozenset({"disabled", "read_only", "loading", "error"}),
    "TreeNode": frozenset({"disabled", "read_only", "loading", "error"}),
    "TreeView": frozenset({"disabled", "read_only", "loading", "error"}),
    "DataTable": frozenset({"disabled", "read_only", "loading", "error"}),
    "EnhancedDataTable": frozenset({"disabled", "read_only", "loading", "error"}),
    "CommandBar": frozenset({"disabled", "read_only", "loading", "error"}),
    "ApprovalCard": frozenset({"disabled", "read_only", "loading", "error"}),
    "SidebarItem": frozenset({"disabled", "read_only", "loading", "error"}),
    "BottomNavItem": frozenset({"disabled", "read_only", "loading", "error"}),
    "Step": frozenset({"disabled", "read_only", "loading", "error"}),
    "NavTrigger": frozenset({"disabled", "read_only", "loading", "error"}),
    "NavLinkItem": frozenset({"disabled", "read_only", "loading", "error"}),
    "AnchorLink": frozenset({"disabled", "read_only", "loading", "error"}),
    "Command": frozenset({"disabled", "read_only", "loading", "error"}),
    "Tab": frozenset({"disabled", "read_only", "loading", "error"}),
    "CheckboxInput": frozenset({"disabled", "read_only", "loading", "error"}),
    "RadioInput": frozenset({"disabled", "read_only", "loading", "error"}),
}

# Navigation affordances are not form fields, but their activation still needs
# one canonical state contract so keyboard and pointer paths agree.
DISABLED_CONTROLS: frozenset[str] = frozenset({"SidebarToggle"})

# A small number of components legitimately use one state name for a native
# semantic rather than the shared interactive contract. Keep those exceptions
# explicit so a newly added partial state API cannot silently bypass review.
PARTIAL_STATE_ALLOWLIST: dict[str, frozenset[str]] = {
    "DataList": frozenset({"loading", "error"}),
    "DescriptionList": frozenset({"loading", "error"}),
    "Img": frozenset({"loading"}),
}


def _behavior_cases() -> tuple[tuple[str, object], ...]:
    """Return representative unavailable controls for the runtime gate.

    Signature introspection catches API drift, but it cannot prove that a
    component actually suppresses its client event bridge. Keep this matrix
    deliberately small and stable; focused unit tests provide the exhaustive
    component coverage.
    """

    def callback(*_args: object, **_kwargs: object) -> None:
        return None
    return (
        ("Input.disabled", ui.Input(on_change=callback, disabled=True)),
        ("Switch.loading", ui.Switch(on_change=callback, loading=True)),
        ("ListBox.error", ui.ListBox(ui.ListOption("One"), on_select=callback, error=True)),
        ("MenuItem.error", ui.MenuItem("Delete", on_select=callback, error=True)),
        ("Action.error", ui.Action("Delete", on_select=callback, error=True)),
        (
            "ToggleGroup.error",
            ui.ToggleGroup(
                ui.ToggleItem(value="one", label="One"),
                on_change=callback,
                error=True,
            ),
        ),
    )


def _collection_state_cases() -> tuple[tuple[str, object, str, str], ...]:
    """Ensure data collections replace stale content in unavailable states."""
    return (
        (
            "Table.loading",
            ui.Table(["Name"], [["stale"]], loading=True),
            "stale",
            'data-vd-state="loading"',
        ),
        (
            "ListBox.error",
            ui.ListBox(ui.ListOption("stale"), error="Unavailable"),
            "stale",
            'data-vd-state="error"',
        ),
        (
            "TreeView.loading",
            ui.TreeView(ui.TreeNode("stale"), loading=True),
            "stale",
            'data-vd-state="loading"',
        ),
        (
            "MasterList.error",
            ui.MasterList(ui.MasterItem("stale"), error="Unavailable"),
            "stale",
            'data-vd-state="error"',
        ),
        (
            "DataList.loading",
            ui.DataList(ui.DataRow("Name", "stale"), loading=True),
            "stale",
            "data-vd-loading-state",
        ),
        (
            "DescriptionList.error",
            ui.DescriptionList(ui.DescriptionItem("Name", "stale"), error="Unavailable"),
            "stale",
            "data-vd-error-state",
        ),
    )


def _validate_behavior_cases() -> list[str]:
    violations: list[str] = []
    for name, component in _behavior_cases():
        try:
            rendered = component.render()
        except (AttributeError, TypeError, ValueError) as error:
            violations.append(f"{name}: runtime state case failed: {error}")
            continue
        if "data-vd-event-" in rendered:
            violations.append(f"{name}: unavailable control retained a client event binding")
    return violations


def _validate_collection_state_cases() -> list[str]:
    violations: list[str] = []
    for name, component, forbidden, marker in _collection_state_cases():
        try:
            rendered = component.render()
        except (AttributeError, TypeError, ValueError) as error:
            violations.append(f"{name}: runtime state case failed: {error}")
            continue
        if forbidden in rendered:
            violations.append(f"{name}: stale collection content remained visible")
        if marker not in rendered:
            violations.append(f"{name}: missing semantic state marker {marker}")
    return violations


def _validate_catalog_state_shapes() -> list[str]:
    """Reject unreviewed partial state APIs across every exported component."""
    violations: list[str] = []
    shared = frozenset({"disabled", "read_only", "loading", "error"})
    for name in ui.__all__:
        component = getattr(ui, name, None)
        if not inspect.isclass(component) or not issubclass(component, ui.Component):
            continue
        parameters = set(inspect.signature(component).parameters)
        present = frozenset(parameters & shared)
        if not present:
            continue
        allowed = PARTIAL_STATE_ALLOWLIST.get(name)
        if allowed is None and present != shared:
            violations.append(
                f"{name}: partial shared state API {sorted(present)} requires explicit allowlist"
            )
        elif allowed is not None and present != allowed:
            violations.append(
                f"{name}: allowlisted state shape changed to {sorted(present)}"
            )
    return violations


def main() -> int:
    violations: list[str] = []
    for name, required in CONTROL_STATES.items():
        component = getattr(ui, name, None)
        if component is None:
            violations.append(f"{name}: export missing")
            continue
        parameters = set(inspect.signature(component).parameters)
        missing = sorted(required - parameters)
        if missing:
            violations.append(f"{name}: missing explicit state parameters {missing}")
    for name in sorted(DISABLED_CONTROLS):
        component = getattr(ui, name, None)
        if component is None:
            violations.append(f"{name}: export missing")
            continue
        if "disabled" not in inspect.signature(component).parameters:
            violations.append(f"{name}: missing explicit disabled parameter")
    # Audit the entire exported component catalog, not only the curated
    # control list. Any constructor exposing one shared state parameter must
    # expose all four unless its exception is documented above.
    violations.extend(_validate_catalog_state_shapes())
    violations.extend(_validate_behavior_cases())
    violations.extend(_validate_collection_state_cases())
    if violations:
        raise SystemExit("control state contract failed: " + "; ".join(violations))
    print(
        "control state contract passed "
        f"({len(CONTROL_STATES)} controls, {len(PARTIAL_STATE_ALLOWLIST)} explicit exceptions)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
