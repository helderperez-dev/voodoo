"""Voodoo authentication: JWT tokens, passwords & API keys, user context,
guards, cookies, and ASGI middleware.

Split by concern; this package re-exports the complete public surface of the
former flat ``voodoo.auth`` module for backwards compatibility::

    from voodoo.auth import AuthMiddleware, AuthUser, login_required
"""

from voodoo.auth.cookies import (
    _normalize_samesite,
    clear_auth_cookie,
    set_auth_cookie,
)
from voodoo.auth.guards import (
    login_required,
    require_api_key,
    require_auth,
    require_roles,
    require_scopes,
    requires_api_key,
    requires_permission,
    requires_permissions,
    requires_role,
    requires_roles,
    requires_scopes,
)
from voodoo.auth.jwt import (
    AuthError,
    ExpiredTokenError,
    InvalidCredentialsError,
    InvalidTokenError,
    PermissionDeniedError,
    _b64decode_str,
    _b64encode_str,
    create_access_token,
    decode_access_token,
)
from voodoo.auth.middleware import AuthMiddleware
from voodoo.auth.passwords import (
    generate_api_key,
    generate_secret_key,
    hash_api_key,
    hash_password,
    verify_api_key,
    verify_password,
)
from voodoo.auth.user import AuthUser, User, current_user, get_current_user

__all__ = [
    "AuthError",
    "AuthMiddleware",
    "AuthUser",
    "ExpiredTokenError",
    "InvalidCredentialsError",
    "InvalidTokenError",
    "PermissionDeniedError",
    "User",
    "clear_auth_cookie",
    "create_access_token",
    "current_user",
    "decode_access_token",
    "generate_api_key",
    "generate_secret_key",
    "get_current_user",
    "hash_api_key",
    "hash_password",
    "login_required",
    "require_api_key",
    "require_auth",
    "require_roles",
    "require_scopes",
    "requires_api_key",
    "requires_permission",
    "requires_permissions",
    "requires_role",
    "requires_roles",
    "requires_scopes",
    "set_auth_cookie",
    "verify_api_key",
    "verify_password",
    "_normalize_samesite",
    "_b64decode_str",
    "_b64encode_str",
]
