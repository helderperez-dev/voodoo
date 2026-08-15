import os
import yaml
from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load .env variables first
load_dotenv()


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
    csp_directives: Dict[str, str] = Field(
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
    db_path: str = Field(
        default_factory=lambda: os.getenv("VOODOO_DB_PATH", ".data/voodoo.db")
    )
    storage_dir: str = Field(
        default_factory=lambda: os.getenv("VOODOO_STORAGE_DIR", "storage")
    )
    port: int = Field(default_factory=lambda: int(os.getenv("VOODOO_PORT", "8000")))
    host: str = Field(default_factory=lambda: os.getenv("VOODOO_HOST", "0.0.0.0"))
    seo: SEOConfig = Field(default_factory=SEOConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    extra: Dict[str, Any] = Field(default_factory=dict)


def load_yaml_config(file_path: str = "voodoo.yaml") -> Dict[str, Any]:
    """Loads configuration from a YAML file if it exists."""
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            try:
                return yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                print(f"Error parsing {file_path}: {e}")
    return {}


def get_config() -> VoodooConfig:
    """Gets the merged configuration from env vars and YAML."""
    yaml_data = load_yaml_config()

    # We allow yaml to override or extend defaults
    # but environment variables usually take precedence in production.
    # For this simple implementation, we'll merge them.
    config_args = {}

    # Add mapped YAML fields if they match our known fields
    if "env" in yaml_data:
        config_args["env"] = yaml_data["env"]
    if "db_path" in yaml_data:
        config_args["db_path"] = yaml_data["db_path"]
    if "storage_dir" in yaml_data:
        config_args["storage_dir"] = yaml_data["storage_dir"]
    if "port" in yaml_data:
        config_args["port"] = yaml_data["port"]
    if "host" in yaml_data:
        config_args["host"] = yaml_data["host"]

    # Load sub-configurations
    if "seo" in yaml_data and isinstance(yaml_data["seo"], dict):
        config_args["seo"] = SEOConfig(**yaml_data["seo"])
    if "auth" in yaml_data and isinstance(yaml_data["auth"], dict):
        config_args["auth"] = AuthConfig(**yaml_data["auth"])
    if "security" in yaml_data and isinstance(yaml_data["security"], dict):
        config_args["security"] = SecurityConfig(**yaml_data["security"])

    # Store any extra custom configuration
    config_args["extra"] = {
        k: v
        for k, v in yaml_data.items()
        if k not in config_args and k not in ("seo", "auth", "security")
    }

    return VoodooConfig(**config_args)


# Global config instance
config = get_config()
