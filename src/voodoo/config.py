import os
import re
from collections.abc import Callable
from typing import Any, Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from voodoo.core.errors import ConfigurationError

# Load .env variables first
load_dotenv()

_ENV_VAR_PATTERN = re.compile(r"\$\{([^}:]+)(?::([^}]*))?\}")


def interpolate_env_vars(value: Any) -> Any:
    """Recursively interpolates ${VAR} or ${VAR:default} in strings, dicts, and lists."""
    if isinstance(value, str):

        def _replace(match: re.Match) -> str:
            var_name = match.group(1)
            default_val = match.group(2)
            val = os.getenv(var_name)
            if val is not None:
                return val
            if default_val is not None:
                return default_val
            return ""

        return _ENV_VAR_PATTERN.sub(_replace, value)
    elif isinstance(value, dict):
        return {k: interpolate_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [interpolate_env_vars(v) for v in value]
    return value


def _env_flag(name: str) -> bool | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _resolve_debug() -> bool:
    """Debug mode: explicit VOODOO_DEBUG wins; otherwise on unless production."""
    explicit = _env_flag("VOODOO_DEBUG")
    if explicit is not None:
        return explicit
    return os.getenv("VOODOO_ENV", "development") != "production"


def _resolve_db_path() -> str:
    """Database location: VOODOO_DB_PATH > DATABASE_URL > default.

    SQLite URLs are normalized to local paths; PostgreSQL URLs are passed
    through unchanged for the ``postgres`` database provider (Sprint 10),
    so ``VOODOO_DATABASE_URL``/``DATABASE_URL`` can point at a server
    without a separate ``database.url`` in ``voodoo.yaml``.
    """
    explicit = os.getenv("VOODOO_DB_PATH")
    if explicit:
        return explicit
    url = os.getenv("DATABASE_URL")
    if url:
        if url == "sqlite://":
            return ":memory:"
        if url.startswith("sqlite:///"):
            return url[len("sqlite:///") :] or ":memory:"
        scheme = url.split(":", 1)[0]
        if scheme in ("postgres", "postgresql"):
            # Pass through — consumed as ``database.url`` by the postgres
            # provider factory (see ``adapters/registry.py``). Kept in
            # ``db_path`` so ``get_config()`` still surfaces it.
            return url
        raise ConfigurationError(
            f"DATABASE_URL scheme '{scheme}://' is not supported yet. "
            "Use a sqlite:///... URL, a postgres://... URL (Sprint 10), "
            "or VOODOO_DB_PATH. Additional backends arrive as optional "
            "extras (e.g. voodoo[postgres]) in a later release."
        )
    return ".voodoo/state/data.db"


class SEOConfig(BaseModel):
    """SEO & GEO configuration for the Voodoo framework."""

    site_name: str = "Voodoo App"
    base_url: str = ""  # e.g., "https://example.com"
    default_og_image: str = ""
    sitemap_enabled: bool = True
    robots_enabled: bool = True
    allow_ai_crawlers: bool = True
    robots_disallow: list[str] = Field(
        default_factory=lambda: ["/_voodoo_ws", "/voodoo/mesh/ws"]
    )
    default_lang: str = "en"
    generator_meta: bool = True  # show Voodoo generator tag


class AuthConfig(BaseModel):
    """Authentication and identity configuration."""

    secret_key: str = Field(
        default_factory=lambda: os.getenv(
            "VOODOO_SECRET_KEY", "dev-secret-key-change-in-production-voodoo-2026"
        )
    )
    token_expiry_seconds: int = Field(
        default_factory=lambda: int(
            os.getenv("VOODOO_TOKEN_EXPIRY", str(7 * 24 * 3600))
        )  # 7 days
    )
    cookie_name: str = "voodoo_auth"
    cookie_secure: bool = Field(
        default_factory=lambda: os.getenv("VOODOO_ENV", "development") == "production"
    )
    cookie_httponly: bool = True
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    api_key_prefix: str = "vd_live"


class SecurityConfig(BaseModel):
    """Security headers, CORS, CSRF, and Rate Limiting configuration."""

    headers_enabled: bool = True
    hsts_enabled: bool = Field(
        default_factory=lambda: os.getenv("VOODOO_ENV", "development") == "production"
    )
    hsts_max_age: int = 31536000
    frame_options: str = "SAMEORIGIN"
    content_type_options: str = "nosniff"
    xss_protection: str = "1; mode=block"
    referrer_policy: str = "strict-origin-when-cross-origin"
    permissions_policy: str = ""  # e.g. "geolocation=(), microphone=()"
    csp_directives: dict[str, str] = Field(
        default_factory=lambda: {
            "default-src": "'self'",
            "script-src": "'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://unpkg.com",
            "style-src": "'self' 'unsafe-inline' https://unpkg.com https://fonts.googleapis.com",
            "font-src": "'self' data: https://fonts.gstatic.com",
            "img-src": "'self' data: https: blob:",
            "connect-src": "'self' ws: wss: http: https:",
            "frame-ancestors": "'self'",
        }
    )
    # CORS
    cors_enabled: bool = True
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = Field(default_factory=lambda: ["*"])
    cors_allow_headers: list[str] = Field(default_factory=lambda: ["*"])
    # CSRF
    csrf_enabled: bool = False
    csrf_cookie_name: str = "voodoo_csrf"
    csrf_header_name: str = "X-CSRF-Token"
    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # seconds


class RuntimeConfig(BaseModel):
    """Runtime operating mode and environment options."""

    mode: str = "development"


class ThemeConfig(BaseModel):
    """Design-token overrides (``theme:`` block in voodoo.yaml).

    Mirrors the configurable surface of ``voodoo.ui.styles.theme.Theme``.
    Values are passed through to ``set_theme``/``create_theme`` at
    runtime; arbitrary keys are allowed so sub-dictionaries forward.
    """

    mode: str = "dark"  # dark | light | system
    model_config = {"extra": "allow"}


class DatabaseConfig(BaseModel):
    """Database provider configuration."""

    provider: str = "sqlite"
    url: str = ""
    path: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


class QueueConfig(BaseModel):
    """Task queue provider configuration."""

    provider: str = "sqlite"
    url: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


class EventsConfig(BaseModel):
    """Event bus provider configuration."""

    provider: str = "sqlite"
    url: str = ""
    path: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


class ObjectsConfig(BaseModel):
    """Object store provider configuration."""

    provider: str = "local"
    bucket: str = ""
    endpoint: str = ""
    base_dir: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


class CacheConfig(BaseModel):
    """Cache provider configuration."""

    provider: str = "memory"
    url: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


class ModelsConfig(BaseModel):
    """AI model routing and default provider configuration."""

    default: str = "mock:default"
    aliases: dict[str, str] = Field(default_factory=dict)
    extra: dict[str, Any] = Field(default_factory=dict)


class VoodooConfig(BaseModel):
    """Core configuration for the Voodoo framework."""

    env: str = Field(default_factory=lambda: os.getenv("VOODOO_ENV", "development"))
    debug: bool = Field(default_factory=_resolve_debug)
    db_path: str = Field(default_factory=_resolve_db_path)
    storage_dir: str = Field(
        default_factory=lambda: os.getenv("VOODOO_STORAGE_DIR", "storage")
    )
    port: int = Field(default_factory=lambda: int(os.getenv("VOODOO_PORT", "8000")))
    host: str = Field(default_factory=lambda: os.getenv("VOODOO_HOST", "0.0.0.0"))

    # Provider & Runtime sub-blocks (Spec §31)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    queue: QueueConfig = Field(default_factory=QueueConfig)
    events: EventsConfig = Field(default_factory=EventsConfig)
    objects: ObjectsConfig = Field(default_factory=ObjectsConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    models: ModelsConfig = Field(default_factory=ModelsConfig)

    seo: SEOConfig = Field(default_factory=SEOConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    theme: ThemeConfig = Field(default_factory=ThemeConfig)
    extra: dict[str, Any] = Field(default_factory=dict)


def load_yaml_config(file_path: str = "voodoo.yaml") -> dict[str, Any]:
    """Loads configuration from a YAML file if it exists, with env interpolation."""
    if os.path.exists(file_path):
        with open(file_path) as f:
            try:
                raw_data = yaml.safe_load(f) or {}
                return interpolate_env_vars(raw_data)
            except yaml.YAMLError as e:
                print(f"Error parsing {file_path}: {e}")
    return {}


def load_toml_config(file_path: str = "voodoo.toml") -> dict[str, Any]:
    """Loads configuration from a TOML file if it exists, with env interpolation."""
    if os.path.exists(file_path):
        try:
            import tomllib

            with open(file_path, "rb") as f:
                raw_data = tomllib.load(f)
                return interpolate_env_vars(raw_data)
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
    return {}


def _build_database_config(file_data: dict[str, Any], db_path: str) -> DatabaseConfig:
    db_data = file_data.get("database") or {}
    if not isinstance(db_data, dict):
        db_data = {"provider": str(db_data)}
    db_provider = (
        db_data.get("provider") or os.getenv("VOODOO_DATABASE_PROVIDER") or "sqlite"
    )
    # ``db_path`` may carry a provider URL (sqlite:///… or postgres://…).
    # For server backends the URL is surfaced as ``database.url`` so the
    # provider factory can connect (Sprint 10).
    db_url = db_data.get("url") or ""
    if not db_url and db_path.startswith(("postgres://", "postgresql://", "sqlite://")):
        db_url = db_path
    return DatabaseConfig(
        provider=db_provider,
        url=db_url,
        path=db_data.get("path", db_path),
        extra={
            k: v for k, v in db_data.items() if k not in ("provider", "url", "path")
        },
    )


def _build_queue_config(file_data: dict[str, Any]) -> QueueConfig:
    queue_data = file_data.get("queue") or {}
    if not isinstance(queue_data, dict):
        queue_data = {"provider": str(queue_data)}
    queue_provider = (
        queue_data.get("provider") or os.getenv("VOODOO_QUEUE_PROVIDER") or "sqlite"
    )
    queue_url = queue_data.get("url") or os.getenv("VOODOO_QUEUE_URL") or ""
    return QueueConfig(
        provider=queue_provider,
        url=queue_url,
        extra={k: v for k, v in queue_data.items() if k not in ("provider", "url")},
    )


def _build_events_config(file_data: dict[str, Any], db_path: str) -> EventsConfig:
    events_data = file_data.get("events") or {}
    if not isinstance(events_data, dict):
        events_data = {"provider": str(events_data)}
    events_provider = (
        events_data.get("provider") or os.getenv("VOODOO_EVENTS_PROVIDER") or "sqlite"
    )
    events_url = events_data.get("url") or os.getenv("VOODOO_EVENTS_URL") or ""
    events_path = events_data.get("path") or os.getenv("VOODOO_EVENTS_PATH") or db_path
    return EventsConfig(
        provider=events_provider,
        url=events_url,
        path=events_path,
        extra={
            k: v for k, v in events_data.items() if k not in ("provider", "url", "path")
        },
    )


def _build_objects_config(file_data: dict[str, Any]) -> ObjectsConfig:
    objects_data = file_data.get("objects") or {}
    if not isinstance(objects_data, dict):
        objects_data = {"provider": str(objects_data)}
    objects_provider = objects_data.get("provider") or os.getenv(
        "VOODOO_OBJECTS_PROVIDER"
    )
    if not objects_provider:
        if (
            os.getenv("VOODOO_BUCKET")
            or os.getenv("AWS_BUCKET")
            or os.getenv("AWS_ACCESS_KEY_ID")
        ):
            objects_provider = "s3"
        else:
            objects_provider = "local"
    objects_bucket = (
        objects_data.get("bucket")
        or os.getenv("VOODOO_BUCKET")
        or os.getenv("AWS_BUCKET")
        or ""
    )
    objects_endpoint = (
        objects_data.get("endpoint")
        or os.getenv("VOODOO_OBJECTS_ENDPOINT")
        or os.getenv("AWS_ENDPOINT_URL")
        or ""
    )
    objects_base_dir = (
        objects_data.get("base_dir")
        or os.getenv("VOODOO_OBJECTS_DIR")
        or ".voodoo/objects"
    )
    return ObjectsConfig(
        provider=objects_provider,
        bucket=objects_bucket,
        endpoint=objects_endpoint,
        base_dir=objects_base_dir,
        extra={
            k: v
            for k, v in objects_data.items()
            if k not in ("provider", "bucket", "endpoint", "base_dir")
        },
    )


def _build_cache_config(file_data: dict[str, Any]) -> CacheConfig:
    cache_data = file_data.get("cache") or {}
    if not isinstance(cache_data, dict):
        cache_data = {"provider": str(cache_data)}
    cache_provider = (
        cache_data.get("provider") or os.getenv("VOODOO_CACHE_PROVIDER") or "memory"
    )
    cache_url = cache_data.get("url") or os.getenv("VOODOO_CACHE_URL") or ""
    return CacheConfig(
        provider=cache_provider,
        url=cache_url,
        extra={k: v for k, v in cache_data.items() if k not in ("provider", "url")},
    )


def _build_models_config(file_data: dict[str, Any]) -> ModelsConfig:
    models_data = file_data.get("models") or {}
    if not isinstance(models_data, dict):
        models_data = {"default": str(models_data)}
    models_default = (
        models_data.get("default")
        or os.getenv("VOODOO_MODELS_DEFAULT")
        or "mock:default"
    )
    models_aliases = models_data.get("aliases") or {}
    return ModelsConfig(
        default=models_default,
        aliases=models_aliases if isinstance(models_aliases, dict) else {},
        extra={k: v for k, v in models_data.items() if k not in ("default", "aliases")},
    )


def _pick(
    file_data: dict[str, Any],
    key: str,
    env: str,
    convert_file: Callable[[Any], Any],
    convert_env: Callable[[str], Any] | None = None,
) -> tuple[str, Any] | None:
    """First value wins: explicit file config > env var > None."""
    if key in file_data:
        return key, convert_file(file_data[key])
    if env and env in os.environ:
        return key, (convert_env or convert_file)(os.environ[env])
    return None


def _build_core_scalars(file_data: dict[str, Any]) -> dict[str, Any]:
    args: dict[str, Any] = {}
    # ``debug``: file ``bool(...)``; env via _resolve_debug (1/true/yes/on).
    scalars: list[tuple[str, str, Callable[[Any], Any], Callable[[str], Any]]] = [
        ("env", "VOODOO_ENV", str, str),
        ("debug", "VOODOO_DEBUG", bool, lambda _val: _resolve_debug()),
        ("port", "VOODOO_PORT", int, int),
        ("host", "VOODOO_HOST", str, str),
        ("storage_dir", "VOODOO_STORAGE_DIR", str, str),
    ]
    for key, env, convert_file, convert_env in scalars:
        picked = _pick(file_data, key, env, convert_file, convert_env)
        if picked:
            args[picked[0]] = picked[1]
    return args


def _build_runtime_config(file_data: dict[str, Any]) -> RuntimeConfig:
    runtime_data = file_data.get("runtime") or {}
    if not isinstance(runtime_data, dict):
        runtime_data = {"mode": str(runtime_data)}
    if "mode" not in runtime_data and "VOODOO_RUNTIME_MODE" in os.environ:
        runtime_data["mode"] = os.environ["VOODOO_RUNTIME_MODE"]
    elif "mode" not in runtime_data and "VOODOO_ENV" in os.environ:
        runtime_data["mode"] = os.environ["VOODOO_ENV"]
    return RuntimeConfig(**runtime_data)


def _load_raw_file_data(file_path: str | None) -> dict[str, Any]:
    if file_path:
        if file_path.endswith(".toml"):
            return load_toml_config(file_path)
        return load_yaml_config(file_path)
    file_data = load_toml_config()
    if not file_data:
        file_data = load_yaml_config()
    return file_data


def get_config(
    file_path: str | None = None,
    overrides: dict[str, Any] | None = None,
) -> VoodooConfig:
    """Gets the merged configuration from config file, env vars, and defaults.

    Precedence: explicit file config > env vars > local defaults.
    """
    file_data = _load_raw_file_data(file_path)
    if overrides:
        file_data = {**file_data, **interpolate_env_vars(overrides)}

    config_args = _build_core_scalars(file_data)
    config_args["runtime"] = _build_runtime_config(file_data)

    # Database sub-block
    db_data = file_data.get("database") or {}
    db_path = (
        (db_data.get("path") if isinstance(db_data, dict) else None)
        or (db_data.get("url") if isinstance(db_data, dict) else None)
        or os.getenv("VOODOO_DB_PATH")
        or os.getenv("DATABASE_URL")
    )
    if not db_path:
        db_path = _resolve_db_path()
    config_args["db_path"] = db_path
    config_args["database"] = _build_database_config(file_data, db_path)

    # Queue, events, objects, cache, models
    config_args["queue"] = _build_queue_config(file_data)
    config_args["events"] = _build_events_config(file_data, db_path)
    config_args["objects"] = _build_objects_config(file_data)
    config_args["cache"] = _build_cache_config(file_data)
    config_args["models"] = _build_models_config(file_data)

    # Existing sub-configurations
    if "seo" in file_data and isinstance(file_data["seo"], dict):
        config_args["seo"] = SEOConfig(**file_data["seo"])
    if "auth" in file_data and isinstance(file_data["auth"], dict):
        config_args["auth"] = AuthConfig(**file_data["auth"])
    if "theme" in file_data and isinstance(file_data["theme"], dict):
        config_args["theme"] = ThemeConfig(**file_data["theme"])
    if "security" in file_data and isinstance(file_data["security"], dict):
        config_args["security"] = SecurityConfig(**file_data["security"])

    # Store any extra custom configuration
    known_keys = {
        "env",
        "debug",
        "db_path",
        "storage_dir",
        "port",
        "host",
        "runtime",
        "database",
        "queue",
        "events",
        "objects",
        "cache",
        "models",
        "seo",
        "auth",
        "security",
        "theme",
        "extra",
    }
    config_args["extra"] = {k: v for k, v in file_data.items() if k not in known_keys}

    return VoodooConfig(**config_args)


# Global config instance
config = get_config()
