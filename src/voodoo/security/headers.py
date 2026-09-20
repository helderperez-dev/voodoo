from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from voodoo.config import config


def _configured_headers(sec_cfg: object) -> dict[str, str]:
    pairs = {
        "X-Content-Type-Options": getattr(sec_cfg, "content_type_options", None),
        "X-Frame-Options": getattr(sec_cfg, "frame_options", None),
        "X-XSS-Protection": getattr(sec_cfg, "xss_protection", None),
        "Referrer-Policy": getattr(sec_cfg, "referrer_policy", None),
        "Permissions-Policy": getattr(sec_cfg, "permissions_policy", None),
    }
    return {name: value for name, value in pairs.items() if value}


def _csp_header(sec_cfg: object) -> str | None:
    directives = getattr(sec_cfg, "csp_directives", None) or {}
    parts = [f"{directive} {value}" for directive, value in directives.items() if value]
    return "; ".join(parts) or None


def _apply_security_headers(response: Response, sec_cfg: object) -> None:
    response.headers.update(_configured_headers(sec_cfg))
    if getattr(sec_cfg, "hsts_enabled", False):
        response.headers["Strict-Transport-Security"] = (
            f"max-age={sec_cfg.hsts_max_age}; includeSubDomains"
        )
    csp = _csp_header(sec_cfg)
    if csp:
        response.headers["Content-Security-Policy"] = csp


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Applies industry-standard HTTP security headers to all responses."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        sec_cfg = config.security
        if sec_cfg.headers_enabled:
            _apply_security_headers(response, sec_cfg)
        return response
