import secrets

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from voodoo.config import config


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
