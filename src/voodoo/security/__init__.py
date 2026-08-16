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
]
