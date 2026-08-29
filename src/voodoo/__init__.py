"""Voodoo — the programmable runtime for adaptive applications and
operational systems.

The public API is intentionally small (~40 names). Everything else lives in
its defining submodule (e.g. ``voodoo.auth``, ``voodoo.seo``) and legacy
top-level imports resolve through a deprecation shim (PEP 562).

The computational model — the fundamental ontology from which all
higher-level capabilities emerge — lives in ``voodoo.primitives``:

    from voodoo.primitives import State, Capability, Intent, Effect
    from voodoo.primitives import TimeSpec, ComputeSpec, Resource, Constraint

    ENTITY → STATE → INTENT → CAPABILITY → EXECUTION → EFFECT → STATE
    TIME + CONSTRAINT surround the entire lifecycle.
"""

import importlib
import warnings
from typing import Any

from .adapters import TailwindAdapter, VoodooCSSAdapter
from .agents import AgentEntity, AgentRegistry, AgentRunRecord, SQLiteAgentRegistry
from .ai import LLMProvider, ModelDescriptor, VoodooModelProvider
from .ai.agent import Agent, AgentRun
from .ai.tools import ToolRegistry, ToolSpec, tool
from .config import config
from .core import App, create_app, event, page, register_event, state, ws_manager
from .data import FK, BaseModel, Model
from .memory import MemoryEntry, MemoryLayer, MemoryStore, SQLiteMemoryStore
from .mesh import mesh
from .routing.api import api
from .telemetry import trace
from .ui import (
    A,
    Article,
    Avatar,
    BackLink,
    Badge,
    Box,
    Brand,
    Button,
    Card,
    ChatMessage,
    Checkbox,
    Chip,
    CodeBlock,
    Component,
    Composer,
    Container,
    CTABand,
    Dialog,
    Div,
    Divider,
    Eyebrow,
    FeatureCard,
    Flex,
    Footer,
    Form,
    Grid,
    Header,
    Heading,
    Hero,
    Html,
    Icon,
    Input,
    Label,
    Link,
    LinkArrow,
    List,
    ListItem,
    Main,
    Markdown,
    MessageList,
    Modal,
    Nav,
    Navbar,
    NavLink,
    Option,
    Page,
    PageHero,
    Radio,
    Section,
    Select,
    Sidebar,
    Stack,
    Stat,
    Stats,
    StreamingText,
    Table,
    Text,
    Textarea,
    ThemeToggle,
)
from .ui.state import State
from .ui.styles import (
    NoopAdapter,
    StyleAdapter,
    current_adapter,
    set_style_adapter,
)
from .ui.styles.theme import Theme, ThemeColors, create_theme
from .workers import task

__version__ = "2.2.0"

__all__ = [
    # Core runtime
    "App",
    "create_app",
    "page",
    "api",
    "trace",
    # Reactive state & events
    "state",
    "event",
    "State",
    # Realtime
    "mesh",
    "register_event",
    "ws_manager",
    # Workers
    "task",
    # AI (full provider abstraction lands with the AI sprints)
    "Agent",
    "AgentRun",
    "tool",
    "ToolSpec",
    "ToolRegistry",
    "LLMProvider",
    "VoodooModelProvider",
    "ModelDescriptor",
    # Memory (Sprint 16)
    "MemoryEntry",
    "MemoryLayer",
    "MemoryStore",
    "SQLiteMemoryStore",
    # Agent registry (Sprint 17)
    "AgentEntity",
    "AgentRegistry",
    "AgentRunRecord",
    "SQLiteAgentRegistry",
    # Data
    "BaseModel",
    "Model",
    "FK",
    # Theming & configuration
    "Theme",
    "ThemeColors",
    "create_theme",
    "config",
    # Styling seam
    "StyleAdapter",
    "NoopAdapter",
    "TailwindAdapter",
    "VoodooCSSAdapter",
    "set_style_adapter",
    "current_adapter",
    # UI — layout
    "Component",
    "Div",
    "Flex",
    "Stack",
    "Grid",
    "Box",
    "Container",
    "Page",
    "A",
    "Link",
    # UI — core components
    "Button",
    "Card",
    "Text",
    "Heading",
    "Badge",
    "Avatar",
    "Divider",
    "Dialog",
    "Modal",
    # UI — icons & markdown
    "Icon",
    "Markdown",
    "Html",
    # UI — chat primitives
    "MessageList",
    "ChatMessage",
    "StreamingText",
    "Composer",
    "Sidebar",
    # UI — forms
    "Form",
    "Label",
    "Input",
    "Textarea",
    "Select",
    "Option",
    "Checkbox",
    "Radio",
    # UI — collections
    "Table",
    "List",
    "ListItem",
    # UI — semantic structure
    "Nav",
    "Header",
    "Footer",
    "Main",
    "Section",
    "Article",
    # UI — chrome
    "Navbar",
    "NavLink",
    "Brand",
    "ThemeToggle",
    "Hero",
    "PageHero",
    "Eyebrow",
    "Chip",
    "CodeBlock",
    "Stats",
    "Stat",
    "CTABand",
    "BackLink",
    "FeatureCard",
    "LinkArrow",
]

# ---------------------------------------------------------------------------
# Deprecation shims: legacy top-level imports resolve from their submodule.
# Removed only with a strong reason (not during the 1.0 cycle).
# ---------------------------------------------------------------------------

_DEPRECATED_EXPORTS: dict[str, str] = {
    # voodoo.auth
    "AuthError": "voodoo.auth",
    "AuthMiddleware": "voodoo.auth",
    "AuthUser": "voodoo.auth",
    "ExpiredTokenError": "voodoo.auth",
    "InvalidCredentialsError": "voodoo.auth",
    "InvalidTokenError": "voodoo.auth",
    "PermissionDeniedError": "voodoo.auth",
    "User": "voodoo.auth",
    "clear_auth_cookie": "voodoo.auth",
    "create_access_token": "voodoo.auth",
    "current_user": "voodoo.auth",
    "decode_access_token": "voodoo.auth",
    "generate_api_key": "voodoo.auth",
    "generate_secret_key": "voodoo.auth",
    "get_current_user": "voodoo.auth",
    "hash_api_key": "voodoo.auth",
    "hash_password": "voodoo.auth",
    "login_required": "voodoo.auth",
    "require_api_key": "voodoo.auth",
    "require_auth": "voodoo.auth",
    "require_roles": "voodoo.auth",
    "require_scopes": "voodoo.auth",
    "requires_api_key": "voodoo.auth",
    "requires_permission": "voodoo.auth",
    "requires_role": "voodoo.auth",
    "requires_roles": "voodoo.auth",
    "requires_scopes": "voodoo.auth",
    "set_auth_cookie": "voodoo.auth",
    "verify_api_key": "voodoo.auth",
    "verify_password": "voodoo.auth",
    # voodoo.components
    "Address": "voodoo.components",
    "Aside": "voodoo.components",
    "AuthGuard": "voodoo.components",
    "ChatBox": "voodoo.components",
    "FigCaption": "voodoo.components",
    "Figure": "voodoo.components",
    "Img": "voodoo.components",
    "LoginForm": "voodoo.components",
    "Paragraph": "voodoo.components",
    "RegisterForm": "voodoo.components",
    "Time": "voodoo.components",
    "UserBadge": "voodoo.components",
    # voodoo.config
    "AuthConfig": "voodoo.config",
    "SecurityConfig": "voodoo.config",
    "SEOConfig": "voodoo.config",
    # voodoo.data
    "get_db": "voodoo.data",
    "on_insert": "voodoo.data",
    "on_update": "voodoo.data",
    "rls_policy": "voodoo.data",
    # voodoo.i18n
    "I18n": "voodoo.i18n",
    "_": "voodoo.i18n",
    "i18n_instance": "voodoo.i18n",
    # voodoo.mcp
    "MCPClient": "voodoo.mcp",
    "mcp": "voodoo.mcp",
    # voodoo.queue
    "enqueue": "voodoo.queue",
    "queue": "voodoo.queue",
    # voodoo.schedule
    "schedule": "voodoo.schedule",
    # voodoo.security
    "CORSMiddleware": "voodoo.security",
    "CSRFMiddleware": "voodoo.security",
    "RateLimiter": "voodoo.security",
    "RateLimitMiddleware": "voodoo.security",
    "SecurityHeadersMiddleware": "voodoo.security",
    "generate_csrf_token": "voodoo.security",
    "rate_limiter": "voodoo.security",
    "set_csrf_cookie": "voodoo.security",
    "validate_password_strength": "voodoo.security",
    # voodoo.security — Sprint 19
    "SecretStore": "voodoo.security",
    "EnvSecretStore": "voodoo.security",
    "LocalSecretStore": "voodoo.security",
    "SecretsError": "voodoo.security",
    "secrets": "voodoo.security",
    "configure_secrets": "voodoo.security",
    "RedactionGuard": "voodoo.security",
    "redact": "voodoo.security",
    "redact_string": "voodoo.security",
    # voodoo.runtime — Sprint 19
    "SENSITIVE_CAPABILITIES": "voodoo.runtime.capability",
    # voodoo.seo
    "FAQ": "voodoo.seo",
    "GEO": "voodoo.seo",
    "SEO": "voodoo.seo",
    "OpenGraph": "voodoo.seo",
    "TwitterCard": "voodoo.seo",
    # voodoo.status
    "ServiceStatus": "voodoo.status",
    # voodoo.storage
    "storage": "voodoo.storage",
    # voodoo.telemetry
    "TelemetryMiddleware": "voodoo.telemetry",
    "telemetry_store": "voodoo.telemetry",
    # voodoo.theme
    "default_theme": "voodoo.theme",
    "set_theme": "voodoo.theme",
}


def __getattr__(name: str) -> Any:
    module_path = _DEPRECATED_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module 'voodoo' has no attribute {name!r}")
    value = getattr(importlib.import_module(module_path), name)
    warnings.warn(
        f"`from voodoo import {name}` is deprecated; "
        f"import it from `{module_path}` instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_DEPRECATED_EXPORTS))
