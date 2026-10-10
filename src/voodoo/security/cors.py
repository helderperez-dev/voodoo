"""Cross-origin request policy middleware."""

from __future__ import annotations

from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from voodoo.config import config

__all__ = ["CORSMiddleware"]


class CORSMiddleware(BaseHTTPMiddleware):
    """
    CORS (Cross-Origin Resource Sharing) middleware supporting preflight and credentials.
    """

    def __init__(self, app: Any, *, config_override: Any = None) -> None:
        super().__init__(app)
        self._config = config_override or config

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        sec_cfg = self._config.security

        if not sec_cfg.cors_enabled:
            return await call_next(request)

        origin = request.headers.get("origin")

        # Handle Preflight OPTIONS request
        if (
            request.method == "OPTIONS"
            and "access-control-request-method" in request.headers
        ):
            if not self._preflight_allowed(request):
                return Response(status_code=403)
            response = Response(status_code=204)
            self._apply_cors_headers(response, origin)
            return response

        response = await call_next(request)
        self._apply_cors_headers(response, origin)
        return response

    def _preflight_allowed(self, request: Request) -> bool:
        """Fail closed when a browser preflight asks for an unapproved policy."""
        sec_cfg = self._config.security
        origin = request.headers.get("origin")
        allowed_origins = sec_cfg.cors_origins
        if not origin:
            return False
        if "*" in allowed_origins:
            # A wildcard cannot be used for credentialed requests.  Do not
            # acknowledge a preflight that the response cannot authorize.
            if sec_cfg.cors_allow_credentials:
                return False
        elif origin not in allowed_origins:
            return False

        requested_method = request.headers.get("access-control-request-method", "")
        methods = {str(method).upper() for method in sec_cfg.cors_allow_methods}
        if "*" not in methods and requested_method.upper() not in methods:
            return False

        requested_headers = request.headers.get("access-control-request-headers", "")
        allowed_headers = {
            str(header).strip().lower() for header in sec_cfg.cors_allow_headers
        }
        if "*" not in allowed_headers:
            for header in requested_headers.split(","):
                if header.strip().lower() not in allowed_headers:
                    return False
        return True

    def _apply_cors_headers(self, response: Response, origin: str | None) -> None:
        sec_cfg = self._config.security

        # Determine allowed origin
        allowed_origins = sec_cfg.cors_origins
        if "*" in allowed_origins:
            if not sec_cfg.cors_allow_credentials:
                response.headers["Access-Control-Allow-Origin"] = "*"
            # Wildcard + credentials is intentionally denied instead of
            # reflecting an attacker-controlled Origin.
        elif origin and origin in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"

        if sec_cfg.cors_allow_credentials and response.headers.get(
            "Access-Control-Allow-Origin"
        ):
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
