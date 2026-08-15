import asyncio
import hashlib
import re
import secrets
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from voodoo.config import config

# =========================================================================
# Security Headers Middleware
# =========================================================================


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Applies industry-standard HTTP security headers to all responses.
    """

    async def dispatch(  # noqa: C901
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        sec_cfg = config.security

        if not sec_cfg.headers_enabled:
            return response

        # Standard hardening headers
        if sec_cfg.content_type_options:
            response.headers["X-Content-Type-Options"] = sec_cfg.content_type_options
        if sec_cfg.frame_options:
            response.headers["X-Frame-Options"] = sec_cfg.frame_options
        if sec_cfg.xss_protection:
            response.headers["X-XSS-Protection"] = sec_cfg.xss_protection
        if sec_cfg.referrer_policy:
            response.headers["Referrer-Policy"] = sec_cfg.referrer_policy

        # HSTS (Strict-Transport-Security)
        if sec_cfg.hsts_enabled:
            response.headers["Strict-Transport-Security"] = (
                f"max-age={sec_cfg.hsts_max_age}; includeSubDomains"
            )

        # Content-Security-Policy (CSP)
        if sec_cfg.csp_directives:
            csp_parts = []
            for directive, val in sec_cfg.csp_directives.items():
                if val:
                    csp_parts.append(f"{directive} {val}")
            if csp_parts:
                response.headers["Content-Security-Policy"] = "; ".join(csp_parts)

        return response


# =========================================================================
# CORS Middleware
# =========================================================================


class CORSMiddleware(BaseHTTPMiddleware):
    """
    CORS (Cross-Origin Resource Sharing) middleware supporting preflight and credentials.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        sec_cfg = config.security

        if not sec_cfg.cors_enabled:
            return await call_next(request)

        origin = request.headers.get("origin")

        # Handle Preflight OPTIONS request
        if (
            request.method == "OPTIONS"
            and "access-control-request-method" in request.headers
        ):
            response = Response(status_code=204)
            self._apply_cors_headers(response, origin)
            return response

        response = await call_next(request)
        self._apply_cors_headers(response, origin)
        return response

    def _apply_cors_headers(self, response: Response, origin: str | None) -> None:
        sec_cfg = config.security

        # Determine allowed origin
        allowed_origins = sec_cfg.cors_origins
        if "*" in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = (
                "*" if not sec_cfg.cors_allow_credentials else (origin or "*")
            )
        elif origin and origin in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin

        if sec_cfg.cors_allow_credentials:
            response.headers["Access-Control-Allow-Credentials"] = "true"

        if sec_cfg.cors_allow_methods:
            response.headers["Access-Control-Allow-Methods"] = ", ".join(
                sec_cfg.cors_allow_methods
            )

        if sec_cfg.cors_allow_headers:
            response.headers["Access-Control-Allow-Headers"] = ", ".join(
                sec_cfg.cors_allow_headers
            )

        response.headers["Access-Control-Max-Age"] = "86400"


# =========================================================================
# CSRF (Cross-Site Request Forgery) Protection
# =========================================================================


def generate_csrf_token() -> str:
    """Generates a cryptographically secure random CSRF token."""
    return secrets.token_urlsafe(32)


def set_csrf_cookie(response: Response, token: str | None = None) -> str:
    """Sets a CSRF token cookie on the response."""
    csrf_token = token or generate_csrf_token()
    response.set_cookie(
        key=config.security.csrf_cookie_name,
        value=csrf_token,
        path="/",
        secure=config.auth.cookie_secure,
        httponly=False,  # Accessible to JS client for X-CSRF-Token header
        samesite="lax",
    )
    return csrf_token


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    Double-submit cookie CSRF protection middleware.
    Exempts safe methods (GET, HEAD, OPTIONS) and machine-to-machine API key requests.
    """

    EXEMPT_METHODS: set[str] = {"GET", "HEAD", "OPTIONS", "TRACE"}
    EXEMPT_PATHS: set[str] = {"/_voodoo_ws", "/voodoo/mesh/ws", "/openapi.json"}

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        sec_cfg = config.security

        if not sec_cfg.csrf_enabled:
            return await call_next(request)

        # Exempt safe methods and internal web sockets
        if (
            request.method in self.EXEMPT_METHODS
            or request.url.path in self.EXEMPT_PATHS
        ):
            response = await call_next(request)
            # Ensure CSRF cookie is set on GET requests if missing
            if (
                request.method == "GET"
                and sec_cfg.csrf_cookie_name not in request.cookies
            ):
                set_csrf_cookie(response)
            return response

        # Exempt M2M API requests with Bearer or API Key headers
        if (
            request.headers.get("X-API-Key")
            or request.headers.get("Authorization", "").startswith("Bearer ")
            or request.headers.get("Authorization", "").startswith("ApiKey ")
        ):
            return await call_next(request)

        cookie_token = request.cookies.get(sec_cfg.csrf_cookie_name)
        header_token = request.headers.get(sec_cfg.csrf_header_name)

        # Verify token match
        if (
            not cookie_token
            or not header_token
            or not secrets.compare_digest(cookie_token, header_token)
        ):
            return JSONResponse(
                {
                    "error": "CSRF verification failed: invalid or missing CSRF token",
                    "code": 403,
                },
                status_code=403,
            )

        return await call_next(request)


# =========================================================================
# Rate Limiting (Sliding Window In-Memory Limiter)
# =========================================================================


class RateLimiter:
    """In-memory sliding window rate limiter."""

    def __init__(self):
        # Maps client_id -> list of timestamps
        self.history: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def is_allowed(
        self, client_id: str, max_requests: int, window_seconds: int
    ) -> tuple[bool, int, int]:
        """
        Checks if client is allowed to make a request.
        Returns: (is_allowed, remaining_requests, reset_after_seconds)
        """
        now = time.time()
        window_start = now - window_seconds

        async with self._lock:
            timestamps = self.history[client_id]
            # Filter out timestamps outside window
            valid_timestamps = [t for t in timestamps if t > window_start]

            if len(valid_timestamps) >= max_requests:
                # Calculate when the oldest request in the window will drop off
                oldest = valid_timestamps[0]
                retry_after = max(1, int(window_seconds - (now - oldest)))
                self.history[client_id] = valid_timestamps
                return False, 0, retry_after

            valid_timestamps.append(now)
            self.history[client_id] = valid_timestamps
            remaining = max(0, max_requests - len(valid_timestamps))
            return True, remaining, 0

    def reset(self):
        """Clears all rate limit records."""
        self.history.clear()


rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware protecting against abuse and brute-force attacks.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        sec_cfg = config.security

        if not sec_cfg.rate_limit_enabled:
            return await call_next(request)

        # Determine client identifier: API key, user id, or client IP
        client_ip = request.client.host if request.client else "127.0.0.1"
        api_key = request.headers.get("X-API-Key")
        auth_header = request.headers.get("Authorization", "")

        client_id = f"ip:{client_ip}"
        if api_key:
            client_id = f"key:{hashlib.sha256(api_key.encode()).hexdigest()[:16]}"
        elif auth_header.startswith("Bearer "):
            client_id = f"token:{hashlib.sha256(auth_header.encode()).hexdigest()[:16]}"

        allowed, remaining, retry_after = await rate_limiter.is_allowed(
            client_id=client_id,
            max_requests=sec_cfg.rate_limit_requests,
            window_seconds=sec_cfg.rate_limit_window,
        )

        if not allowed:
            resp = JSONResponse(
                {
                    "error": "Too Many Requests",
                    "message": f"Rate limit exceeded. Try again in {retry_after} seconds.",
                    "code": 429,
                    "retry_after": retry_after,
                },
                status_code=429,
            )
            resp.headers["Retry-After"] = str(retry_after)
            resp.headers["X-RateLimit-Limit"] = str(sec_cfg.rate_limit_requests)
            resp.headers["X-RateLimit-Remaining"] = "0"
            resp.headers["X-RateLimit-Reset"] = str(retry_after)
            return resp

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(sec_cfg.rate_limit_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


# =========================================================================
# Password Strength & Input Validation
# =========================================================================


def validate_password_strength(password: str, min_length: int = 8) -> tuple[bool, str]:
    """
    Validates that a password satisfies minimum security requirements:
    - Minimum length
    - At least one letter and at least one digit or special character
    """
    if not password or len(password) < min_length:
        return False, f"Password must be at least {min_length} characters long"

    has_letter = bool(re.search(r"[A-Za-z]", password))
    has_digit = bool(re.search(r"\d", password))
    has_symbol = bool(re.search(r"[^A-Za-z0-9]", password))

    if not has_letter:
        return False, "Password must contain at least one letter"
    if not (has_digit or has_symbol):
        return False, "Password must contain at least one number or symbol"

    return True, ""
