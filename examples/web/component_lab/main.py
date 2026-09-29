"""Voodoo Component Lab — visual and behavioral acceptance application.

Run:
    voodoo dev examples.web.component_lab.main:app

The lab intentionally uses only public Voodoo APIs and no application CSS.
It is the canonical surface for visual review, interaction checks and future
browser screenshot regression tests.
"""

from __future__ import annotations

from types import SimpleNamespace

from voodoo import App, page
from voodoo.ui import (
    A,
    Accordion,
    AccordionItem,
    Action,
    ActionSheet,
    AgentStatus,
    Alert,
    AlertDialog,
    AlertDialogTrigger,
    ApprovalCard,
    Autocomplete,
    Badge,
    BottomSheet,
    Breadcrumb,
    BreadcrumbItem,
    Button,
    ButtonGroup,
    CapabilityList,
    Card,
    CheckboxGroup,
    CheckboxInput,
    Column,
    ColumnDef,
    Combobox,
    Command,
    CommandGroup,
    CommandPalette,
    Container,
    ContextMenu,
    DataList,
    DataRow,
    DataStat,
    DataTable,
    DatePicker,
    DescriptionItem,
    DescriptionList,
    DescriptionSection,
    DetailPane,
    DeviceCard,
    Dock,
    DockItem,
    DropdownMenu,
    DropZone,
    EdgeNode,
    EmptyState,
    EnhancedDataTable,
    EventRow,
    ExecutionStatus,
    ExecutionTimeline,
    Field,
    FileUpload,
    Flex,
    Form,
    FormError,
    FormValidationSummary,
    Grid,
    Heading,
    Input,
    InspectorPanel,
    Kbd,
    KeyBinding,
    KeyboardShortcutRegistry,
    ListBox,
    ListOption,
    LogViewer,
    MasterDetail,
    MasterItem,
    MasterList,
    MenuCheckboxItem,
    MenuGroup,
    MenuItem,
    MenuRadioItem,
    MenuSeparator,
    Menubar,
    MenubarItem,
    MenubarMenu,
    MenubarSeparator,
    Metric,
    MultiSelect,
    NumberInput,
    ObservationFeed,
    OTPInput,
    Page,
    Pagination,
    Panel,
    PasswordInput,
    PolicyDecision,
    Popover,
    Progress,
    RadioGroup,
    RadioInput,
    RangeSlider,
    ResizablePanels,
    RuntimeStatus,
    ScrollArea,
    SearchInput,
    Segment,
    SegmentedControl,
    Skeleton,
    Slider,
    Spinner,
    Stack,
    StatGroup,
    StatusBadge,
    Step,
    Stepper,
    SubMenu,
    Switch,
    Tab,
    Tabs,
    TelemetryPanel,
    Text,
    Textarea,
    ThemeToggle,
    TimePicker,
    Timeline,
    ToggleGroup,
    ToggleItem,
    Toolbar,
    ToolbarButton,
    ToolbarGroup,
    ToolbarSeparator,
    Tooltip,
    TreeNode,
    TreeView,
    WorldEntityInspector,
)

app = App()


async def _noop(*_args, **_kwargs):
    return None


def _header(active: str) -> Card:
    links = [
        ("Overview", "/"),
        ("Forms", "/forms"),
        ("Navigation", "/navigation"),
        ("Advanced", "/advanced"),
        ("Data", "/data"),
        ("Workspace", "/workspace"),
        ("System", "/system"),
        ("Feedback", "/feedback"),
    ]
    return Card(
        Flex(
            Stack(
                Badge("Voodoo", variant="secondary"),
                Heading("Component Lab", level=1, size="lg"),
                gap="xs",
            ),
            Flex(
                *[
                    A(
                        label,
                        href=href,
                        aria_current="page" if active == href else None,
                    )
                    for label, href in links
                ],
                ThemeToggle(),
                gap="md",
                items="center",
                wrap="wrap",
            ),
            justify="between",
            items="center",
            gap="lg",
            wrap="wrap",
        ),
        variant="ghost",
        padding="none",
    )


def _section(title: str, description: str, *children) -> Stack:
    return Stack(
        Stack(
            Heading(title, level=2, size="md"),
            Text(description, tone="muted"),
            gap="xs",
        ),
        *children,
        gap="lg",
    )


@page("/")
def overview():
    return Page(
        Stack(
            _header("/"),
            Stack(
                Badge("Design System 4 acceptance surface", variant="outline"),
                Heading("Every component should feel product-ready.", size="display"),
                Text(
                    "This page is the visual contract for Voodoo's native component "
                    "library: no Tailwind, no custom application CSS, no hidden fixes.",
                    tone="muted",
                ),
                gap="md",
            ),
            _section(
                "Actions",
                "Variants, sizes and states must remain visually balanced together.",
                Card(
                    Stack(
                        Flex(
                            Button("Primary", variant="primary"),
                            Button("Secondary", variant="secondary"),
                            Button("Outline", variant="outline"),
                            Button("Ghost", variant="ghost"),
                            Button("Danger", variant="danger"),
                            gap="sm",
                            wrap="wrap",
                        ),
                        Flex(
                            Button("Small", size="sm"),
                            Button("Default"),
                            Button("Large", size="lg"),
                            Button("Loading", loading=True, variant="primary"),
                            Button("Disabled", disabled=True),
                            gap="sm",
                            wrap="wrap",
                        ),
                        ButtonGroup(
                            Button("Day"),
                            Button("Week"),
                            Button("Month"),
                            label="Range",
                        ),
                        gap="lg",
                    )
                ),
            ),
            _section(
                "Surfaces",
                "Cards should provide hierarchy without making the page feel boxed-in.",
                Grid(
                    Card(
                        Heading("Default", level=3),
                        Text("Quiet surface for ordinary content.", tone="muted"),
                    ),
                    Card(
                        Heading("Elevated", level=3),
                        Text("Raised only when hierarchy requires it.", tone="muted"),
                        variant="elevated",
                    ),
                    Card(
                        Heading("Outline", level=3),
                        Text("Low-emphasis boundary with no artificial depth.", tone="muted"),
                        variant="outline",
                    ),
                    cols="3",
                    gap="lg",
                ),
            ),
            _section(
                "Signals",
                "Status should be legible without relying only on color.",
                Flex(
                    StatusBadge("online"),
                    StatusBadge("degraded"),
                    StatusBadge("offline"),
                    Badge("Default"),
                    Badge("Success", variant="success"),
                    Badge("Warning", variant="warning"),
                    Badge("Danger", variant="danger"),
                    gap="sm",
                    wrap="wrap",
                ),
                Grid(
                    Metric("Latency", "42 ms", change="-8%", change_tone="success"),
                    Metric("Requests", "12.8k", description="Last 24 hours"),
                    Metric("Errors", "0.08%", description="Healthy"),
                    cols="3",
                    gap="lg",
                ),
            ),
            _section(
                "Loading and empty states",
                "Temporary and empty states are first-class product moments.",
                Card(
                    Stack(
                        Skeleton(lines=3),
                        Progress(68, label="Import progress"),
                        Flex(Spinner("Loading"), Text("Synchronizing…", tone="muted"), gap="sm", items="center"),
                        gap="lg",
                    )
                ),
                EmptyState(
                    "Nothing here yet",
                    "Create the first item to turn an empty surface into useful state.",
                    action=Button("Create item", variant="primary"),
                    icon="plus",
                ),
            ),
            gap="xxxl",
        ),
        size="xl",
    )


@page("/forms")
def forms():
    return Page(
        Stack(
            _header("/forms"),
            _section(
                "Inputs",
                "Form controls must share height, rhythm, focus and disabled behavior.",
                Card(
                    Grid(
                        Field("Name", Input(name="name", placeholder="Ada Lovelace"), required=True),
                        Field("Search", SearchInput(name="search", placeholder="Search projects")),
                        Field("Password", PasswordInput(name="password", placeholder="••••••••")),
                        Field("Seats", NumberInput(name="seats", value=3, minimum=1, maximum=20)),
                        Field("Volume", Slider(name="volume", value=62)),
                        Field("Notes", Textarea(name="notes", placeholder="A short note…")),
                        cols="2",
                        gap="lg",
                    )
                ),
            ),
            _section(
                "Choices",
                "Single and multi-choice controls should be obvious without visual noise.",
                Card(
                    Grid(
                        RadioGroup(
                            ["Starter", "Pro", "Enterprise"],
                            name="plan",
                            value="Pro",
                            label="Plan",
                        ),
                        CheckboxGroup(
                            ["Email", "Push", "SMS"],
                            name="channels",
                            values=("Email", "Push"),
                            label="Notifications",
                        ),
                        Combobox(
                            ["Brazil", "Portugal", "United States"],
                            name="country",
                            value="Brazil",
                            label="Country",
                        ),
                        MultiSelect(
                            ["Python", "Rust", "TypeScript", "Flutter"],
                            name="skills",
                            values=("Python", "Rust"),
                            label="Skills",
                        ),
                        cols="2",
                        gap="lg",
                    )
                ),
            ),
            _section(
                "Date, time and files",
                "Native platform capabilities should still feel like one design system.",
                Card(
                    Grid(
                        Field("Start date", DatePicker(name="start_date")),
                        Field("Start time", TimePicker(name="start_time")),
                        FileUpload(name="attachment", label="Choose attachment"),
                        DropZone(
                            name="assets",
                            label="Drop assets here or browse",
                            description="PNG, JPG or PDF up to your application limit.",
                            multiple=True,
                        ),
                        cols="2",
                        gap="lg",
                    )
                ),
            ),
            _section(
                "Specialized controls",
                "Verification, ranges, validation and compact choice controls use the same visual contract.",
                Card(
                    Grid(
                        OTPInput(name="code", length=6, label="Verification code"),
                        RangeSlider(name="budget", min_value=20, max_value=80, minimum=0, maximum=100),
                        Autocomplete(
                            name="framework",
                            suggestions=["Voodoo", "Python", "Rust"],
                            label="Technology",
                        ),
                        Stack(
                            CheckboxInput(
                                label="Enable previews",
                                description="Receive early visual-system updates.",
                                checked=True,
                            ),
                            RadioInput(
                                label="Stable channel",
                                description="Prefer release-quality components.",
                                value="stable",
                                name="channel",
                                checked=True,
                            ),
                            gap="md",
                        ),
                        cols="2",
                        gap="lg",
                    ),
                    FormValidationSummary(
                        errors=[
                            FormError("Project name is required", field_id="project"),
                            FormError("Choose a valid environment", field_id="environment"),
                        ],
                        title="Review these fields",
                    ),
                ),
            ),
            _section(
                "Complete form",
                "The common path should require composition, not browser plumbing.",
                Form(
                    Stack(
                        Field("Project name", Input(name="project", placeholder="Atlas"), required=True),
                        Switch(
                            "Public project",
                            description="Allow anyone in the workspace to discover it.",
                            checked=True,
                        ),
                        gap="lg",
                    ),
                    on_submit=_noop,
                    submit="Create project",
                ),
            ),
            gap="xxxl",
        ),
        size="xl",
    )


@page("/navigation")
def navigation():
    menu = DropdownMenu(
        Button("Actions", variant="secondary"),
        MenuItem("Rename", shortcut="R"),
        MenuItem("Duplicate", shortcut="D"),
        MenuSeparator(),
        MenuItem("Delete", destructive=True),
        label="Project actions",
        align="end",
    )
    return Page(
        Stack(
            _header("/navigation"),
            _section(
                "Location and paging",
                "Navigation should communicate position without dominating the content.",
                Breadcrumb(
                    BreadcrumbItem("Workspace", "/"),
                    BreadcrumbItem("Projects", "/"),
                    BreadcrumbItem("Voodoo", current=True),
                ),
                Pagination(total_pages=12, current_page=5, on_change=_noop),
                Stepper(
                    Step("Account", description="Identity"),
                    Step("Workspace", description="Team details"),
                    Step("Finish", description="Review"),
                    current=1,
                ),
            ),
            _section(
                "Tabs",
                "Tabs need strong keyboard semantics and restrained active styling.",
                Tabs(
                    Tab("overview", "Overview", Card(Text("Overview content"))),
                    Tab("activity", "Activity", Card(Text("Activity content"))),
                    Tab("settings", "Settings", Card(Text("Settings content"))),
                    value="overview",
                    on_change=_noop,
                ),
            ),
            _section(
                "Contextual actions",
                "Menus, popovers and tooltips should feel anchored and predictable.",
                Flex(
                    menu,
                    Popover(
                        Button("Popover", variant="outline"),
                        Stack(
                            Heading("Context", level=3, size="sm"),
                            Text("A lightweight contextual surface.", tone="muted"),
                            gap="xs",
                        ),
                    ),
                    Tooltip(Button("Hover or focus", variant="ghost"), "Helpful context"),
                    gap="md",
                    wrap="wrap",
                ),
            ),
            _section(
                "Disclosure",
                "Content density should be manageable without custom scripting.",
                Accordion(
                    AccordionItem(
                        "What is Voodoo Store?",
                        Text("The zero-config durable substrate for the Runtime."),
                        open=True,
                    ),
                    AccordionItem(
                        "Can I use PostgreSQL?",
                        Text("Yes. External infrastructure remains an explicit adapter."),
                    ),
                    variant="contained",
                ),
                Flex(Text("Shortcut"), Kbd("⌘"), Kbd("K"), gap="xs", items="center"),
            ),
            gap="xxxl",
        ),
        size="xl",
    )


@page("/feedback")
def feedback():
    return Page(
        Stack(
            _header("/feedback"),
            _section(
                "Alerts",
                "Tone should change meaning without changing the component's visual language.",
                Stack(
                    Alert("A neutral informational message.", title="Information", tone="info"),
                    Alert("Everything completed successfully.", title="Success", tone="success"),
                    Alert("Review this before continuing.", title="Warning", tone="warning"),
                    Alert("Something needs attention.", title="Error", tone="danger"),
                    gap="md",
                ),
            ),
            _section(
                "Progress",
                "Loading feedback should work from subtle inline state to explicit progress.",
                Card(
                    Stack(
                        Progress(24, tone="primary", label="Primary progress"),
                        Progress(58, tone="success", label="Success progress"),
                        Progress(82, tone="warning", label="Warning progress"),
                        Progress(None, label="Indeterminate progress"),
                        Flex(Spinner(size="sm"), Spinner(), Spinner(size="lg"), gap="lg", items="center"),
                        gap="lg",
                    )
                ),
            ),
            gap="xxxl",
        ),
        size="xl",
    )


@page("/advanced")
def advanced():
    alert_dialog = AlertDialog(
        "The resource will be permanently removed.",
        title="Delete resource?",
        cancel_label="Cancel",
        confirm_label="Delete",
        tone="danger",
        on_confirm=_noop,
        id="lab-delete-dialog",
    )
    return Page(
        Stack(
            _header("/advanced"),
            _section(
                "Interaction kernel",
                "High-interaction controls should feel native, quiet and keyboard-ready.",
                Card(
                    Stack(
                        ToggleGroup(
                            ToggleItem(value="bold", label="Bold"),
                            ToggleItem(value="italic", label="Italic"),
                            ToggleItem(value="underline", label="Underline"),
                            value=["bold"],
                            type="multiple",
                            on_change=_noop,
                        ),
                        SegmentedControl(
                            Segment("day", label="Day"),
                            Segment("week", label="Week"),
                            Segment("month", label="Month"),
                            value="week",
                            on_change=_noop,
                        ),
                        AlertDialogTrigger("Delete resource", target=alert_dialog),
                        alert_dialog,
                        gap="lg",
                    )
                ),
            ),
            _section(
                "Command and context surfaces",
                "Transient surfaces share one elevation, border and focus language.",
                Grid(
                    CommandPalette(
                        CommandGroup(
                            "Actions",
                            Command("Open project", shortcut="⌘O"),
                            Command("Search files", shortcut="⌘P"),
                            Command("Settings", shortcut="⌘,"),
                        ),
                        placeholder="Type a command…",
                    ),
                    ContextMenu(
                        Card(Text("Right-click this surface"), variant="outline"),
                        MenuGroup(
                            MenuItem("Open"),
                            MenuItem("Duplicate"),
                            SubMenu("Share", MenuItem("Email"), MenuItem("Copy link")),
                            label="Actions",
                        ),
                        MenuCheckboxItem("Show details", checked=True),
                        MenuRadioItem("Comfortable", value="comfortable", checked=True),
                        MenuRadioItem("Compact", value="compact"),
                    ),
                    cols="2",
                    gap="lg",
                ),
            ),
            _section(
                "Mobile actions",
                "Sheets must preserve hierarchy and comfortable touch targets.",
                Flex(
                    ActionSheet(
                        Action("Edit", on_select=_noop),
                        Action("Duplicate", on_select=_noop),
                        Action("Delete", destructive=True, on_select=_noop),
                        title="Project actions",
                    ),
                    BottomSheet(
                        Text("A compact contextual workflow for small screens."),
                        title="Quick settings",
                    ),
                    gap="lg",
                    wrap="wrap",
                ),
            ),
            gap="xxxl",
        ),
        size="xl",
    )


@page("/data")
def data():
    rows = [
        {"name": "Voodoo", "status": "Healthy", "latency": "42 ms"},
        {"name": "Store", "status": "Healthy", "latency": "8 ms"},
        {"name": "Edge", "status": "Degraded", "latency": "96 ms"},
    ]
    return Page(
        Stack(
            _header("/data"),
            _section(
                "Metrics",
                "Dense data should remain calm and scannable.",
                StatGroup(
                    DataStat("Requests", "12.8k", change="+8%", trend="up"),
                    DataStat("Latency", "42 ms", change="-12%", trend="down"),
                    DataStat("Errors", "0.08%", change="-0.02%", trend="down"),
                    columns=3,
                ),
            ),
            _section(
                "Tables",
                "Simple and advanced tables share row rhythm, hover and boundary treatment.",
                DataTable(
                    [
                        Column("name", "Service"),
                        Column("status", "Status"),
                        Column("latency", "Latency", align="end"),
                    ],
                    rows,
                    row_key="name",
                    on_select=_noop,
                ),
                EnhancedDataTable(
                    columns=[
                        ColumnDef("name", "Service", sortable=True, pinned="left"),
                        ColumnDef("status", "Status", filterable=True),
                        ColumnDef("latency", "Latency", sortable=True, align="right"),
                    ],
                    rows=rows,
                    label="Runtime services",
                    on_sort=_noop,
                    on_row_click=_noop,
                ),
            ),
            _section(
                "Structured details",
                "Property sheets and dense metadata should never look like raw debug output.",
                Grid(
                    DescriptionList(
                        DescriptionItem("Application", "component-lab"),
                        DescriptionItem("Runtime", "healthy"),
                        DescriptionSection(
                            "Store",
                            DescriptionItem("Provider", "voodoo"),
                            DescriptionItem("Path", ".voodoo/application.vstore"),
                        ),
                        label="Application details",
                    ),
                    DataList(
                        DataRow("HTTP Method", "GET", monospace=True),
                        DataRow("Status", "200 OK", highlight=True),
                        DataRow("Latency", "42ms"),
                        DataRow("Trace", "7f9a2d", monospace=True, copyable=True),
                        label="Request metadata",
                        striped=True,
                    ),
                    cols="2",
                    gap="lg",
                ),
            ),
            _section(
                "Selection and activity",
                "Lists, timelines, logs and inspectors are product surfaces, not debug leftovers.",
                Grid(
                    ListBox(
                        ListOption("Python", selected=True, description="Application language"),
                        ListOption("Rust", description="Store core"),
                        ListOption("TypeScript", description="Optional integration"),
                        label="Languages",
                        on_select=_noop,
                    ),
                    Timeline(
                        EventRow("Runtime started", timestamp="09:42", status="completed"),
                        EventRow("Store verified", timestamp="09:42", status="completed"),
                        EventRow("Agent waiting", timestamp="09:43", status="running"),
                    ),
                    cols="2",
                    gap="lg",
                ),
                LogViewer(["runtime ready", "store verified", "listening on :8000"]),
                InspectorPanel(
                    "Runtime context",
                    Metric("Executions", "24"),
                    description="Canonical operational state",
                    open=True,
                ),
            ),
            gap="xxxl",
        ),
        size="xl",
    )


@page("/workspace")
def workspace():
    return Page(
        Stack(
            _header("/workspace"),
            _section(
                "Desktop chrome",
                "Complex desktop surfaces still follow the same restrained product language.",
                Menubar(
                    MenubarMenu(
                        "File",
                        MenubarItem("New", shortcut="⌘N"),
                        MenubarItem("Open", shortcut="⌘O"),
                        MenubarSeparator(),
                        MenubarItem("Close"),
                    ),
                    MenubarMenu(
                        "Edit",
                        MenubarItem("Undo", shortcut="⌘Z"),
                        MenubarItem("Redo", shortcut="⇧⌘Z"),
                    ),
                ),
                Toolbar(
                    ToolbarGroup(
                        ToolbarButton("Bold", pressed=True),
                        ToolbarButton("Italic"),
                    ),
                    ToolbarSeparator(),
                    ToolbarGroup(ToolbarButton("Share")),
                ),
            ),
            _section(
                "Resizable workspace",
                "Panels and trees should feel like one coherent desktop environment.",
                ResizablePanels(
                    Panel(
                        "navigation",
                        children=[
                            TreeView(
                                TreeNode(
                                    "src",
                                    children=[
                                        TreeNode("runtime"),
                                        TreeNode("ui", selected=True),
                                        TreeNode("storage"),
                                    ],
                                ),
                                TreeNode("tests"),
                                label="Project files",
                            )
                        ],
                    ),
                    Panel(
                        "content",
                        children=[
                            ScrollArea(
                                Stack(
                                    Heading("Design System", level=2, size="md"),
                                    Text(
                                        "Workspace components inherit the same tokens, focus and surface hierarchy.",
                                        tone="muted",
                                    ),
                                    Card(Text("Editor/content surface"), variant="outline"),
                                    gap="lg",
                                )
                            )
                        ],
                    ),
                ),
            ),
            _section(
                "Master-detail",
                "Selection patterns keep the active item obvious without heavy decoration.",
                MasterDetail(
                    master=MasterList(
                        MasterItem("Runtime", selected=True),
                        MasterItem("Store"),
                        MasterItem("UI"),
                    ),
                    detail=DetailPane(
                        Stack(
                            Heading("Runtime", level=3, size="sm"),
                            Text("Canonical execution and application lifecycle.", tone="muted"),
                            gap="sm",
                        )
                    ),
                ),
            ),
            _section(
                "Dock and shortcuts",
                "Secondary utilities can be expressive without breaking visual restraint.",
                Dock(
                    DockItem(icon="⌘", label="Command"),
                    DockItem(icon="◎", label="Runtime", badge=2),
                    DockItem(icon="◇", label="Store"),
                ),
                KeyboardShortcutRegistry(
                    KeyBinding("Command palette", "⌘K"),
                    KeyBinding("Search", "⌘P"),
                    KeyBinding("Save", "⌘S"),
                    label="Workspace shortcuts",
                    visible=True,
                ),
            ),
            gap="xxxl",
        ),
        size="xl",
    )


@page("/system")
def system():
    agent = SimpleNamespace(
        id="agent-1",
        name="Operations Agent",
        status="running",
        model="provider:model",
        capabilities=["world.read", "device.command"],
    )
    device = {
        "id": "edge-1",
        "name": "Workshop Node",
        "status": "online",
        "capabilities": ["temperature.read", "motor.control"],
        "updated_at": "now",
    }
    execution = SimpleNamespace(
        id="exec-1",
        status=SimpleNamespace(value="completed"),
        intent=SimpleNamespace(name="device.inspect"),
        duration_seconds=0.42,
        created_at="now",
    )
    entity = {
        "id": "robot-1",
        "type": "robot",
        "properties": {"battery.level": 0.82, "mode": "idle"},
        "relationship_count": 3,
        "observation_count": 14,
    }
    return Page(
        Stack(
            _header("/system"),
            _section(
                "Runtime",
                "Voodoo's own concepts deserve the same product-grade presentation as ordinary app UI.",
                RuntimeStatus(
                    {
                        "summary": {
                            "executions": 24,
                            "active_executions": 2,
                            "waiting_executions": 1,
                            "failed_executions": 0,
                            "pending_approvals": 1,
                            "entities": 8,
                        }
                    }
                ),
                Grid(
                    AgentStatus(agent),
                    DeviceCard(device),
                    EdgeNode(device),
                    cols="3",
                    gap="lg",
                ),
            ),
            _section(
                "Execution and human control",
                "Operational truth, policy and approval surfaces stay readable under pressure.",
                ExecutionStatus(execution),
                ExecutionTimeline([execution]),
                ApprovalCard(
                    {
                        "id": "ap-1",
                        "reason": "Refund needs review",
                        "capability": "refund.issue",
                    },
                    on_approve=_noop,
                    on_deny=_noop,
                ),
                PolicyDecision(
                    {
                        "decision": "waiting",
                        "reason": "Human approval required",
                        "capability": "refund.issue",
                    }
                ),
            ),
            _section(
                "World and telemetry",
                "Observed state, capability and metrics share one information hierarchy.",
                Grid(
                    WorldEntityInspector(entity),
                    ObservationFeed(
                        [
                            {
                                "property": "battery.level",
                                "value": 0.82,
                                "source": "bms",
                                "confidence": 0.99,
                                "observed_at": "now",
                            }
                        ]
                    ),
                    cols="2",
                    gap="lg",
                ),
                CapabilityList(["world.read", {"name": "device.command"}]),
                TelemetryPanel({"cpu_usage": "12%", "latency_ms": 8, "queue_depth": 2}),
            ),
            gap="xxxl",
        ),
        size="xl",
    )


if __name__ == "__main__":
    app.run()
