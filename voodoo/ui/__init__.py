"""The Voodoo UI system: component model, library, and style adapters.

Import the component library from here::

    from voodoo.ui import Button, Card, Page

Styling is pluggable — swap the CSS framework without touching components::

    from voodoo.ui import set_style_adapter, NoopAdapter
    set_style_adapter(NoopAdapter())
"""

from voodoo.ui.component import Component, Html, escape
from voodoo.ui.library import (
    A,
    Address,
    Article,
    Aside,
    AuthGuard,
    Avatar,
    Badge,
    Button,
    Card,
    ChatBox,
    Checkbox,
    Container,
    Dialog,
    Div,
    Divider,
    FigCaption,
    Figure,
    Flex,
    Footer,
    Form,
    Grid,
    Header,
    Heading,
    Img,
    Input,
    Label,
    List,
    ListItem,
    LoginForm,
    Main,
    Modal,
    Nav,
    Option,
    Page,
    Paragraph,
    Radio,
    RegisterForm,
    Section,
    Select,
    Table,
    Text,
    Textarea,
    Time,
    UserBadge,
)
from voodoo.ui.styles import (
    NoopAdapter,
    StyleAdapter,
    current_adapter,
    set_style_adapter,
)

__all__ = [
    # Component model
    "Component",
    "Html",
    "escape",
    # Style adapters
    "StyleAdapter",
    "NoopAdapter",
    "set_style_adapter",
    "current_adapter",
    # Layout
    "Div",
    "Flex",
    "Grid",
    "Container",
    "Page",
    # Core elements
    "A",
    "Button",
    "Card",
    "Text",
    "Heading",
    "Badge",
    "Avatar",
    "Divider",
    "Dialog",
    "Modal",
    # Forms
    "Form",
    "Label",
    "Input",
    "Textarea",
    "Select",
    "Option",
    "Checkbox",
    "Radio",
    # Collections
    "Table",
    "List",
    "ListItem",
    "ChatBox",
    # Semantic structure
    "Nav",
    "Header",
    "Footer",
    "Main",
    "Section",
    "Article",
    "Aside",
    "Figure",
    "FigCaption",
    "Address",
    "Paragraph",
    "Time",
    "Img",
    # Auth UI
    "LoginForm",
    "RegisterForm",
    "UserBadge",
    "AuthGuard",
]
