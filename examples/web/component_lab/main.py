"""Voodoo Component Lab — visual and behavioral acceptance application.

Run:
    voodoo dev examples.web.component_lab.main:app

The lab intentionally uses only public Voodoo APIs and no application CSS.
It is the canonical surface for visual review, interaction checks and future
browser screenshot regression tests.
"""

from __future__ import annotations

from voodoo import App, page
from voodoo.ui import (
    A,
    Accordion,
    AccordionItem,
    Alert,
    Badge,
    Breadcrumb,
    BreadcrumbItem,
    Button,
    ButtonGroup,
    Card,
    CheckboxGroup,
    Combobox,
    Container,
    DatePicker,
    DropZone,
    EmptyState,
    Field,
    FileUpload,
    Flex,
    Form,
    Grid,
    Heading,
    Input,
    Kbd,
    Metric,
    MultiSelect,
    NumberInput,
    Page,
    Pagination,
    PasswordInput,
    Popover,
    Progress,
    RadioGroup,
    SearchInput,
    Skeleton,
    Slider,
    Spinner,
    Stack,
    StatusBadge,
    Step,
    Stepper,
    Switch,
    Tab,
    Tabs,
    Text,
    Textarea,
    ThemeToggle,
    TimePicker,
    Tooltip,
    DropdownMenu,
    MenuItem,
    MenuSeparator,
)

app = App()


async def _noop(*_args, **_kwargs):
    return None


def _header(active: str) -> Card:
    links = [
        ("Overview", "/"),
        ("Forms", "/forms"),
        ("Navigation", "/navigation"),
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


if __name__ == "__main__":
    app.run()
