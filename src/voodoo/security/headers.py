"""HTTP response security headers."""

from __future__ import annotations

import base64
import hashlib
import re
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from voodoo.config import config

__all__ = ["SecurityHeadersMiddleware"]


_INLINE_SCRIPT_RE = re.compile(
    rb"<script(?:\s[^>]*?)?>(?!\s*</script>)(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)


def _inline_script_hashes(body: bytes) -> list[str]:
    """Return CSP SHA-256 sources for inline executable script bodies."""
    hashes: list[str] = []
    for match in _INLINE_SCRIPT_RE.finditer(body):
        tag = match.group(0).split(b">", 1)[0].lower()
        if b" src=" in tag or b" src=" in tag.replace(b"'", b'"'):
            continue
        digest = base64.b64encode(hashlib.sha256(match.group(1)).digest()).decode(
            "ascii"
        )
        hashes.append(f"'sha256-{digest}'")
    return hashes


async def _materialize_html_response(response: Response) -> tuple[Response, bytes | None]:
    """Read a streaming HTML response so its inline scripts can be hashed."""
    content_type = response.headers.get("content-type", "").lower()
    if "text/html" not in content_type:
        return response, None
    body = getattr(response, "body", None)
    if body is None:
        iterator = getattr(response, "body_iterator", None)
        if iterator is None:
            return response, None
        body = b"".join([chunk async for chunk in iterator])
        headers = dict(response.headers)
        headers.pop("content-length", None)
        response = Response(
            content=body,
            status_code=response.status_code,
            headers=headers,
            media_type=content_type.split(";", 1)[0],
            background=response.background,
        )
    return response, body


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
            f"max-age={getattr(sec_cfg, 'hsts_max_age', 31536000)}; includeSubDomains"
        )
    csp = _csp_header(sec_cfg)
    if csp:
        response.headers["Content-Security-Policy"] = csp


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Applies industry-standard HTTP security headers to all responses."""

    def __init__(self, app: Any, *, config_override: Any = None) -> None:
        super().__init__(app)
        self._config = config_override or config

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        sec_cfg = self._config.security
        if sec_cfg.headers_enabled:
            response, body = await _materialize_html_response(response)
            if body is not None:
                directives = getattr(sec_cfg, "csp_directives", None) or {}
                script_src = directives.get("script-src", "")
                hashes = _inline_script_hashes(body)
                if hashes and "'unsafe-inline'" not in script_src:
                    directives = dict(directives)
                    directives["script-src"] = " ".join(
                        part for part in (script_src, *hashes) if part
                    )
                    # Do not mutate the shared application config. The helper
                    # accepts an object with the same attribute contract.
                    sec_cfg = type("SecurityHeadersConfig", (), {
                        **vars(sec_cfg),
                        "csp_directives": directives,
                    })()
            _apply_security_headers(response, sec_cfg)
        return response
