import os
from typing import Any, Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from voodoo.core.errors import ConfigurationError

# Load .env variables first
load_dotenv()


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
    """Database location: VOODOO_DB_PATH > DATABASE_URL (sqlite) > default."""
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
        raise ConfigurationError(
            f"DATABASE_URL scheme '{scheme}://' is not supported yet. "
            "Use a sqlite:///... URL or VOODOO_DB_PATH. Additional backends "
            "arrive as optional extras (e.g. voodoo[postgres]) in a later release."
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
    seo: SEOConfig = Field(default_factory=SEOConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    extra: dict[str, Any] = Field(default_factory=dict)


def load_yaml_config(file_path: str = "voodoo.yaml") -> dict[str, Any]:
    """Loads configuration from a YAML file if it exists."""
    if os.path.exists(file_path):
        with open(file_path) as f:
            try:
                return yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                print(f"Error parsing {file_path}: {e}")
    return {}


def load_toml_config(file_path: str = "voodoo.toml") -> dict[str, Any]:
    """Loads configuration from a TOML file if it exists."""
    if os.path.exists(file_path):
        try:
            import tomllib

            with open(file_path, "rb") as f:
                return tomllib.load(f)
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
    return {}


def get_config() -> VoodooConfig:
    """Gets the merged configuration from env vars and config file.

    Precedence: voodoo.toml > voodoo.yaml > environment variables > defaults.
    """
    # Prefer voodoo.toml; fall back to voodoo.yaml for compatibility
    file_data = load_toml_config()
    if not file_data:
        file_data = load_yaml_config()

    # We allow config file to override or extend defaults
    # but environment variables usually take precedence in production.
    # For this simple implementation, we'll merge them.
    config_args = {}

    # Add mapped file fields if they match our known fields
    if "env" in file_data:
        config_args["env"] = file_data["env"]
    if "db_path" in file_data:
        config_args["db_path"] = file_data["db_path"]
    if "storage_dir" in file_data:
        config_args["storage_dir"] = file_data["storage_dir"]
    if "port" in file_data:
        config_args["port"] = file_data["port"]
    if "host" in file_data:
        config_args["host"] = file_data["host"]

    # Load sub-configurations
    if "seo" in file_data and isinstance(file_data["seo"], dict):
        config_args["seo"] = SEOConfig(**file_data["seo"])
    if "auth" in file_data and isinstance(file_data["auth"], dict):
        config_args["auth"] = AuthConfig(**file_data["auth"])
    if "security" in file_data and isinstance(file_data["security"], dict):
        config_args["security"] = SecurityConfig(**file_data["security"])

    # Store any extra custom configuration
    config_args["extra"] = {
        k: v
        for k, v in file_data.items()
        if k not in config_args and k not in ("seo", "auth", "security")
    }

    return VoodooConfig(**config_args)


# Global config instance
config = get_config()
