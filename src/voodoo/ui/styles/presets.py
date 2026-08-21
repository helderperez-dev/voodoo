"""Theme presets: shareable, JSON-serializable theme packages.

A preset is a ``theme.json`` document that fully describes a theme using the
token-first format (the same shape ``Theme`` produces). Presets make a theme
portable, installable, and swappable without touching application code.

Resolution order (first match wins):

1. An explicit path or URL.
2. The project preset at ``.voodoo/theme/theme.json``.
3. A named built-in preset (``default``, ``ember-paper``).
4. A user-installed preset at ``~/.voodoo/themes/<name>/theme.json``.
5. A PyPI package named ``voodoo-theme-<name>`` exposing ``theme.json``.

Theme-specific CSS lives in a **sibling** ``custom.css`` file (never embedded
in JSON) so editors and linters treat it as first-class CSS.
"""

from __future__ import annotations

import importlib.util
import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from voodoo.core.errors import ConfigurationError
from voodoo.ui.styles.theme import Theme, set_theme

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ThemePreset(BaseModel):
    """A theme package: metadata plus a token-first theme definition.

    ``theme`` is the same shape ``Theme.model_dump()`` produces, so a preset
    round-trips losslessly through JSON.
    """

    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    theme: Theme


@dataclass(frozen=True)
class ThemeSource:
    """A resolved theme plus its origin and optional sibling custom CSS."""

    theme: Theme
    origin: str
    custom_css: str = ""


# ---------------------------------------------------------------------------
# Internal state
# ---------------------------------------------------------------------------

_active_custom_css: str = ""

# Built-in presets are lazy (registered by name → factory) so importing this
# module does not pay for heavy font/color tables until a preset is requested.
_BUILTINS: dict[str, Any] = {}


def register_builtin(name: str, factory: Any) -> None:
    """Register a built-in preset factory by name."""
    _BUILTINS[name] = factory


def list_presets() -> list[dict[str, str]]:
    """Return the names and descriptions of all discoverable presets."""
    result: list[dict[str, str]] = []
    for name in sorted(_BUILTINS):
        try:
            preset = _load_builtin(name)
        except ConfigurationError:
            continue
        result.append(
            {
                "name": preset.name,
                "version": preset.version,
                "description": preset.description,
                "source": "builtin",
            }
        )
    user_dir = _user_themes_dir()
    if user_dir.is_dir():
        for child in sorted(user_dir.iterdir()):
            theme_file = child / "theme.json"
            if not theme_file.is_file():
                continue
            try:
                preset = _load_from_file(theme_file)
            except ConfigurationError:
                continue
            result.append(
                {
                    "name": preset.name,
                    "version": preset.version,
                    "description": preset.description,
                    "source": str(child),
                }
            )
    return result


# ---------------------------------------------------------------------------
# Loading primitives
# ---------------------------------------------------------------------------


def _load_from_file(path: Path) -> ThemePreset:
    """Parse and validate a ``theme.json`` file."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"Could not read theme preset {path}: {exc}") from exc
    return _load_from_dict(data, origin=str(path))


def _load_from_dict(data: dict[str, Any], *, origin: str = "<dict>") -> ThemePreset:
    """Validate a theme preset dict."""
    try:
        return ThemePreset(**data)
    except ValidationError as exc:
        raise ConfigurationError(f"Invalid theme preset ({origin}): {exc}") from exc


def _load_builtin(name: str) -> ThemePreset:
    factory = _BUILTINS.get(name)
    if factory is None:
        raise ConfigurationError(
            f"Unknown built-in theme preset '{name}'. "
            f"Available: {', '.join(sorted(_BUILTINS)) or 'none'}."
        )
    preset = factory()
    if isinstance(preset, ThemePreset):
        return preset
    # Factory may return a raw dict for laziness.
    return _load_from_dict(preset, origin=f"builtin:{name}")


def _read_custom_css(directory: Path) -> str:
    """Read a sibling ``custom.css`` if present."""
    candidate = directory / "custom.css"
    try:
        return candidate.read_text(encoding="utf-8")
    except OSError:
        return ""


def _load_from_dir(directory: Path) -> ThemeSource:
    theme_file = directory / "theme.json"
    if not theme_file.is_file():
        raise ConfigurationError(
            f"Theme preset directory {directory} has no theme.json."
        )
    preset = _load_from_file(theme_file)
    return ThemeSource(
        theme=preset.theme,
        origin=str(directory),
        custom_css=_read_custom_css(directory),
    )


def _load_from_url(url: str) -> ThemeSource:
    """Fetch a ``theme.json`` (and optional sibling custom.css) over HTTP."""
    try:
        with urllib.request.urlopen(url) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise ConfigurationError(f"Could not load theme from {url}: {exc}") from exc
    preset = _load_from_dict(data, origin=url)
    # Custom CSS is fetched from a sibling ``custom.css`` next to the JSON URL.
    base = url.rsplit("/", 1)[0]
    custom_css = ""
    try:
        with urllib.request.urlopen(f"{base}/custom.css") as resp:  # noqa: S310
            custom_css = resp.read().decode("utf-8")
    except OSError:
        custom_css = ""
    return ThemeSource(theme=preset.theme, origin=url, custom_css=custom_css)


def _load_from_pypi(name: str) -> ThemeSource:
    module_name = f"voodoo_theme_{name.replace('-', '_')}"
    try:
        spec = importlib.util.find_spec(module_name)
    except (ImportError, ValueError):
        spec = None
    if spec is None or spec.origin is None:
        raise ConfigurationError(
            f"Theme preset '{name}' is not installed. "
            f"Install it with 'voodoo theme install {name}'."
        )
    directory = Path(spec.origin).parent
    return _load_from_dir(directory)


def _user_themes_dir() -> Path:
    return Path.home() / ".voodoo" / "themes"


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def resolve_theme(
    preset: str | None = None, *, project_root: str | None = None
) -> ThemeSource:
    """Resolve a theme preset to a concrete :class:`ThemeSource`.

    Args:
        preset: Optional preset name, path, or URL. When ``None``, the project
            preset (``.voodoo/theme/theme.json``) is used, falling back to the
            built-in ``default``.
        project_root: Root directory for project-scoped discovery. Defaults to
            the current working directory.
    """
    root = Path(project_root) if project_root else Path.cwd()

    if preset:
        if preset.startswith(("http://", "https://")):
            return _load_from_url(preset)
        candidate = Path(preset).expanduser()
        if candidate.is_file() and candidate.suffix == ".json":
            return _load_from_dir(candidate.parent)
        if candidate.is_dir():
            return _load_from_dir(candidate)
        if preset in _BUILTINS:
            return _load_builtin_source(preset)
        user_dir = _user_themes_dir() / preset
        if (user_dir / "theme.json").is_file():
            return _load_from_dir(user_dir)
        return _load_from_pypi(preset)

    project_theme = root / ".voodoo" / "theme"
    if (project_theme / "theme.json").is_file():
        return _load_from_dir(project_theme)
    return _load_builtin_source("default")


def _load_builtin_source(name: str) -> ThemeSource:
    preset = _load_builtin(name)
    return ThemeSource(theme=preset.theme, origin=f"builtin:{name}")


def activate_theme(
    preset: str | None = None,
    *,
    project_root: str | None = None,
    mode: str | None = None,
) -> Theme:
    """Resolve, install, and return the active theme.

    Installs the resolved theme as the global ``default_theme`` (so rendering,
    adapters, and component tone resolution all observe it) and caches any
    sibling ``custom.css`` for ``render_page`` to inject.

    Args:
        preset: Optional preset name, path, or URL.
        project_root: Root directory for project-scoped discovery.
        mode: Optional top-level mode override. Only applied to the built-in
            default (presets are self-describing, including their mode).
    """
    global _active_custom_css
    source = resolve_theme(preset, project_root=project_root)
    theme = source.theme
    if mode is not None and preset is None and source.origin == "builtin:default":
        theme = theme.model_copy(update={"mode": mode})
    _active_custom_css = source.custom_css
    set_theme(theme)
    return theme


def get_active_custom_css() -> str:
    """Return the cached custom CSS for the active theme (``""`` if none)."""
    return _active_custom_css


# ---------------------------------------------------------------------------
# Built-in presets
# ---------------------------------------------------------------------------

# ``default`` is the stock token set; the factory is trivial because Theme() is
# already the canonical zero-config theme.
register_builtin(
    "default",
    lambda: ThemePreset(
        name="default", description="Voodoo default theme", theme=Theme()
    ),
)


def _ember_paper_theme() -> Theme:
    """Build the warm "ember-paper" theme (editorial serif + ember accent).

    Font families reference the faces by name with graceful system fallbacks;
    the actual webfonts are the theme author's responsibility (self-host or
    load via ``.voodoo/theme/custom.css``) so the built-in stays zero-network.
    """
    from voodoo.ui.styles.theme import ThemeColors, ThemeTypography

    colors = ThemeColors(
        # Ember accent (amber in dark mode, burnt ember in light mode).
        secondary="#E8A33D",
        light_secondary="#B45309",
        on_secondary="#0F0D0B",
        light_on_secondary="#FFFFFF",
        # Warm paper surfaces — dark.
        primary="#F5EFE6",
        primary_hover="#E7DED2",
        background="#0F0D0B",
        surface="#171412",
        surface_raised="#221D19",
        text="#F5EFE6",
        text_muted="#A39A8C",
        border="#26211D",
        on_primary="#0F0D0B",
        # Warm paper surfaces — light.
        light_primary="#1C1917",
        light_primary_hover="#2E2823",
        light_background="#FBF7F0",
        light_surface="#F4EDE1",
        light_surface_raised="#ECE2D3",
        light_text="#1C1917",
        light_text_muted="#6E645A",
        light_border="#E2D8C8",
        light_on_primary="#FBF7F0",
    )
    typography = ThemeTypography(
        font_family=(
            '"Schibsted Grotesk", -apple-system, BlinkMacSystemFont, '
            '"Segoe UI", Roboto, Helvetica, Arial, sans-serif'
        ),
        mono_family=(
            '"IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, '
            'Consolas, "Courier New", monospace'
        ),
        display_family='"Fraunces", Georgia, "Times New Roman", serif',
    )
    return Theme(
        mode="dark",
        colors=colors,
        typography=typography,
        extra_tokens={
            # A soft ember halo for theme-specific chrome (used by custom.css).
            "glow": (
                "0 0 0 1px "
                "color-mix(in srgb, var(--vd-color-secondary) 30%, transparent), "
                "0 10px 40px -12px "
                "color-mix(in srgb, var(--vd-color-secondary) 45%, transparent)"
            ),
        },
    )


register_builtin(
    "ember-paper",
    lambda: ThemePreset(
        name="ember-paper",
        description=(
            "Warm paper aesthetic with an ember accent and editorial serif "
            "display type."
        ),
        theme=_ember_paper_theme(),
    ),
)


__all__ = [
    "ThemePreset",
    "ThemeSource",
    "activate_theme",
    "get_active_custom_css",
    "list_presets",
    "register_builtin",
    "resolve_theme",
]
