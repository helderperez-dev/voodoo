from contextvars import Token

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from voodoo.auth.jwt import AuthError, decode_access_token
from voodoo.auth.user import AuthUser, User, current_user
from voodoo.config import config

# =========================================================================
# ASGI Auth Middleware
# =========================================================================


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Extracts and authenticates user from:
    1. Authorization: Bearer <token>
    2. X-API-Key: <key> or Authorization: ApiKey <key>
    3. Session cookie (voodoo_auth)

    Populates request.state.user and current_user ContextVar.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        user = AuthUser(is_authenticated=False)
        auth_header = request.headers.get("Authorization", "").strip()
        api_key_header = request.headers.get("X-API-Key", "").strip()
        cookie_val = request.cookies.get(config.auth.cookie_name)

        # 1. Check API Key Header
        if api_key_header:
            db_user = await User.find_by_api_key(api_key_header)
            if db_user:
                user = db_user.to_auth_user(auth_type="api_key")
            else:
                # Invalid API key
                user = AuthUser(
                    id=None,
                    username="api_client",
                    role="service",
                    roles=["service"],
                    scopes=["read", "write"],
                    auth_type="api_key",
                    is_authenticated=False,
                )
        # 2. Check Bearer Token or ApiKey in Authorization Header
        elif auth_header:
            if auth_header.startswith("Bearer "):
                token_str = auth_header[7:].strip()
                try:
                    payload = decode_access_token(token_str)
                    user = AuthUser(
                        id=payload.get("sub") or payload.get("id"),
                        email=payload.get("email"),
                        username=payload.get("username"),
                        role=payload.get("role", "user"),
                        roles=payload.get("roles", [payload.get("role", "user")]),
                        scopes=payload.get("scopes", []),
                        auth_type="token",
                        is_authenticated=True,
                        raw_data=payload,
                    )
                except AuthError:
                    user = AuthUser(is_authenticated=False)
            elif auth_header.startswith("ApiKey "):
                raw_key = auth_header[7:].strip()
                db_user = await User.find_by_api_key(raw_key)
                if db_user:
                    user = db_user.to_auth_user(auth_type="api_key")
        # 3. Check Session Cookie
        elif cookie_val:
            try:
                payload = decode_access_token(cookie_val)
                user = AuthUser(
                    id=payload.get("sub") or payload.get("id"),
                    email=payload.get("email"),
                    username=payload.get("username"),
                    role=payload.get("role", "user"),
                    roles=payload.get("roles", [payload.get("role", "user")]),
                    scopes=payload.get("scopes", []),
                    auth_type="session",
                    is_authenticated=True,
                    raw_data=payload,
                )
            except AuthError:
                user = AuthUser(is_authenticated=False)

        # Set request state and task context variable
        request.state.user = user
        ctx_token: Token[AuthUser | None] = current_user.set(user)
        try:
            response = await call_next(request)
            return response
        finally:
            current_user.reset(ctx_token)
