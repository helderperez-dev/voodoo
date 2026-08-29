"""Voodoo security package.

This package re-exports the names that previously lived in the flat
``voodoo/security.py`` module, now split by concern:

- ``voodoo/security/headers.py`` — ``SecurityHeadersMiddleware``
- ``voodoo/security/cors.py`` — ``CORSMiddleware``
- ``voodoo/security/csrf.py`` — ``CSRFMiddleware``, ``generate_csrf_token``,
  ``set_csrf_cookie``
- ``voodoo/security/rate_limit.py`` — ``RateLimiter``, ``RateLimitMiddleware``
  and the shared ``rate_limiter`` singleton
- ``voodoo/security/passwords.py`` — ``validate_password_strength``
- ``voodoo/security/secrets.py`` — ``SecretStore``, ``EnvSecretStore``,
  ``LocalSecretStore``, ``secrets``, ``configure`` (Sprint 19)
- ``voodoo/security/redaction.py`` — ``redact``, ``redact_string``,
  ``RedactionGuard`` (Sprint 19)
"""

from voodoo.security.cors import CORSMiddleware
from voodoo.security.csrf import (
    CSRFMiddleware,
    generate_csrf_token,
    set_csrf_cookie,
)
from voodoo.security.headers import SecurityHeadersMiddleware
from voodoo.security.passwords import validate_password_strength
from voodoo.security.rate_limit import (
    RateLimiter,
    RateLimitMiddleware,
    rate_limiter,
)
from voodoo.security.redaction import RedactionGuard, redact, redact_string
from voodoo.security.secrets import (
    EnvSecretStore,
    LocalSecretStore,
    SecretsError,
    SecretStore,
    secrets,
)
from voodoo.security.secrets import (
    configure as configure_secrets,
)

__all__ = [
    # Headers
    "SecurityHeadersMiddleware",
    # CORS
    "CORSMiddleware",
    # CSRF
    "CSRFMiddleware",
    "generate_csrf_token",
    "set_csrf_cookie",
    # Rate limiting
    "RateLimiter",
    "RateLimitMiddleware",
    "rate_limiter",
    # Passwords
    "validate_password_strength",
    # Secrets (Sprint 19)
    "SecretStore",
    "EnvSecretStore",
    "LocalSecretStore",
    "SecretsError",
    "secrets",
    "configure_secrets",
    # Redaction (Sprint 19)
    "RedactionGuard",
    "redact",
    "redact_string",
]
