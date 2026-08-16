from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from voodoo.config import config


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
            if not sec_cfg.cors_allow_credentials:
                response.headers["Access-Control-Allow-Origin"] = "*"
            else:
                # When credentials are involved, reflect the actual origin
                # instead of the wildcard literal (per CORS spec).
                response.headers["Access-Control-Allow-Origin"] = origin or "*"
                if origin:
                    response.headers["Vary"] = "Origin"
        elif origin and origin in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"

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
