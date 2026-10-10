"""Double-submit-cookie CSRF protection."""

from __future__ import annotations

import secrets
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from voodoo.config import config

__all__ = ["CSRFMiddleware", "generate_csrf_token", "set_csrf_cookie"]


def generate_csrf_token() -> str:
    """Generates a cryptographically secure random CSRF token."""
    return secrets.token_urlsafe(32)


def set_csrf_cookie(
    response: Response,
    token: str | None = None,
    *,
    config_override: Any = None,
) -> str:
    """Sets a CSRF token cookie on the response."""
    csrf_token = token or generate_csrf_token()
    resolved = config_override or config
    response.set_cookie(
        key=resolved.security.csrf_cookie_name,
        value=csrf_token,
        path="/",
        secure=resolved.auth.cookie_secure,
        httponly=False,  # Accessible to JS client for X-CSRF-Token header
        samesite="lax",
    )
    return csrf_token


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    Double-submit cookie CSRF protection middleware.
    Exempts safe methods (GET, HEAD, OPTIONS) and machine-to-machine API key requests.
    """

    # TRACE is intentionally not exempt: if an application exposes a TRACE
    # route, it must not become a CSRF bypass (and production deployments
    # should disable TRACE at the edge).
    EXEMPT_METHODS: set[str] = {"GET", "HEAD", "OPTIONS"}
    EXEMPT_PATHS: set[str] = {"/_voodoo_ws", "/voodoo/mesh/ws", "/openapi.json"}

    def __init__(self, app: Any, *, config_override: Any = None) -> None:
        super().__init__(app)
        self._config = config_override or config

    @staticmethod
    def _has_validated_non_cookie_auth(request: Request) -> bool:
        user = getattr(request.state, "user", None)
        return bool(
            user is not None
            and getattr(user, "is_authenticated", False)
            and getattr(user, "auth_type", None) in {"api_key", "token"}
        )

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        sec_cfg = self._config.security

        if not sec_cfg.csrf_enabled:
            return await call_next(request)

        # Exempt safe methods and internal web sockets
        if request.method in self.EXEMPT_METHODS or (
            request.method == "GET" and request.url.path in self.EXEMPT_PATHS
        ):
            response = await call_next(request)
            # Ensure CSRF cookie is set on GET requests if missing
            if (
                request.method == "GET"
                and sec_cfg.csrf_cookie_name not in request.cookies
            ):
                set_csrf_cookie(response, config_override=self._config)
            return response

        # Header presence is not authentication. AuthMiddleware must validate
        # the credential before a non-cookie request can bypass CSRF.
        if self._has_validated_non_cookie_auth(request):
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
