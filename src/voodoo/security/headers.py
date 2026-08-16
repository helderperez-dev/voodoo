from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from voodoo.config import config


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

        if sec_cfg.permissions_policy:
            response.headers["Permissions-Policy"] = sec_cfg.permissions_policy

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
